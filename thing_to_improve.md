# 1 | Assumptions:
- The data and assumped we will be having <100 tables.
- And only one Excel will be taken, all the tables and tables informations will be present inside one excel.
- Table metadata and the Excel file are in English (embedding model and prompts are English-centric).
- A single Excel file is used as the schema source; all tables and their column information are present in one sheet named `Table Metadata`.
- The Excel sheet has the fixed columns: `Table Name`, `Column Name`, `Data Type`, `Nullable`, `Description`, `Relationships`.
- Table names are unique across the schema (no two tables share the same name).
- The schema is static at runtime — no live table additions or modifications while the server is running (re-indexing requires a restart or an explicit `/index` call).
- User questions are in English and are well-formed natural language (max 1,000 characters).
- The system runs as a single instance — the file-backed cache is not safe for concurrent multi-process writes.
- The top-k retrieved table schemas fit within the LLM's context window (schema text is not truncated before being sent to the LLM).
- Only SELECT queries are generated, to protect the system from the prompt injectins.


# 2 | Limitations:
- No ANN retrival, so with bigger tables it will be slower.
- No re-indexing methods -> if you want you have to re-run from beginning. Slower
- **Cache**: Is based on plain text match, even a single charater change in question will not hit the cache. 
    - Need to setup the radis and setup for better cache machanisum (sematic-query-cache)
    - No TTL implemented for now, Need to delete the cache manually if needed.
    - LRU eviction is not implemented — cache grows unbounded
- Blocklist is regex-based — creative rephrasing or obfuscation can bypass it (e.g. mixed case, Unicode lookalikes)
- Top-k is fixed at 4 (attempt 1) / 6 (attempt 2) — no dynamic sizing based on query complexity
- MAX_REACT_STEPS=8 tool calls total, not per tool type — a poorly behaving LLM can exhaust steps without making progress (I accept to fail, because more API calls are wast of time and cost.)


# Improvements I can make:

### 1. Prompt Injection Hardening
- Currently only SELECT queries are allowed via a blocklist + SELECT-only validator.
- Needs deeper analysis: enumerate additional injection vectors (e.g. comment-based bypasses, UNION injections, nested subquery abuse) and design mitigations specific to each.

### 2. ANN / Vector DB Retrieval
- The current retriever uses an in-memory NumPy cosine search, which scales linearly with the number of tables.
- If the table count grows significantly (>100), migrate to an ANN (Approximate Nearest Neighbour) index such as FAISS or a dedicated vector database for sub-linear retrieval.

### 3. Incremental Re-indexing
- Currently re-indexing requires rebuilding the entire index from scratch.
- A more efficient approach would be incremental re-indexing: detect which tables have changed in the schema source and only re-embed and update those entries, leaving unchanged tables untouched.

### 4. Model Selection & Evaluation
- A systematic evaluation is needed to identify which LLM performs best for SQL generation on this schema.
- This requires generating a ground-truth (GT) SQL dataset for the target questions and running automated accuracy benchmarks across candidate models.

### 5. Prompt Tuning
- Experiment with few-shot examples, chain-of-thought hints, and schema formatting variations in the LLM prompts to improve first-attempt SQL accuracy and reduce how often the retry or agentic path is needed.

### 6. Semantic Query Cache
- The current cache uses exact normalised-text matching, so any minor rephrasing of a question results in a cache miss.
- A semantic cache (e.g. embedding the question and retrieving cached results by cosine similarity above a threshold) would significantly improve hit rates and reduce LLM call volume — potentially a large cost and latency saving.
- Longer term, evaluate Redis with vector search as the cache backend to support multi-instance deployments.

### 7. Add test cases
- I need to add atleast unit test cases.


```
- Prompt injection -> for safely only allowing select SQL queries.
    - Do analysis for more injection ways and solution specific to each one of them.
- If needed, go to ANN (vector DB) approach
- Plan a effecient re-indexing process.
    - becuase while doing re-try we can do increasemental re-index. only change the modified tables. Need time to implement this.
- Analysis to choose what model wil be performing better.
    - I need to generate and validate the GT SQL for better mmodel evaluation.
- Prompt Tuning
- cache -> if we have more time, we can analysis the cache hit rate and time duration what will be helpful and everything. -> I feel this wil be a huge cost and time saver.
    - can think of better retrival and storage here. for now its plain text mathicng.
```