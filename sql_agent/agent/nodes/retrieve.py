import time
from typing import Optional

from sql_agent.agent.state import AgentState
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.kg.expander import KGExpander
from sql_agent.utils.logger import get_logger
from sql_agent.utils.metrics import LOW_SCORE_THRESHOLD

logger = get_logger(__name__)


def make_retrieve(retriever: SchemaRetriever, expander: Optional[KGExpander] = None):
    """Return a retrieve node bound to the given SchemaRetriever (and optional KGExpander)."""

    def retrieve(state: AgentState) -> dict:
        attempt = state["attempt"]
        # Attempt 1 → narrow retrieval; attempt 2 → wider net.
        top_k = 4 if attempt == 1 else 6
        logger.info("[retrieve] attempt=%d top_k=%d", attempt, top_k)

        t0 = time.perf_counter()
        results = retriever.retrieve(state["question"], top_k=top_k)
        rag_elapsed = (time.perf_counter() - t0) * 1000

        tables = [schema for schema, _ in results]
        top_score = results[0][1] if results else 0.0
        scores = [round(s, 3) for _, s in results]

        logger.info("[retrieve] vector tables: %s scores=%s", [t.name for t in tables], scores)

        if top_score < LOW_SCORE_THRESHOLD:
            logger.warning(
                "[retrieve] LOW RETRIEVAL SCORE — top=%.3f (threshold=%.2f) "
                "question=%r — retrieval quality may have degraded",
                top_score, LOW_SCORE_THRESHOLD, state["question"],
            )

        # KG expansion: find FK-neighbour tables not already in the vector results.
        kg_expanded: list[str] = []
        if expander is not None:
            seed_names = [t.name for t in tables]
            neighbor_names = expander.expand(seed_names)

            # Look up full TableSchema objects for each KG neighbour.
            all_tables = {t.name: t for t in retriever.tables}
            for name in neighbor_names:
                if name in all_tables:
                    tables.append(all_tables[name])
                    kg_expanded.append(name)

            if kg_expanded:
                logger.info("[retrieve] KG expanded: %s", kg_expanded)

        return {
            "tables":              tables,
            "kg_expanded":         kg_expanded,
            "rag_ms":              state.get("rag_ms", 0.0) + rag_elapsed,
            "retrieval_top_score": top_score,
        }

    return retrieve


if __name__ == "__main__":
    from sql_agent.config.settings import INDEX_STORE
    from sql_agent.kg.connection import get_driver

    retriever = SchemaRetriever()
    retriever.load(INDEX_STORE)

    driver = get_driver()
    expander = KGExpander(driver)
    retrieve_fn = make_retrieve(retriever, expander)

    questions = [
        ("Which agents had the most escalations last week?",  1),
        ("Which agents had the most escalations last week?",  2),  # attempt 2 → top_k=6
        ("Show me CSAT scores for premium customers",         1),
        ("How much money did premium customers spend?",       1),  # low-score case
    ]

    for question, attempt in questions:
        state = {"question": question, "attempt": attempt, "rag_ms": 0.0}
        result = retrieve_fn(state)

        vector_count = len(result["tables"]) - len(result["kg_expanded"])
        print(f"Q (attempt {attempt}): {question}")
        print(f"  top_score  : {result['retrieval_top_score']:.3f}")
        print(f"  vector     : {[t.name for t in result['tables'][:vector_count]]}")
        print(f"  kg_expanded: {result['kg_expanded']}")
        print(f"  all tables : {[t.name for t in result['tables']]}")
        print(f"  rag_ms     : {result['rag_ms']:.1f}")
        print()

    driver.close()
