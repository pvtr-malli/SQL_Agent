"""
Persistent metrics store — counters survive server restarts.

Loads from METRICS_FILE on first use, flushes back to disk after every record() call.
Thread-safe via a threading.Lock.
"""

import json
import os
import threading
from typing import Any

from sql_agent.config.settings import METRICS_FILE

# Threshold below which a retrieval score is flagged as potentially low quality.
# Cosine similarity is in [-1, 1]; for well-matched schema descriptions we expect > 0.3.
LOW_SCORE_THRESHOLD = 0.20

_lock = threading.Lock()

_DEFAULTS: dict[str, Any] = {
    "total_requests":       0,
    "success":              0,
    "failed":               0,
    "cache_hits":           0,
    "agentic_triggered":    0,
    "validation_failures":  0,
    "low_score_retrievals": 0,
    "_latency_sum_ms":      0.0,
    "_rag_sum_ms":          0.0,
    "_llm_sum_ms":          0.0,
    "_validate_sum_ms":     0.0,
}


def _load() -> dict[str, Any]:
    """Read counters from disk, falling back to defaults if the file is missing or corrupt."""
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE) as f:
                saved = json.load(f)
            # Merge: keep any keys from defaults not yet in the saved file (schema evolution).
            return {**_DEFAULTS, **saved}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def _flush(counters: dict[str, Any]) -> None:
    """Write counters to disk atomically via a temp file."""
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    tmp = METRICS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(counters, f, indent=2)
    os.replace(tmp, METRICS_FILE)


# Load on module import so the first record() sees the correct totals.
_counters: dict[str, Any] = _load()


def record(result: dict, top_score: float) -> None:
    """
    Called once per completed query request.

    param result:    The dict returned by run_query().
    param top_score: Highest cosine similarity score from the retriever this request.
    """
    with _lock:
        _counters["total_requests"] += 1

        if result["status_code"] == 200:
            _counters["success"] += 1
        else:
            _counters["failed"] += 1

        if result.get("cache_hit"):
            _counters["cache_hits"] += 1

        if result.get("agentic_ms", 0) > 0:
            _counters["agentic_triggered"] += 1

        if result.get("attempts", 1) >= 2:
            _counters["validation_failures"] += 1

        if top_score < LOW_SCORE_THRESHOLD:
            _counters["low_score_retrievals"] += 1

        _counters["_latency_sum_ms"]  += result.get("latency_ms", 0.0)
        _counters["_rag_sum_ms"]      += result.get("rag_ms", 0.0)
        _counters["_llm_sum_ms"]      += result.get("llm_ms", 0.0)
        _counters["_validate_sum_ms"] += result.get("validate_ms", 0.0)

        _flush(_counters)


def snapshot() -> dict:
    """Return a copy of the current metrics, safe to serialise as JSON."""
    with _lock:
        n = _counters["total_requests"] or 1  # avoid div-by-zero
        return {
            "requests": {
                "total":              _counters["total_requests"],
                "success":            _counters["success"],
                "failed":             _counters["failed"],
                "cache_hits":         _counters["cache_hits"],
                "cache_hit_rate_pct": round(_counters["cache_hits"] / n * 100, 1),
            },
            "quality": {
                "validation_failures":         _counters["validation_failures"],
                "validation_failure_rate_pct": round(_counters["validation_failures"] / n * 100, 1),
                "agentic_triggered":           _counters["agentic_triggered"],
                "agentic_rate_pct":            round(_counters["agentic_triggered"] / n * 100, 1),
                "low_score_retrievals":        _counters["low_score_retrievals"],
                "low_score_rate_pct":          round(_counters["low_score_retrievals"] / n * 100, 1),
                "low_score_threshold":         LOW_SCORE_THRESHOLD,
            },
            "latency_avg_ms": {
                "total":    round(_counters["_latency_sum_ms"] / n, 1),
                "rag":      round(_counters["_rag_sum_ms"] / n, 1),
                "llm":      round(_counters["_llm_sum_ms"] / n, 1),
                "validate": round(_counters["_validate_sum_ms"] / n, 1),
            },
        }
