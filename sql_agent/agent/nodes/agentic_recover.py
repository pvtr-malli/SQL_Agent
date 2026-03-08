import re

import sqlglot
import sqlglot.expressions as exp
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from sql_agent.agent.state import AgentState
from sql_agent.config.models import TableSchema
from sql_agent.config.settings import MAX_REACT_STEPS
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.utils.logger import get_logger

logger = get_logger(__name__)


# This is a bounded agentic system, only 3 tools allowed. not fully open one
# this is helpful in. prompt injection protection also.


_FENCE_RE = re.compile(r"^```(?:sql)?\s*\n?|\n?```$", re.IGNORECASE)

_SYSTEM_PROMPT = (
    "You are a SQL debugging expert. Two previous attempts to generate valid SQL failed.\n"
    "Your job:\n"
    "  1. Study the error from the previous attempt.\n"
    "  2. Call search_tables to find relevant tables.\n"
    "  3. Call get_table_schemas (batch all tables in ONE call) to inspect columns.\n"
    "  4. Draft a SQL SELECT query.\n"
    "  5. Call validate_sql to check it. Fix any errors and re-validate.\n"
    "  6. Once validate_sql returns 'valid', output ONLY the final SQL — no explanation."
)


def make_agentic_recover(llm: ChatOllama, retriever: SchemaRetriever, all_tables: list[TableSchema]):
    """Return an agentic_recover node with tools closed over the retriever and full schema."""

    schema_map: dict[str, TableSchema] = {t.name: t for t in all_tables}

    # --- Tool definitions (closures over retriever / schema_map) ---

    @tool
    def search_tables(query: str) -> str:
        """Search for relevant table names by semantic similarity. Returns top-5 table names."""
        logger.info("[agentic] tool=search_tables query=%r", query)
        results = retriever.retrieve(query, top_k=5)
        names = [schema.name for schema, _ in results]
        logger.info("[agentic] search_tables → %s", names)
        return f"Relevant tables: {', '.join(names)}"

    @tool
    def get_table_schemas(table_names: list[str]) -> str:
        """Get full schema (columns + description) for all requested tables in one call."""
        logger.info("[agentic] tool=get_table_schemas tables=%s", table_names)
        parts = []
        for name in table_names:
            if name in schema_map:
                parts.append(schema_map[name].to_text())
            else:
                parts.append(f"Table '{name}' not found in schema.")
        return "\n\n".join(parts)

    @tool
    def validate_sql(sql: str) -> str:
        """
        Validate SQL syntax and verify all tables/columns exist in the schema.
        Returns 'valid' or an error message describing the problem.
        """
        logger.info("[agentic] tool=validate_sql sql=%r", sql)
        try:
            ast = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
        except sqlglot.errors.ParseError as exc:
            result = f"Syntax error: {exc}"
            logger.warning("[agentic] validate_sql → %s", result)
            return result

        if not isinstance(ast, exp.Select):
            result = "Only SELECT statements are allowed."
            logger.warning("[agentic] validate_sql → %s", result)
            return result

        for table_node in ast.find_all(exp.Table):
            if table_node.name and table_node.name not in schema_map:
                result = f"Unknown table: {table_node.name}"
                logger.warning("[agentic] validate_sql → %s", result)
                return result

        for col_node in ast.find_all(exp.Column):
            qualifier = col_node.table
            col_name = col_node.name
            if qualifier and qualifier in schema_map and col_name and col_name != "*":
                known = {c.name.lower() for c in schema_map[qualifier].columns}
                if col_name.lower() not in known:
                    result = f"Unknown column: {qualifier}.{col_name}"
                    logger.warning("[agentic] validate_sql → %s", result)
                    return result

        logger.info("[agentic] validate_sql → valid")
        return "valid"

    tools = [search_tables, get_table_schemas, validate_sql]
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    # --- Node function ---

    def agentic_recover(state: AgentState) -> dict:
        error = state.get("previous_error") or state.get("validation_error")
        logger.info("[agentic_recover] starting — previous_error=%r", error)

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Question: {state['question']}\n\n"
                f"Previous validation error: {error}"
            )),
        ]

        react_steps = 0
        fetched_tables: list[TableSchema] = []
        last_sql = state.get("sql", "")

        while react_steps < MAX_REACT_STEPS:
            logger.info("[agentic_recover] ReAct step %d — calling LLM ...", react_steps + 1)
            # print(messages)
            response = llm_with_tools.invoke(messages)
            # print("✅✅✅✅ response✅✅✅" , response)
            messages.append(response)

            # No tool calls → LLM emitted its final answer (the SQL).
            if not response.tool_calls:
                sql = _FENCE_RE.sub("", response.content).strip()
                if sql:
                    last_sql = sql
                    logger.info("[agentic_recover] LLM emitted final SQL:\n%s", sql)
                else:
                    logger.warning("[agentic_recover] LLM emitted empty response, keeping previous SQL")
                break

            # Execute every tool call in this turn.
            for tool_call in response.tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]

                result = tool_map[name].invoke(args)
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
                react_steps += 1

                # Track tables fetched so validate node has schema context.
                if name == "get_table_schemas":
                    for tbl_name in args.get("table_names", []):
                        if tbl_name in schema_map and schema_map[tbl_name] not in fetched_tables:
                            fetched_tables.append(schema_map[tbl_name])

                if react_steps >= MAX_REACT_STEPS:
                    logger.warning("[agentic_recover] hit MAX_REACT_STEPS=%d — stopping", MAX_REACT_STEPS)
                    break

        logger.info("[agentic_recover] done — react_steps=%d final_sql=%r", react_steps, last_sql[:80] if last_sql else "")
        return {
            "sql":              last_sql,
            "tables":           fetched_tables or state.get("tables", []),
            "react_steps":      react_steps,
            "validation_error": None,   # agentic validated internally — clear the old error
        }

    return agentic_recover
