from neo4j import Driver

from sql_agent.utils.logger import get_logger

logger = get_logger(__name__)


class KGExpander:
    """
    Expands a set of seed tables (from vector search) by traversing
    JOINS_WITH edges in Neo4j to find tables that are reachable via FK paths.

    Why this matters:
      Vector search finds semantically similar tables.
      KGExpander finds tables you *must* JOIN to answer the question —
      even if those tables aren't mentioned in the question text.

    Example:
      seed = ["escalations_tbl"]
      expand() → {"tickets_tbl", "agents_tbl"}
      because escalations_tbl joins to both via FK columns.
    """

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    def expand(self, seed_tables: list[str], hops: int = 2) -> set[str]:
        """
        Return table names reachable from seed_tables within `hops` JOINS_WITH steps,
        excluding the seed tables themselves (they're already in the retrieval result).

        hops=1  → only direct FK neighbours
        hops=2  → neighbours of neighbours (default — covers most multi-join queries)

        Falls back to empty set if Neo4j is unreachable so vector search still works.
        """
        if not seed_tables:
            return set()

        try:
            with self._driver.session() as session:
                result = session.run(
                    f"""
                    MATCH (t:Table)-[:JOINS_WITH*1..{hops}]-(neighbor:Table)
                    WHERE t.name IN $seed_tables
                    AND NOT neighbor.name IN $seed_tables
                    RETURN DISTINCT neighbor.name AS name
                    """,
                    seed_tables=seed_tables,
                )
                neighbors = {record["name"] for record in result}

            logger.debug(
                "KGExpander: seed=%s hops=%d → expanded=%s",
                seed_tables, hops, sorted(neighbors),
            )
            return neighbors

        except Exception as exc:
            logger.warning("KGExpander: Neo4j unavailable, skipping expansion (%s)", exc)
            return set()
