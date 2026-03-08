# API Design

Three endpoints — indexing, retrieval inspection, and SQL generation.

---

## `POST /index`

Drops all existing table embeddings and rebuilds the vector index from scratch using the latest schema source.

**When to call:** after schema changes (new tables, column updates, description edits).

**Request:** no body required.

**Response (success):**
```json
{
  "status": "ok",
  "tables_indexed": 8,
  "latency_ms": 420.1
}
```

**Response (failure):**
```json
{
  "status": "error",
  "message": "Failed to load schema: sheet 'Table Metadata' not found"
}
```
HTTP status: `500 Internal Server Error`

**Behaviour:**
- Acquires a write lock before clearing the index — in-flight `/query` requests finish before the index is replaced.
- Cache is also flushed on reindex (stale SQL may reference dropped columns).
- Logs: tables found, embed time, total time.

---

## `GET /retrieve`

Returns the tables the RAG retriever would select for a given question — without calling the LLM. Useful for debugging retrieval quality and prompt inspection.

**Query parameter:** `question` (string, required).

**Example:** `GET /retrieve?question=Which+agents+had+the+most+escalations`

**Response (success):**
```json
{
  "question": "Which agents had the most escalations",
  "tables": [
    {
      "name": "escalations_tbl",
      "score": 0.91,
      "columns": ["ticket_id", "agent_id", "escalation_reason", "escalated_at"]
    },
    {
      "name": "tickets_tbl",
      "score": 0.78,
      "columns": ["ticket_id", "agent_id", "status", "created_at"]
    },
    {
      "name": "agents_tbl",
      "score": 0.71,
      "columns": ["agent_id", "name", "team", "hire_date"]
    },
    {
      "name": "csat_tbl",
      "score": 0.54,
      "columns": ["ticket_id", "agent_id", "score", "submitted_at"]
    }
  ],
  "top_k": 4,
  "retrieval_latency_ms": 18.3
}
```

**Response (empty index):**
```json
{
  "error": "Index is empty. Call POST /index first."
}
```
HTTP status: `503 Service Unavailable`

**Notes:**
- Always returns `top_k=4` (the default). Does not simulate retry widening.
- Scores are cosine similarity values in `[0, 1]`.
- No LLM call is made.

---

## `POST /query`

Takes a natural language question, runs the full agent loop (RAG → SQL generation → validation → retry), and returns the final SQL.

**Request:**
```json
{ "question": "Which agents handled the most escalations last week?" }
```

**Validation:**
- `question` must be non-empty string, max 1000 characters.
- Prompt injection check runs before any LLM call — rejected with `400` immediately.

**Response (success):**
```json
{
  "sql": "SELECT a.agent_id, a.name, COUNT(e.ticket_id) AS escalation_count FROM agents_tbl a JOIN escalations_tbl e ON a.agent_id = e.agent_id WHERE e.escalated_at >= DATE('now', '-7 days') GROUP BY a.agent_id, a.name ORDER BY escalation_count DESC",
  "attempts": 1,
  "tables_used": ["agents_tbl", "escalations_tbl"],
  "latency_ms": 312.4
}
```

**Response (max retries exceeded):**
```json
{
  "error": "Max retries exceeded",
  "last_sql": "SELECT ...",
  "last_error": "Column 'agent_name' does not exist in agents_tbl",
  "attempts": 3,
  "latency_ms": 1840.2
}
```
HTTP status: `422 Unprocessable Entity`

**Response (prompt injection detected):**
```json
{
  "error": "Invalid input: prompt injection detected"
}
```
HTTP status: `400 Bad Request`

**Response (index not ready):**
```json
{
  "error": "Index is empty. Call POST /index first."
}
```
HTTP status: `503 Service Unavailable`

---

## Summary

| Endpoint | Method | Purpose | LLM call |
|---|---|---|---|
| `/index` | POST | Rebuild vector index from schema source | No |
| `/retrieve` | GET | Inspect which tables RAG would select | No |
| `/query` | POST | Generate SQL for a natural language question | Yes |
