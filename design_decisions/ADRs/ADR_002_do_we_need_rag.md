# ADR-002: Do We Need RAG Here?

## Status

Accepted

---

## Context

We have 8 tables(for now, it can be any number) with metadata. The agent needs to know which tables are relevant to answer a user's question before generating SQL. The question is: should we just pass all table schemas to the LLM every time, or use RAG to retrieve only the relevant ones?

## Decision

- **Use RAG — scoped to schema/table retrieval only.**

## Rationale

**Option A: Dump all schemas into every prompt.**

- This is the right approach to go with for the current schema and table information. -> but in future there can be any number of tables -> that might not fit in the "context window" -> **its just gonna bloat the prompt**.
- Works today with 8 tables — they fit in context.
- But irrelevant tables in the prompt confuse the LLM and lead to hallucinated joins.
- Doesn't scale — real customer service DBs have more than this number -> 50-100+ tables.
- Scores poorly on evaluation criterion #2: "Effective use of retrieval methods, embeddings, LLMs."

**Option B: RAG over table metadata (chosen).**

- Embed each table's metadata (name + columns + descriptions) as one unit at startup.
- On each question, retrieve top-k most semantically similar tables via cosine similarity.
- Only the relevant tables go into the prompt → cleaner SQL, fewer hallucinated joins.
- Demonstrates retrieval understanding as required by the assignment.

**What we are NOT doing:** RAG over row-level data. The assignment says output is a SQL query — no data processing needed. Retrieval is purely at the schema level.

## RAG Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` (sentence-transformers) | Small, fast, CPU-only, strong semantic similarity for short text. |
| Vector store | In-memory numpy cosine similarity | 8 tables — no need for ChromaDB/FAISS overhead. Simple dict + numpy is sufficient. even for 100s of tables also dont need FAISS. |
| Chunking unit | One chunk per table | Table is the unit of retrieval. Splitting by column would lose context. |
| Retrieval method | Cosine similarity | Standard for semantic search; effective for matching NL questions to schema descriptions. |
| Top-k | 4 tables | Covers complex 3-4 table joins without bloating the prompt. |
| Index built | Once at startup | Schema is static, not gonna change often — no need to re-embed on every request. |


## trade off 
- Since the tables are lesss, we are going for numby search basically a KNN apporach. This might not be suitable for the big enterprise having 5000+ tables. -> there we need to switch to some vectore DB. 
- If we think the schema will change frequently, **We need a re-indexing mechanisum**
- But for now we dont need it assumpes is the schema is static.
- If the retrival fails to get the SQL right in the first go, will ask the LLM to choose the needed tables in a call. -> need to be decided.