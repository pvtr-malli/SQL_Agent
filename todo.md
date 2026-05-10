- [x] List the decisions to make
- [x] Makes the ADRs -> give the reasong why yo uchose it
- [x] How many API requests you will have ? -> api design doc
- [x] Prompt injection ways and methods to prevent
- [x] Finish the initial desing
- [x] Fake data and the excel file generation
- [ ] Choose the LLM model using some validation method. -> No time picked the well performing decoder one.
- [x] Do the finsih the indexing pipeipline with the API calls 
- [x] rertrival and its checks -> should work fine
- [x] lang graph nodes and structure flow - decide this
    - [x] code the deteministic part
    - [x] code the agentic part
- [ ] Check the whole flow 
- [x] Do the latency check  -> latency is fine even with the llm calls, its < 20s. 
- [x] Small UI 
- [x] Invlove Docker if needed - not needed mostly  -> not added, here docker is simply a over-engineering. but can be added not a big deal.
- [x] Chekc the final desing    
    - [x] code changed to use try 1 & 2 is deterministic and try 3 is fully agentic (LLM decides what to do 
    next)
    - [x] Deployment Architecture for Production
- [x] Make readme
- [x] Deployment Architecture for Production
- [ ] Monitoring and basic observability hook,


Step-by-Step: Adding Neo4j as Secondary Retrieval
Step 1 — Map the FK graph by hand (no code)
Before writing anything, understand what the graph looks like. From tables.json, the FK edges are:


customers_tbl ←── tickets_tbl ──→ agents_tbl
                       │               ↑
                       ↓               │
               interactions_tbl ───────┘
                       
tickets_tbl ←── ticket_products_tbl ──→ products_tbl
tickets_tbl ←── feedback_tbl ──→ customers_tbl
tickets_tbl ←── escalations_tbl ──→ agents_tbl (x2: from/to)
categories_tbl ←── tickets_tbl
What you'll learn here: tickets_tbl is the hub — almost everything joins through it. This is exactly the structural knowledge vector search doesn't have. If someone asks about "product complaints", vector finds feedback_tbl but misses that you need tickets_tbl → ticket_products_tbl → products_tbl to get product names.

Step 2 — Install Neo4j and verify the Python connection
Run Neo4j locally via Docker and write a 10-line connection test.

What you'll learn: How Neo4j talks to Python via the neo4j driver (Bolt protocol), credentials, and session lifecycle.

Step 3 — Design the Cypher node/relationship model
Decide on the graph schema before writing ingestion code:


(:Table {name, description})
(:Column {name, data_type, nullable, description})

(:Table)-[:HAS_COLUMN]->(:Column)
(:Column)-[:REFERENCES]->(:Column)          ← FK edge
(:Table)-[:JOINS_WITH {via_column}]->(:Table)  ← derived, easier to query
What you'll learn: The difference between a property graph (Neo4j's model) and a relational schema. You'll also see why we keep both REFERENCES (precise, column-level) and JOINS_WITH (convenient, table-level) — they serve different queries.

Step 4 — Write the schema-to-graph ingestion
Parse the FK strings from tables.json (e.g. "FK -> tickets_tbl.ticket_id") and run Cypher MERGE statements to build the graph.

What you'll learn: Cypher MERGE (like upsert — creates if not exists), how to parse FK strings, and the ingestion pattern that POST /index will call.

Step 5 — Write KGExpander
A single class with one method: expand(seed_table_names) → set[str]. Runs a Cypher traversal query to find tables reachable in 1–2 hops via JOINS_WITH.


MATCH (t:Table)-[:JOINS_WITH*1..2]-(neighbor:Table)
WHERE t.name IN $seed_tables
RETURN DISTINCT neighbor.name AS name
What you'll learn: Variable-length path patterns (*1..2), DISTINCT, and why 2 hops is the right limit (3 hops from escalations_tbl would pull in everything).

Step 6 — Wire KGExpander into the retrieve node
The retrieve node currently returns top-k by cosine. After this step it returns: union(vector_results, kg_expanded_neighbors). The LLM gets a richer schema with JOIN partners included.

What you'll learn: How the two retrieval signals combine — vector gives semantic relevance, KG gives structural completeness. You'll see this in action by comparing /retrieve output before and after.

Step 7 — Update POST /index to also populate Neo4j
Currently /index only rebuilds the numpy vector index. After this step it also calls the ingestion from Step 4 — so one API call keeps both stores in sync.

What you'll learn: Why index consistency matters — if Neo4j has stale edges when the vector index has new tables, the KG expansion gives wrong results.

Step 8 — Update GET /retrieve response
Add a kg_expanded field so you can inspect what the KG added on top of vector search:


{
  "question": "Which products had the most complaints?",
  "tables": [...],
  "kg_expanded": ["tickets_tbl", "ticket_products_tbl"],
  "retrieval_latency_ms": 22.1
}
What you'll learn: How to use this for debugging — if KG expansion is pulling in tables that don't make sense, the FK relationships in tables.json need fixing.

Ready to start with Step 1 — want me to draw the full FK graph as a Mermaid diagram so you can see it clearly before we touch any code?