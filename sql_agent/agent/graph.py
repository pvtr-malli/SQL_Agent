import time

from langgraph.graph import END, StateGraph
from langchain_ollama import ChatOllama

from sql_agent.agent.edges.should_retry import retry_prep, should_retry
from sql_agent.agent.nodes.agentic_recover import make_agentic_recover
from sql_agent.agent.nodes.cache_check import make_cache_check, route_cache
from sql_agent.agent.nodes.generate import make_generate
from sql_agent.agent.nodes.inject_check import inject_check, route_inject
from sql_agent.agent.nodes.retrieve import make_retrieve
from sql_agent.agent.nodes.validate import validate
from sql_agent.agent.state import AgentState
from sql_agent.config.settings import LLM_MODEL, LLM_TEMPERATURE, OLLAMA_BASE_URL
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.utils.cache import QueryCache


def build_graph(retriever: SchemaRetriever, cache: QueryCache):
    """
    Compile and return the LangGraph for the full agent pipeline:
    attempts 1 & 2 (deterministic) + attempt 3 (ReAct agentic recovery).
    """
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
    )

    g = StateGraph(AgentState)

    # --- Nodes ---
    g.add_node("cache_check",     make_cache_check(cache))
    g.add_node("inject_check",    inject_check)
    g.add_node("retrieve",        make_retrieve(retriever))
    g.add_node("generate",        make_generate(llm))
    g.add_node("validate",        validate)
    g.add_node("retry_prep",      retry_prep)
    g.add_node("agentic_recover", make_agentic_recover(llm, retriever, retriever.tables))

    # --- Edges ---
    g.set_entry_point("cache_check")

    g.add_conditional_edges("cache_check", route_cache, {
        "hit":  END,
        "miss": "inject_check",
    })
    g.add_conditional_edges("inject_check", route_inject, {
        "clean":     "retrieve",
        "injection": END,
    })

    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "validate")

    g.add_conditional_edges("validate", should_retry, {
        "success": END,
        "failure": END,
        "retry":   "retry_prep",
        "agentic": "agentic_recover",
    })

    g.add_edge("retry_prep",      "retrieve")
    g.add_edge("agentic_recover", END)

    return g.compile()


def run_query(
    question: str,
    retriever: SchemaRetriever,
    cache: QueryCache,
    graph=None,
) -> dict:
    """
    Run the agent graph for a question and return a plain result dict.

    Returns:
      {
        "status_code": int,           # 200 | 400 | 422
        "sql":         str | None,
        "error":       str | None,
        "cache_hit":   bool,
        "attempts":    int,
        "tables_used": list[str],
        "latency_ms":  float,
      }
    """
    if graph is None:
        graph = build_graph(retriever, cache)

    initial: AgentState = {
        "question":        question,
        "cache_hit":       False,
        "attempt":         1,
        "tables":          [],
        "sql":             "",
        "validation_error": None,
        "previous_error":  None,
        "tables_used":     [],
        "latency_ms":      0.0,
        "react_steps":     0,
        "status_code":     0,
        "error_message":   None,
        "rag_ms":          0.0,
        "llm_ms":          0.0,
        "validate_ms":     0.0,
        "agentic_ms":      0.0,
    }

    t0 = time.perf_counter()
    final: AgentState = graph.invoke(initial)
    latency_ms = (time.perf_counter() - t0) * 1000

    # Determine final status from state if not already set by a node.
    status_code = final.get("status_code") or 0
    if status_code == 0:
        status_code = 200 if final.get("validation_error") is None else 422

    # Write to cache on clean success that wasn't already a cache hit.
    if status_code == 200 and not final.get("cache_hit") and final.get("sql"):
        cache.set(question, final["sql"])

    return {
        "status_code": status_code,
        "sql":         final.get("sql") or None,
        "error":       final.get("error_message") or final.get("validation_error"),
        "cache_hit":   final.get("cache_hit", False),
        "attempts":    final.get("attempt", 1),
        "tables_used": final.get("tables_used", []),
        "latency_ms":  round(latency_ms, 2),
        "rag_ms":      round(final.get("rag_ms", 0.0), 2),
        "llm_ms":      round(final.get("llm_ms", 0.0), 2),
        "validate_ms": round(final.get("validate_ms", 0.0), 2),
        "agentic_ms":  round(final.get("agentic_ms", 0.0), 2),
        "react_steps": final.get("react_steps", 0),
    }


if __name__ == "__main__":
    import sys
    from sql_agent.config.settings import CACHE_FILE, INDEX_STORE, XLSX_PATH
    from sql_agent.indexing.retriever import SchemaRetriever
    from sql_agent.utils.cache import QueryCache
    from sql_agent.utils.schema_loader import load_schema

    retriever = SchemaRetriever()
    if not retriever.load(INDEX_STORE):
        print(f"No saved index found — building from {XLSX_PATH} ...")
        tables = load_schema(XLSX_PATH)
        retriever.build_index(tables)
        retriever.save(INDEX_STORE)
    print(f"Index ready — {retriever.table_count} tables")

    cache = QueryCache(CACHE_FILE)
    graph = build_graph(retriever, cache)

    question = " ".join(sys.argv[1:]) or "How many tickets were opened last week?"
    print(f"\nQuestion: {question}\n")

    result = run_query(question, retriever, cache, graph)

    print(result)

    print(f"Status   : {result['status_code']}")
    print(f"Cache hit: {result['cache_hit']}")
    print(f"Attempts : {result['attempts']}")
    print(f"Latency  : {result['latency_ms']} ms")
    print(f"Tables   : {result['tables_used']}")
    if result["sql"]:
        print(f"\nSQL:\n{result['sql']}")
    if result["error"]:
        print(f"\nError: {result['error']}")

    # if result["error"]:
    #     print(f"\nError: {result['error']}")
