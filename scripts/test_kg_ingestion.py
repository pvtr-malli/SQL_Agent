"""
Run this script to:
  1. Verify the Neo4j connection works
  2. Push the full schema (tables, columns, FK edges) into Neo4j
  3. Print a summary of what was created

Before running, make sure:
  - Neo4j Desktop DBMS is started
  - NEO4J_PASSWORD env var matches what you set in Desktop (or edit settings.py default)

Run:
    NEO4J_PASSWORD=your_password uv run python scripts/test_kg_ingestion.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_agent.kg.connection import get_driver, verify_connection
from sql_agent.kg.ingestion import clear_graph, ingest_schema
from sql_agent.utils.schema_loader import load_schema
from sql_agent.config.settings import XLSX_PATH

driver = get_driver()

print("Checking Neo4j connection...")
if not verify_connection(driver):
    print("ERROR: Cannot connect to Neo4j. Is the DBMS running in Desktop?")
    print(f"  URI:  {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")
    print(f"  User: {os.getenv('NEO4J_USER', 'neo4j')}")
    sys.exit(1)

print("Connected.\n")

print("Loading schema from Excel...")
tables = load_schema(XLSX_PATH)
print(f"  {len(tables)} tables loaded\n")

print("Clearing existing graph...")
clear_graph(driver)
print("  Done.\n")

print("Ingesting schema into Neo4j...")
ingest_schema(driver, tables)
print("  Done.\n")

# Summary query — count what we created
with driver.session() as session:
    table_count  = session.run("MATCH (t:Table) RETURN count(t) AS n").single()["n"]
    col_count    = session.run("MATCH (c:Column) RETURN count(c) AS n").single()["n"]
    fk_count     = session.run("MATCH ()-[:REFERENCES]->() RETURN count(*) AS n").single()["n"]
    join_count   = session.run("MATCH ()-[:JOINS_WITH]->() RETURN count(*) AS n").single()["n"]

print("Graph summary:")
print(f"  Table nodes   : {table_count}")
print(f"  Column nodes  : {col_count}")
print(f"  REFERENCES    : {fk_count}  (column → column FK edges)")
print(f"  JOINS_WITH    : {join_count}  (table ↔ table, bidirectional)")
print()
print("Open Neo4j Browser and run:  MATCH (n) RETURN n")
print("You should see all tables and columns connected by edges.")

driver.close()
