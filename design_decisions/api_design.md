# API Design

Five endpoints — indexing, retrieval inspection, SQL generation, cache management, and runtime metrics.

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

## `GET /metrics`

Returns accumulated runtime metrics since the server first started — persisted across restarts in `cache/metrics.json`.

**Request:** no parameters.

**Response:**
```json
{
  "requests": {
    "total": 42,
    "success": 40,
    "failed": 2,
    "cache_hits": 8,
    "cache_hit_rate_pct": 19.0
  },
  "quality": {
    "validation_failures": 11,
    "validation_failure_rate_pct": 26.2,
    "agentic_triggered": 3,
    "agentic_rate_pct": 7.1,
    "low_score_retrievals": 1,
    "low_score_rate_pct": 2.4,
    "low_score_threshold": 0.2
  },
  "latency_avg_ms": {
    "total": 4120.1,
    "rag": 66.2,
    "llm": 4046.0,
    "validate": 3.1
  }
}
```

**Fields:**

| Field | Description |
|---|---|
| `requests.total` | All queries received (excludes blocked injections) |
| `requests.cache_hit_rate_pct` | % served from cache with no LLM call |
| `quality.validation_failures` | Queries that needed ≥ 2 attempts (first SQL was invalid) |
| `quality.agentic_triggered` | Queries that escalated to the ReAct agentic loop (attempt 3) |
| `quality.low_score_retrievals` | Queries where top RAG cosine score < threshold — potential schema drift |
| `latency_avg_ms` | Running average per component across all non-cached requests |

**Notes:**
- Counters accumulate indefinitely — there is no reset endpoint (delete `cache/metrics.json` to reset manually).
- Cache hit requests contribute to request counts but record `0 ms` for all component timings.

---

## `DELETE /cache`

Clears all cached query → SQL entries. Call this after rebuilding the index so stale SQL is not served.

**Request:** no body required.

**Response:**
```json
{ "status": "ok", "entries_cleared": 16 }
```

---

## Summary

| Endpoint | Method | Purpose | LLM call |
|---|---|---|---|
| `/index` | POST | Rebuild vector index from schema source | No |
| `/retrieve` | GET | Inspect which tables RAG would select | No |
| `/query` | POST | Generate SQL for a natural language question | Yes |
| `/metrics` | GET | Runtime counters, quality signals, avg latency | No |
| `/cache` | DELETE | Clear the query result cache | No |
