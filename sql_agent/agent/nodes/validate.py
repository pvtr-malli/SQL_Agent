import sqlglot
import sqlglot.expressions as exp

from sql_agent.agent.state import AgentState

# Statement types that are never allowed (SELECT-only allowlist, ADR-006 Layer 2).
_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,  # covers EXEC / arbitrary commands
)


def validate(state: AgentState) -> dict:
    sql = state["sql"].strip()
    tables = state["tables"]

    if not sql:
        return {"validation_error": "LLM returned an empty response."}

    # --- Layer 1: syntax check via sqlglot ---
    try:
        ast = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as exc:
        return {"validation_error": f"Syntax error: {exc}"}

    # --- Layer 2: SELECT-only allowlist ---
    if isinstance(ast, _FORBIDDEN):
        return {"validation_error": "Only SELECT statements are allowed."}
    if not isinstance(ast, exp.Select):
        return {"validation_error": "Only SELECT statements are allowed."}

    # --- Layer 3: table existence check ---
    schema_map: dict[str, set[str]] = {
        t.name.lower(): {c.name.lower() for c in t.columns} for t in tables
    }

    referenced_tables: list[str] = []
    for table_node in ast.find_all(exp.Table):
        name = table_node.name
        if not name:
            continue
        if name.lower() not in schema_map:
            return {"validation_error": f"Unknown table: {name}"}
        referenced_tables.append(name)

    # --- Layer 4: qualified column check (table.column only) ---
    # Unqualified columns are skipped to avoid false positives from aliases.
    for col_node in ast.find_all(exp.Column):
        qualifier = col_node.table
        col_name = col_node.name
        if not qualifier or not col_name or col_name == "*":
            continue
        if qualifier.lower() in schema_map:
            if col_name.lower() not in schema_map[qualifier.lower()]:
                return {
                    "validation_error": f"Unknown column: {qualifier}.{col_name}"
                }

    return {"validation_error": None, "tables_used": referenced_tables}
