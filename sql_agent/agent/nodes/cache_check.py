from sql_agent.agent.state import AgentState
from sql_agent.utils.cache import QueryCache


def make_cache_check(cache: QueryCache):
    """Return a cache_check node bound to the given QueryCache instance."""

    def cache_check(state: AgentState) -> dict:
        sql = cache.get(state["question"])
        if sql:
            return {"sql": sql, "cache_hit": True, "status_code": 200}
        return {"cache_hit": False}

    return cache_check


def route_cache(state: AgentState) -> str:
    return "hit" if state.get("cache_hit") else "miss"
