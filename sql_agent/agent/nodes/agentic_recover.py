from sql_agent.agent.state import AgentState

# Stub — ReAct loop implementation is tracked separately (ADR-007 attempt 3).
# Routes to END with 422 until the full ReAct sub-graph is wired in.


def agentic_recover(state: AgentState) -> dict:
    return {
        "status_code": 422,
        "error_message": (
            "Agentic recovery (attempt 3) is not yet implemented. "
            f"Last error: {state.get('validation_error')}"
        ),
    }
