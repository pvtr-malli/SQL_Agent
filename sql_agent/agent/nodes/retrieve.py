from sql_agent.agent.state import AgentState
from sql_agent.indexing.retriever import SchemaRetriever


def make_retrieve(retriever: SchemaRetriever):
    """Return a retrieve node bound to the given SchemaRetriever instance."""

    def retrieve(state: AgentState) -> dict:
        attempt = state["attempt"]
        # Attempt 1 → narrow retrieval; attempt 2 → wider net.
        top_k = 4 if attempt == 1 else 6
        results = retriever.retrieve(state["question"], top_k=top_k)
        tables = [schema for schema, _ in results]
        return {"tables": tables}

    return retrieve
