from sql_agent.agent.state import AgentState
from sql_agent.utils.cache import QueryCache
from sql_agent.utils.logger import get_logger

logger = get_logger(__name__)


def make_cache_check(cache: QueryCache):
    """Return a cache_check node bound to the given QueryCache instance."""

    def cache_check(state: AgentState) -> dict:
        logger.info("[cache_check] question=%r", state["question"])
        sql = cache.get(state["question"])
        if sql:
            logger.info("[cache_check] HIT — returning cached SQL")
            return {"sql": sql, "cache_hit": True, "status_code": 200}
        logger.info("[cache_check] MISS — proceeding to inject_check")
        return {"cache_hit": False}

    return cache_check


def route_cache(state: AgentState) -> str:
    return "hit" if state.get("cache_hit") else "miss"
