# ADR-005: LLM Model Choice and Evaluation

## Status

Accepted

---

## Context

The agent needs an LLM to generate SQL from a natural language question and a retrieved schema context. Two decisions are needed: which model to use, and how to evaluate whether it is performing well enough.

## Decision

- **Model: TODO**
- **Evaluation: correctness check against known scenario answers + retry rate as a proxy metric.**

---

## Rationale

### Model Choice

**Options considered:**

Bets option:
1 - claude opus -> but this is very costly (we have to look for this when the accuracy is very important)

| # | Model | HuggingFace Path | Params | CPU Ready |
|---|---|---|---|---|
| 1 | SQLCoder-7B-2 | `defog/sqlcoder-7b-2` | 7B | Yes (GGUF available) |
| 2 | OmniSQL-7B | `seeklhy/OmniSQL-7B` | 7B | Via GGUF |
| 3 | Arctic-Text2SQL-R1-7B | `Snowflake/Arctic-Text2SQL-R1-7B` | 7B | Via GGUF |

-> these models are documented good, but bigger models (7B). **IT will be very slow in CPU only systems.** -> should look for smaller ones.


| Model | Path | Params | BIRD Score | CPU Speed | Multi-JOIN |
|---|---|---|---|---|---|
| XiYanSQL-3B | `XGenerationLab/XiYanSQL-QwenCoder-3B-2504` | 3B | ~mid-50s% (est.) | 8–15s (Q4 GGUF) | Yes |
| Prem-1B-SQL | `prem-research/prem-1B-SQL` | 1.3B | 51.54% | 5–10s | Yes |
| T5-Large Spider | `gaussalgo/T5-LM-Large-text2sql-spider` | 770M | 49.2% EM (Spider) | 2–5s | Yes |

---

### How to Evaluate the Model

**No ground-truth executor** (we don't run SQL against a DB), so we use two proxies:

**1. Structural correctness (automated):**
- SQL parses without syntax errors.
- All referenced tables exist in the known schema.
- All referenced columns exist in the referenced tables.
- The things used for joins are valid keys.
- This is the validator already in the agent loop.

**2. Scenario coverage (manual spot-check):**
- Run all 15 scenarios from the `Scenarios` sheet through the agent.
- Manually inspect the generated SQL for logical correctness.
- Track: how many passed on attempt 1 vs 2 vs 3 vs failed entirely.

**3. Retry rate as a quality signal (operational):**
- If >20% of requests hit attempt 2 or 3, the model+prompt combination needs improvement.
- If >5% hit max retries, it is a model or schema description quality problem.
- Logged automatically via observability.

---

## Trade-offs

- **No automated semantic evaluation** — checking if the SQL is *logically correct* (not just structurally valid) requires executing it against real data. Out of scope per the assignment ("no data processing needed"). Manual review of scenarios is the pragmatic substitute.
- **Haiku would be cheaper** but the higher retry rate would likely negate the saving in API calls and add latency.
- **If the model is swapped** (e.g. to a local model), the prompt may need tuning — Claude follows "output only SQL" reliably; other models often add prose around the query.



## how did I pick the mdoels - Using BIRD score.
BIRD = Big bench for Intelligent Reasoning and Discovery (in SQL).

It's a benchmark dataset of ~12,000 NL→SQL pairs from real-world databases (finance, healthcare, sports, etc.), much harder than the older Spider benchmark because:

Databases have more tables and columns
Questions require domain knowledge (e.g., knowing what "active customer" means in context)
Many queries need multi-table joins, aggregations, and nested subqueries
Score = execution accuracy — the generated SQL is actually run against the DB and the result is compared to the ground truth result. So it's stricter than just checking if SQL is syntactically valid.

Benchmark	What it tests	Difficulty
Spider	Clean academic DBs, simple questions	Easy
BIRD	Real-world messy DBs, domain-specific questions	Hard
So when prem-1B-SQL says 51.54% BIRD — it means it gets the right answer (not just valid SQL) on ~51% of hard real-world questions at 1.3B params, which is decent for a model that small.