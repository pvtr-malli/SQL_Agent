# Design Requirements

## Non-Technical Requirements

- A user asks a question in plain English about customer service data.
- The system returns a SQL query that answers the question.
- If the system cannot generate a valid answer, it tries again before giving up.
- **Latency**: The system must respond within 20 seconds (excluding LLM generation time).
- The system must log every request and flag when it struggles to answer.
- **Monitoring**: Add a basic monitoring system to track the latency for 
    - seach query, 
    - how many re-tries it took, 
    - metadata: for input question, its length, etc, 
    - metadata:  model performance monitering, **how many tables used for anwering (would be helpful for post-analsying or error analysis on where the model failing most.**)




## Technical Requirements

### Input / Output
- Input: natural language question (string). 
    - Might need to check for the **prompt injuction also**. 
- Output: SQL query (string) + number of attempts + latency in ms.

### Agent
- Load table schema from `Table Metadata` sheet at startup (once, not per request).
- Embed each table's metadata using sentence-transformers (local, CPU).
- Retrieve top-k relevant tables via cosine similarity for each question.
- Send retrieved schema + question to Claude (claude-sonnet-4-6) to generate SQL.
- Validate generated SQL: check syntax and that referenced tables/columns exist in schema.
- Retry up to 3 times, feeding the validation error back to the LLM on each retry.

### API
- FastAPI, single endpoint: `POST /query`.
- Request: `{ "question": str }`.
- Response: `{ "sql": str, "attempts": int, "latency_ms": float }`.

### Observability
- Structured `logging` only — no external monitoring tools.
- Log per request:
  - Input question + character length.
  - Retrieved tables (names + count).
  - Generated SQL.
  - Attempt count.
  - Search/retrieval latency and total latency (ms).
- Warn in logs if max retries are hit (signals model struggling with query type).
