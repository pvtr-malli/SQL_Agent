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
from sql_agent.config.settings import INDEX_STORE, TOP_K_DEFAULT, XLSX_PATH

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# Single retriever instance shared across all requests.
retriever = SchemaRetriever()


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
def query(_: QueryRequest):
    """
    Generate SQL for a natural language question.
    Full agent loop (RAG → generate → validate → retry) — coming in next phase.
    """
    raise HTTPException(status_code=501, detail="Not implemented yet.")
