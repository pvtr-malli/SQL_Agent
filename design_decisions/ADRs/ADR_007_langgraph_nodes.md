# ADR-007: LangGraph — Node Structure and State Flow

## Status

Accepted

---

## Decision

Use **LangGraph** to implement the agent loop with **6 nodes**, a **conditional retry edge**, and a **pure ReAct sub-graph for attempt 3**.

---

## Why LangGraph over a plain while loop

A plain while loop works but LangGraph gives us:
- **Explicit state schema** — every piece of data the agent touches is typed and visible.
- **Visual graph** — can render the flow for debugging and documentation.
- **Clean conditional routing** — retry logic lives in the edge, not buried inside node code.
- **Easy to extend** — adding a cache node or a reranker node is just adding a new node and wiring an edge.

---

## State Schema

Everything the agent needs across the full loop lives in one typed dict.

```python
class AgentState(TypedDict):
    question:         str               # original user question (never mutated)
    cache_hit:        bool              # True if result was served from cache
    attempt:          int               # current attempt number: 1, 2, or 3
    tables:           list[TableSchema] # tables selected for this attempt
    sql:              str               # last generated SQL
    validation_error: str | None        # error from validator (None = valid)
    previous_error:   str | None        # error from the attempt before this one
    tables_used:      list[str]         # table names used in the final SQL (for logging)
    latency_ms:       float             # total elapsed time
    react_steps:      int               # number of tool calls made in the ReAct loop (attempt 3 only)
```

`react_steps` guards the ReAct loop against infinite tool use — capped at **MAX_REACT_STEPS = 10**.

---

## Nodes

### 0. `cache_check`
- Normalises the question (lowercase + collapse whitespace) and looks it up in `cache/query_cache.json`.
- On **cache hit**: writes `sql` + `cache_hit=True` into state, routes to `END` (200) immediately — skips all LLM calls.
- On **cache miss**: routes to `inject_check`.
- **No LLM call.**

### 1. `inject_check`
- Runs regex blocklist + length check on the question.
- Routes to `END` with a 400 error if injection detected.
- Routes to `retrieve` if clean.
- **No LLM call.**

### 2. `retrieve`
- Decides retrieval strategy based on `attempt`:
  - Attempt 1 → RAG top-4
  - Attempt 2 → RAG top-6 (wider net)
  - Attempt 3 → routes to `agentic_recover` sub-graph instead
- Writes `tables` into state (attempts 1 & 2 only).

### 3. `generate`
- Builds the LLM prompt from `question` + `tables` + `validation_error` (if any).
- Calls LLM to generate SQL.
- Writes `sql` into state.

### 4. `validate`
- Checks `sql` for syntax errors (via `sqlglot`) and that all referenced tables/columns exist in schema.
- Writes `validation_error` into state (None if valid).

### 5. `should_retry` *(conditional edge, not a node)*
- Reads `validation_error`, `previous_error`, and `attempt`.
- Routes to `END` (success) if `validation_error` is None.
- Routes to `agentic_recover` if `attempt == 3` (ReAct path, described below).
- Routes to `END` (failure) if `error == previous_error` (no progress).
- Otherwise increments `attempt`, copies `validation_error` → `previous_error`, routes back to `retrieve`.

---

## Attempt 3 — Pure ReAct Sub-Graph (`agentic_recover`)

When attempts 1 and 2 both fail, the graph does **not** hardcode a recovery strategy. Instead, the LLM enters a **ReAct loop** and decides its own path using tools.

### Why ReAct instead of hardcoded table selection

Attempts 1 and 2 are deterministic pipelines — they are fast and correct most of the time. But when they fail, we don't know *why*: wrong tables? wrong column names? ambiguous question? Hardcoding "LLM picks tables" is just a third deterministic guess. A ReAct loop lets the LLM **reason about the error, inspect the schema, and act accordingly** — it can check columns, look up related tables, or confirm relationships before committing to a SQL query.

### ReAct Tools

The LLM is given three tools:

| Tool | Signature | What it does |
|---|---|---|
| `search_tables` | `search_tables(query: str) -> list[str]` | Runs RAG retrieval, returns top-5 table names ranked by relevance to `query`. |
| `get_table_schemas` | `get_table_schemas(table_names: list[str]) -> list[TableSchema]` | Returns the full column list + description for all requested tables in one call. |
| `validate_sql` | `validate_sql(sql: str) -> str \| None` | Runs sqlglot syntax check + schema column check. Returns `None` if valid, or an error string describing the problem. |

The LLM can call these tools as many times as it wants (up to `MAX_REACT_STEPS = 10`). The intended pattern is: explore schema → draft SQL → call `validate_sql` → fix if needed → call `validate_sql` again → exit when it returns `None`.

The external `validate` node that runs **after** the ReAct loop exits is still present as a safety net — it catches any case where the LLM exits without calling `validate_sql` or ignores a validation error.

### ReAct Loop Design

```
agentic_recover:
  Input: question, previous_error

  System prompt:
    "You failed to generate valid SQL. The error was: {previous_error}.
     Use the tools to inspect the schema, write SQL, and verify it with
     validate_sql before finishing. Only exit when validate_sql returns None."

  Loop:
    LLM reasons → calls search_tables, get_table_schema, or validate_sql
    Tool result appended to context
    react_steps += 1

    if LLM emits final SQL (no tool call):
        write sql → state
        break

    if react_steps >= MAX_REACT_STEPS (10):
        write last SQL attempt → state
        break

  Output: tables (all schemas fetched during loop), sql
```

### Typical happy path inside the loop

```
1. search_tables("billing escalations")                          → ["escalations_tbl", "tickets_tbl", ...]
2. get_table_schemas(["escalations_tbl", "tickets_tbl"])         → full schemas for both in one call
3. validate_sql("SELECT t.id, e.reason…")                       → "Unknown column: agnt_id"
4. validate_sql("SELECT t.id, e.reason…")                       → None   ← clean
5. LLM emits final SQL, loop exits
```

---

## Graph

```
START
  │
  ▼
cache_check ──── cache hit ──→ END (200, return cached sql)
  │
  │ miss
  ▼
inject_check ──── injection detected ──→ END (400)
  │
  │ clean
  ▼
retrieve (attempt 1 or 2)
  │
  ▼
generate
  │
  ▼
validate
  │
  ├── valid ─────────────────────────────→ END (200, return sql)
  │
  ├── attempt == 1 or 2, error changed ──→ retrieve  (loop back)
  │
  ├── attempt < 3, same error ───────────→ END (422, no progress)
  │
  └── attempt == 2, error changed ────────→ agentic_recover
                                                │
                                          ReAct loop
                                          (tools: search_tables,
                                                  get_table_schema)
                                                │
                                          validate
                                                │
                                          ├── valid ──→ END (200)
                                          └── invalid → END (422, last_sql + error)
```

---

## Retry Strategy Per Attempt

| Attempt | Table Source | Error Context | LLM calls |
|---|---|---|---|
| 1 | RAG top-4 | None | 1 (generate) |
| 2 | RAG top-6 | Previous error | 1 (generate) |
| 3 | LLM chooses via ReAct tools | Previous error + schema inspection | 1–9 (ReAct loop + generate) |

---

## What Each Node Reads and Writes

| Node | Reads from state | Writes to state |
|---|---|---|
| `cache_check` | `question` | `sql`, `cache_hit` |
| `inject_check` | `question` | — |
| `retrieve` | `question`, `attempt` | `tables` |
| `generate` | `question`, `tables`, `validation_error` | `sql` |
| `validate` | `sql`, `tables` | `validation_error` |
| `should_retry` (edge) | `validation_error`, `previous_error`, `attempt` | `attempt`, `previous_error` |
| `agentic_recover` | `question`, `previous_error` | `tables`, `sql`, `react_steps` |

On a successful path (validation_error is None), the graph writes the result to the cache before routing to END.

---

## File Layout

```
sql_agent/agent/
  state.py              # AgentState TypedDict
  graph.py              # LangGraph graph construction + compile
  nodes/
    cache_check.py      # file-backed cache lookup + write
    inject_check.py
    retrieve.py
    generate.py
    validate.py
    agentic_recover.py  # ReAct loop node with search_tables, get_table_schemas, validate_sql tools
  edges/
    should_retry.py     # conditional edge logic

sql_agent/utils/
  cache.py              # QueryCache — normalise, get, set, flush to JSON file

cache/
  query_cache.json      # persisted cache (gitignored)
```

---

## Trade-offs

| Trade-off | Notes |
|---|---|
| LangGraph adds a dependency | Lightweight — just orchestration, no hidden LLM calls. |
| State is a flat dict | Simple to debug; all values inspectable at any node. |
| Attempt 3 can cost up to 10 LLM calls | Each tool call + final generate counts. Max steps cap (10) bounds the cost. |
| ReAct is slower than hardcoded table selection | Attempt 3 is the last resort — latency already degraded. Correctness matters more. |
| `should_retry` is an edge not a node | Keeps routing logic separate from action logic. Cleaner to test. |
| `react_steps` cap is arbitrary | Set to 10: inspect all 9 tables (9 steps) + 1 validate_sql call = 10. Extra headroom for a fix-and-revalidate cycle. Tunable. |
