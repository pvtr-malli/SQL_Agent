from sql_agent.agent.state import AgentState


def should_retry(state: AgentState) -> str:
    """
    Conditional edge after validate.

    Returns:
      "success"  — SQL is valid, route to END.
      "failure"  — same error repeated, no progress, route to END (422).
      "retry"    — attempt < 3, error changed, route to retry_prep → retrieve.
      "agentic"  — attempt == 3 and error changed, route to agentic_recover.
    """
    error = state.get("validation_error")
    prev = state.get("previous_error")

    if error is None:
        return "success"

    if error == prev:
        return "failure"

    if state.get("attempt", 1) >= 3:
        return "agentic"

    return "retry"


def retry_prep(state: AgentState) -> dict:
    """
    Node: increment attempt and shift current error → previous_error
    before looping back to retrieve.
    """
    return {
        "attempt": state["attempt"] + 1,
        "previous_error": state["validation_error"],
        "validation_error": None,
    }
