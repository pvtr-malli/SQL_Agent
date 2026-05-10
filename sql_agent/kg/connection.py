from neo4j import GraphDatabase

from sql_agent.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def get_driver():
    """Return a Neo4j driver using settings from env / settings.py."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def verify_connection(driver) -> bool:
    """Return True if the driver can reach Neo4j, False otherwise."""
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return True
    except Exception:
        return False
