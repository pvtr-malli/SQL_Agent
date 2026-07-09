from neo4j import Driver

from sql_agent.config.models import TableSchema


def _parse_fk(rel: str | None) -> tuple[str, str] | None:
    """
    Parse a FK relationship string into (target_table, target_column).

    Input:  "FK -> tickets_tbl.ticket_id"
    Output: ("tickets_tbl", "ticket_id")

    Returns None for PK markers or empty values.
    """
    if not rel or not rel.startswith("FK ->"):
        return None
    target = rel.split("->", 1)[1].strip()
    parts = target.split(".")
    if len(parts) != 2:
        return None
    return parts[0].strip(), parts[1].strip()


def clear_graph(driver: Driver) -> None:
    """Delete every node and relationship in the database."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


def ingest_schema(driver: Driver, tables: list[TableSchema]) -> None:
    """
    Populate Neo4j from a list of TableSchema objects.

    What gets created:
      (:Table)                      — one node per table
      (:Column)                     — one node per column
      (:Table)-[:HAS_COLUMN]->(:Column)
      (:Column)-[:REFERENCES]->(:Column)   FK edge at column level
      (:Table)-[:JOINS_WITH]->(:Table)     derived join edge at table level (bidirectional)

    MERGE is used throughout so re-running is safe (idempotent).
    """
    with driver.session() as session:

        # --- Pass 1: nodes and HAS_COLUMN edges ---
        # Do this first so all nodes exist before we try to link them with FK edges.
        for table in tables:
            session.run(
                """
                MERGE (t:Table {name: $name})
                SET t.description = $description
                """,
                name=table.name,
                description=table.description,
            )

            for col in table.columns:
                # Column identity = (table_name, col_name) — same col name can appear in multiple tables.
                session.run(
                    """
                    MERGE (c:Column {table_name: $table_name, name: $col_name})
                    SET c.data_type   = $data_type,
                        c.nullable    = $nullable,
                        c.description = $description
                    WITH c
                    MATCH (t:Table {name: $table_name})
                    MERGE (t)-[:HAS_COLUMN]->(c)
                    """,
                    table_name=table.name,
                    col_name=col.name,
                    data_type=col.data_type,
                    nullable=col.nullable,
                    description=col.description,
                )

        # --- Pass 2: FK edges ---
        # Separate pass because both sides of the FK must already exist as nodes.
        for table in tables:
            for col in table.columns:
                fk = _parse_fk(col.relationships)
                if fk is None:
                    continue
                tgt_table, tgt_col = fk

                # Column-level: precise "this column points to that column"
                session.run(
                    """
                    MATCH (src:Column {table_name: $src_table, name: $src_col})
                    MATCH (tgt:Column {table_name: $tgt_table, name: $tgt_col})
                    MERGE (src)-[:REFERENCES]->(tgt)
                    """,
                    src_table=table.name,
                    src_col=col.name,
                    tgt_table=tgt_table,
                    tgt_col=tgt_col,
                )

                # Table-level: bidirectional so traversal works from either side.
                # e.g. escalations_tbl <--> agents_tbl via agent_id
                session.run(
                    """
                    MATCH (src:Table {name: $src_table})
                    MATCH (tgt:Table {name: $tgt_table})
                    MERGE (src)-[:JOINS_WITH {via: $via}]->(tgt)
                    MERGE (tgt)-[:JOINS_WITH {via: $via}]->(src)
                    """,
                    src_table=table.name,
                    tgt_table=tgt_table,
                    via=col.name,
                )
