import re

from sql_agent.agent.state import AgentState

# --- Blocklist (ADR-006) ---
# Covers: DDL keywords, classic hijack openers, persona injection,
# prompt extraction, SQL comment markers, and newline injection.
_BLOCKLIST = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE)\b"
    r"|ignore\s+(all\s+)?previous\s+instructions?"
    r"|you\s+are\s+now\b"
    r"|\bact\s+as\b"
    r"|\bsystem\s+prompt\b"
    r"|\breveal\b"
    r"|--|/\*|\*/"
    r"|\\n|\\r",
    re.IGNORECASE,
)

_MAX_LENGTH = 1000  # matches QueryRequest.question max_length in models.py


def inject_check(state: AgentState) -> dict:
    question = state["question"]
    if len(question) > _MAX_LENGTH:
        return {
            "status_code": 400,
            "error_message": "Question exceeds maximum length of 1000 characters.",
        }
    if _BLOCKLIST.search(question):
        return {
            "status_code": 400,
            "error_message": "Request rejected: potential injection detected.",
        }
    return {}


def route_inject(state: AgentState) -> str:
    return "injection" if state.get("status_code") == 400 else "clean"
