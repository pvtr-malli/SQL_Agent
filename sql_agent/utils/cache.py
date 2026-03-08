import json
import os
import re
import threading


class QueryCache:
    """
    Persistent file-backed cache mapping normalized questions to valid SQL.

    - Stored as a JSON dict in CACHE_FILE.
    - Key: question lowercased + whitespace collapsed (improves hit rate for
      minor phrasing differences like extra spaces or capitalisation).
    - Value: the validated SQL string.
    - Only successful queries (validation_error is None) should be written.
    - Thread-safe via a lock.
    """

    def __init__(self, cache_file: str) -> None:
        self._path = cache_file
        self._lock = threading.Lock()
        self._data: dict[str, str] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, question: str) -> str | None:
        """Return cached SQL for question, or None if not cached."""
        key = self._normalise(question)
        with self._lock:
            return self._data.get(key)

    def set(self, question: str, sql: str) -> None:
        """Store sql for question and flush to disk."""
        key = self._normalise(question)
        with self._lock:
            self._data[key] = sql
            self._flush()

    def invalidate(self, question: str) -> bool:
        """Remove a single entry. Returns True if it existed."""
        key = self._normalise(question)
        with self._lock:
            if key not in self._data:
                return False
            del self._data[key]
            self._flush()
            return True

    def clear(self) -> int:
        """Remove all entries. Returns count of entries cleared."""
        with self._lock:
            count = len(self._data)
            self._data = {}
            self._flush()
            return count

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(question: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace."""
        text = question.strip().lower()
        text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
        return re.sub(r"\s+", " ", text).strip()

    def _load(self) -> dict[str, str]:
        if not os.path.exists(self._path):
            return {}
        with open(self._path) as f:
            return json.load(f)

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)


if __name__ == "__main__":
    from sql_agent.config.settings import CACHE_FILE

    cache = QueryCache(CACHE_FILE)
    print(f"Cache loaded — {cache.size} entries in '{CACHE_FILE}'")

    cache.set("How many tickets were opened last week?", "SELECT COUNT(*) FROM tickets_tbl WHERE created_at >= NOW() - INTERVAL 7 DAY")
    cache.set("List all premium customers", "SELECT * FROM customers_tbl WHERE tier = 'premium'")

    print(f"After writes — {cache.size} entries")

    hit = cache.get("how many tickets were opened last week?")  # different casing
    print(f"Cache hit (case-insensitive): {hit}")

    miss = cache.get("something completely different")
    print(f"Cache miss: {miss}")
