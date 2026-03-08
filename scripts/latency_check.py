"""
SQL Agent — Latency Benchmark
Runs N questions through the real pipeline and reports per-component
percentile statistics: p25, p50, p75, p90, p99.

Usage:
    uv run python scripts/latency_check.py          # runs default 15-question suite
    uv run python scripts/latency_check.py "q1" "q2" ...  # custom questions
"""

import sys
import statistics
import tempfile
import os

from sql_agent.agent.graph import build_graph, run_query
from sql_agent.config.settings import INDEX_STORE, XLSX_PATH
from sql_agent.indexing.retriever import SchemaRetriever
from sql_agent.utils.cache import QueryCache
from sql_agent.utils.schema_loader import load_schema

# ── colours ───────────────────────────────────────────────────────────────────
G, Y, R, C, B, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"

TARGET_NON_LLM_MS = 20_000

# ── 15 default questions (vary complexity) ────────────────────────────────────
DEFAULT_QUESTIONS = [
    # simple — single table
    "How many tickets are currently open?",
    "List all agents and their email addresses.",
    "What are the most recent 10 tickets created?",
    "How many tickets were closed last week?",
    "Show all customers from the United States.",
    # medium — aggregation / filter
    "Which agent has resolved the most tickets this month?",
    "What is the average resolution time per ticket status?",
    "How many tickets per product category were opened in the last 30 days?",
    "List customers who have more than 5 open tickets.",
    "What percentage of tickets are escalated by priority level?",
    # hard — multi-table join
    "List the top 5 customers by number of open tickets in the past 90 days, along with the agent assigned to each.",
    "Which agents handled the most escalated tickets last quarter and what was their average resolution time?",
    "For each customer tier, show the percentage of tickets that were escalated.",
    "Which product categories have the highest ticket reopen rate this year?",
    # hardest — cross-domain, subquery
    "Which agents resolved the most tickets in the product categories with the highest reopen rate in the current quarter?",
]


# ── stats helpers ─────────────────────────────────────────────────────────────

def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100) * (len(sorted_data) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (idx - lo) * (sorted_data[hi] - sorted_data[lo])


def print_stat_row(label: str, data: list[float], target: float | None = None):
    if not data:
        print(f"  {label:<22} {'N/A':>8}")
        return
    p25 = percentile(data, 25)
    p50 = percentile(data, 50)
    p75 = percentile(data, 75)
    p90 = percentile(data, 90)
    p99 = percentile(data, 99)
    avg = statistics.mean(data)

    p99_colour = ""
    if target is not None:
        p99_colour = G if p99 < target else R

    print(
        f"  {label:<22} "
        f"avg={avg:>7.0f}  "
        f"p25={p25:>7.0f}  "
        f"p50={p50:>7.0f}  "
        f"p75={p75:>7.0f}  "
        f"p90={p90:>7.0f}  "
        f"{p99_colour}p99={p99:>7.0f}{RESET}"
        + ("  ms" if not p99_colour else f"  ms  ← {'✓ PASS' if p99 < target else '✗ FAIL'} (target <{target/1000:.0f}s)" if target else "")
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    questions = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_QUESTIONS
    n = len(questions)

    from sql_agent.config.settings import LLM_MODEL
    print(f"\n{B}SQL Agent — Latency Benchmark{RESET}")
    print(f"Questions : {n}  |  Target non-LLM p99 < {TARGET_NON_LLM_MS/1000:.0f}s")
    print(f"Model     : {LLM_MODEL}\n")

    retriever = SchemaRetriever()
    if not retriever.load(INDEX_STORE):
        print("Building index...")
        retriever.build_index(load_schema(XLSX_PATH))
        retriever.save(INDEX_STORE)
    print(f"Index ready — {retriever.table_count} tables\n")

    # Use a fresh temp cache per run so results are never served from cache.
    tmp_cache = tempfile.mktemp(suffix=".json", prefix="latency_bench_")
    cache = QueryCache(tmp_cache)
    graph = build_graph(retriever, cache)

    results: list[dict] = []
    ok = fail = agentic_count = 0

    print(f"{'#':<4} {'St':<4} {'Att':<4} {'RAG':>6} {'LLM':>7} {'Val':>6} {'nonLLM':>8} {'Total':>8}  Question")
    print("─" * 100)

    for i, q in enumerate(questions, 1):
        r = run_query(q, retriever, cache, graph)
        results.append(r)

        non_llm_ms = r["latency_ms"] - r["llm_ms"]
        status_label = f"{G}ok{RESET}"   if r["status_code"] == 200 else f"{R}fail{RESET}"
        ag_marker    = f"{Y}[A]{RESET}"  if r["agentic_ms"] > 0      else "   "
        non_llm_col  = G if non_llm_ms < TARGET_NON_LLM_MS else R

        print(
            f"{i:<4} {status_label:<4} {r['attempts']:<4}"
            f"{r['rag_ms']:>6.0f}"
            f"{r['llm_ms']:>7.0f}"
            f"{r['validate_ms']:>6.1f}"
            f"{non_llm_col}{non_llm_ms:>8.0f}{RESET}"
            f"{r['latency_ms']:>8.0f}"
            f"  {ag_marker} {q[:60]}{'…' if len(q)>60 else ''}"
        )

        if r["status_code"] == 200:
            ok += 1
        else:
            fail += 1
        if r["agentic_ms"] > 0:
            agentic_count += 1

    # ── percentile summary ────────────────────────────────────────────────────
    non_llm_times = [r["latency_ms"] - r["llm_ms"] for r in results]

    print(f"\n{B}{'─'*100}{RESET}")
    print(f"{B}  Percentile Summary  (all times in ms){RESET}")
    print(f"{'─'*100}")
    print(f"  {'Metric':<22} {'avg':>11}  {'p25':>11}  {'p50':>11}  {'p75':>11}  {'p90':>11}  {'p99':>11}")
    print(f"  {'─'*92}")

    print_stat_row("RAG retrieval",      [r["rag_ms"]      for r in results])
    print_stat_row("LLM calls (total)",  [r["llm_ms"]      for r in results])
    print_stat_row("Validation",         [r["validate_ms"] for r in results])

    agentic_times = [r["agentic_ms"] for r in results if r["agentic_ms"] > 0]
    if agentic_times:
        print_stat_row(f"Agentic loop ({len(agentic_times)} runs)", agentic_times)

    print(f"  {'─'*92}")
    print_stat_row("Non-LLM latency",    non_llm_times, target=TARGET_NON_LLM_MS)
    print_stat_row("Overall latency",    [r["latency_ms"]  for r in results])

    print(f"\n  Runs: {n}  |  OK: {G}{ok}{RESET}  |  Fail: {R}{fail}{RESET}  |  Agentic triggered: {Y}{agentic_count}{RESET}")
    print(f"{'─'*100}\n")

    # Clean up temp cache file.
    if os.path.exists(tmp_cache):
        os.remove(tmp_cache)


if __name__ == "__main__":
    main()
