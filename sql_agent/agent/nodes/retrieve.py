from sql_agent.agent.state import AgentState
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.utils.logger import get_logger

logger = get_logger(__name__)


def make_retrieve(retriever: SchemaRetriever):
    """Return a retrieve node bound to the given SchemaRetriever instance."""

    def retrieve(state: AgentState) -> dict:
        attempt = state["attempt"]
        # Attempt 1 → narrow retrieval; attempt 2 → wider net.
        top_k = 4 if attempt == 1 else 6
        logger.info("[retrieve] attempt=%d top_k=%d", attempt, top_k)
        results = retriever.retrieve(state["question"], top_k=top_k)
        tables = [schema for schema, _ in results]
        logger.info("[retrieve] retrieved tables: %s", [t.name for t in tables])
        return {"tables": tables}

    return retrieve
