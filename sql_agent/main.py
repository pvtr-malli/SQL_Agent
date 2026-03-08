import logging
import time

from fastapi import FastAPI, HTTPException, Query

from sql_agent.config.models import (
    IndexResponse,
    QueryRequest,
    RetrievedTable,
    RetrieveResponse,
)
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.utils.schema_loader import load_schema
from sql_agent.config.settings import CACHE_FILE, INDEX_STORE, TOP_K_DEFAULT, XLSX_PATH
from sql_agent.agent.graph import build_graph, run_query
from sql_agent.utils.cache import QueryCache

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# Singletons shared across all requests.
retriever = SchemaRetriever()
cache = QueryCache(CACHE_FILE)
graph = None  # built lazily on first /query call (requires index to be ready)


app = FastAPI(title="SQL Agent")


@app.post("/index", response_model=IndexResponse)
def reindex() -> IndexResponse:
    """
    Build (or rebuild) the vector index from the schema file and persist it to disk.
    Call this once before using /retrieve or /query, and again whenever the schema changes.
    """
    t0 = time.perf_counter()
    logger.info("POST /index — building index from %s", XLSX_PATH)

    tables = load_schema(XLSX_PATH)
    embed_latency_ms = retriever.build_index(tables)
    retriever.save(INDEX_STORE)
    total_latency_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "POST /index — indexed %d tables | embed=%.1f ms | total=%.1f ms | saved to %s",
        retriever.table_count,
        embed_latency_ms,
        total_latency_ms,
        INDEX_STORE,
    )
    return IndexResponse(
        status="ok",
        tables_indexed=retriever.table_count,
        latency_ms=round(total_latency_ms, 2),
    )


@app.get("/retrieve", response_model=RetrieveResponse)
def retrieve_tables(
    question: str = Query(..., min_length=1, max_length=1000),
) -> RetrieveResponse:
    """
    Return the top-k tables the RAG retriever would select for a given question.
    No LLM call is made — useful for debugging retrieval quality.
    """
    if not retriever.is_ready:
        raise HTTPException(status_code=503, detail="Index is empty. Call POST /index first.")

    logger.info("GET /retrieve — question=%r", question)

    t0 = time.perf_counter()
    results = retriever.retrieve(question, top_k=TOP_K_DEFAULT)
    retrieval_latency_ms = (time.perf_counter() - t0) * 1000

    tables = [
        RetrievedTable(
            name=schema.name,
            score=round(score, 4),
            columns=[col.name for col in schema.columns],
        )
        for schema, score in results
    ]

    logger.info(
        "GET /retrieve — returned %d tables in %.1f ms: %s",
        len(tables),
        retrieval_latency_ms,
        [t.name for t in tables],
    )
    return RetrieveResponse(
        question=question,
        tables=tables,
        top_k=TOP_K_DEFAULT,
        retrieval_latency_ms=round(retrieval_latency_ms, 2),
    )


@app.post("/query")
def query(req: QueryRequest):
    """
    Generate SQL for a natural language question.
    Runs the full agent loop: cache check → injection check → RAG → generate → validate → retry.
    """
    global graph

    if not retriever.is_ready:
        raise HTTPException(status_code=503, detail="Index is empty. Call POST /index first.")

    if graph is None:
        graph = build_graph(retriever, cache)

    logger.info("POST /query — question=%r", req.question)

    result = run_query(req.question, retriever, cache, graph)

    logger.info(
        "POST /query — status=%d cache_hit=%s attempts=%d latency=%.1f ms",
        result["status_code"],
        result["cache_hit"],
        result["attempts"],
        result["latency_ms"],
    )

    if result["status_code"] == 400:
        raise HTTPException(status_code=400, detail=result["error"])
    if result["status_code"] == 422:
        raise HTTPException(status_code=422, detail={
            "error": result["error"],
            "last_sql": result["sql"],
        })

    return {
        "sql":         result["sql"],
        "cache_hit":   result["cache_hit"],
        "attempts":    result["attempts"],
        "tables_used": result["tables_used"],
        "latency_ms":  result["latency_ms"],
    }


@app.delete("/cache")
def clear_cache():
    """
    Clear all cached query → SQL entries.
    Call this when the schema changes so stale SQL is not served from cache.
    """
    cleared = cache.clear()
    logger.info("DELETE /cache — cleared %d entries", cleared)
    return {"status": "ok", "entries_cleared": cleared}
