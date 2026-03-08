# ADR-003: Do We Need Caching?

## Status

Accepted

---

## Context

In a company, the same or semantically similar questions are frequently asked by different people or repeatedly over time (e.g. "show all open high-priority tickets"). Each request currently triggers an embedding call + LLM call. Should we cache SQL results to avoid redundant work?

## Decision

- **Yes — add a simple in-memory exact-match cache with TTL.**

---

## Rationale

**Why cache helps here:**
- SQL generation for identical questions is deterministic — same question will always produce the same SQL.
- In a support team, common queries (daily standups, dashboards) get asked repeatedly by different agents.
- Skipping the LLM call on a cache hit reduces latency significantly and saves API cost.

**What we cache:**
- Key: normalized question string (lowercased, stripped whitespace).
- Value: the generated SQL + metadata (attempt count, retrieved tables).

**What we do NOT cache:**
- Failed attempts (max retries exceeded) — don't cache errors.
- Partial results — only cache successfully validated SQL.

---

## Cache Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage | In-memory dict | Simple, zero infra, sufficient for single-instance. Redis is the upgrade path for multi-instance. |
| Expiry type | TTL (time-to-live) | Schema could change; stale SQL against a new schema would be wrong. TTL ensures periodic refresh. |
| TTL duration | 24 hours | **NEED ANALYSIS** : Schema changes rarely within a day. Long enough to benefit from repeated queries. |
| Cache type | Exact-match on normalized question | Semantic caching (embedding similarity) is overkill here — adds complexity for marginal gain. |
| Max size | 500 entries (LRU eviction) | **NEED ANALYSIS** |

---

## Trade-offs

- **Exact-match only** — "show open tickets" and "list open tickets" are treated as different questions. Semantic caching (embed the question, find similar cached queries) would handle this but adds complexity. Not needed for now.
- **In-memory is lost on restart** — acceptable for this assignment. In production, use Redis with persistence.
- **TTL is a blunt tool** — if the schema changes mid-day, cached SQL could reference dropped columns. Mitigation: provide an admin endpoint to flush the cache on schema updates.
- **Multi-instance problem** — each API instance has its own cache. For horizontal scaling, switch to a shared Redis cache.
