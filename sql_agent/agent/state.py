from typing import TypedDict

from sql_agent.config.models import TableSchema


class AgentState(TypedDict):
    question:         str                # original user question (never mutated)
    cache_hit:        bool               # True if result was served from cache
    attempt:          int                # current attempt number: 1, 2, or 3
    tables:           list[TableSchema]  # tables selected for this attempt
    sql:              str                # last generated SQL
    validation_error: str | None         # error from validator (None = valid)
    previous_error:   str | None         # error from the attempt before this one
    tables_used:      list[str]          # table names found in the final SQL (for logging)
    latency_ms:       float              # total elapsed time (set by the graph runner)
    react_steps:      int                # tool calls made in the ReAct loop (attempt 3 only)
    status_code:      int                # HTTP status code for the final response
    error_message:    str | None         # human-readable error (400 / 422 paths)
    # Per-component timing (ms) — accumulated across all attempts
    rag_ms:           float
    llm_ms:           float
    validate_ms:      float
    agentic_ms:       float
