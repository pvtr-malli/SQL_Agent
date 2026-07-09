# ADR-004: Agent Loop — Max Retries and Stop Conditions

## Status

Accepted

---

## Context

The agent runs a generate → validate → retry loop. Without limits, a failing question could loop indefinitely, burning LLM API calls and blocking the request. We need to decide: how many retries, when to stop, and what to return on failure.

## Decision

- **Max 3 attempts total (1 initial + 2 retries).**
- **Stop early if the same error repeats twice** — retrying an identical error without changing strategy is pointless.
- **On final failure, return HTTP 422 with the last error and last generated SQL.**

---

## Rationale

**Why 3 attempts?**

- Attempt 1: Normal RAG path — expected to work fine most of the time.
- Attempt 2: Wider retrieval (top-6) + error fed back to LLM — catches most retrieval misses.
- Attempt 3: LLM picks its own tables (bypasses RAG) — handles edge cases where cosine sim consistently fails.
- Attempt 4+ rarely adds value — if 3 attempts with different strategies fail, the question is likely malformed or outside scope.

**Why stop on repeated error? - patient window=1**

- If the validator returns the same error on attempt 2 as attempt 1, the LLM is not making progress.
- Continuing wastes API calls without improving the result.
- Log this as a quality signal — useful for post-analysis.

---

## Loop Design

```
attempt = 1
error = None

while attempt <= MAX_RETRIES (3):

    if attempt == 1:
        tables = RAG top-4

    elif attempt == 2:
        tables = RAG top-6  # wider net
        context += previous error

    elif attempt == 3:
        tables = LLM picks from all table names  # bypass RAG
        context += previous error

    sql = LLM generate(question, tables, error)
    error = validate(sql)

    if no error → return sql  ✓

    if error == previous_error → break early  (no progress)

    attempt += 1

→ raise MaxRetriesExceeded (HTTP 422)
```

---

## Stop Conditions Summary

| Condition | Action |
|---|---|
| SQL passes validation | Return SQL immediately. |
| Max attempts (3) reached | Return 422 with last SQL + error. |
| Same error repeated | Break early, return 422. Log as quality signal. |
| Prompt injection detected | Reject immediately, no LLM call. Return 400. |

---

## Trade-offs

- **3 is conservative** — could increase to 5 for higher accuracy, but each retry adds ~5-15s latency. 3 keeps us comfortably within the 20s latency target.
- **Early stop on repeated error** — small risk of stopping too soon if the error message is identical but the cause is different. Acceptable trade-off for cost savings.
- **Attempt 3 costs an extra LLM call** (table selection + SQL generation) — ~2 LLM calls on the worst path. Justified by the accuracy gain.
