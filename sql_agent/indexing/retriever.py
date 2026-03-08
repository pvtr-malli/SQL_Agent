import json
import os
import threading
import time

import numpy as np
from sentence_transformers import SentenceTransformer

from sql_agent.config.models import TableSchema
from sql_agent.config.settings import EMBED_MODEL, TABLES_FILE, VECTORS_FILE


class SchemaRetriever:
    """
    Embeds table schemas at index-build time and retrieves the most relevant
    tables for a user question via cosine similarity.

    Thread-safe: a read-write lock prevents reads during a live reindex.
    The index is persisted to disk so restarts do not require re-embedding.
    """

    def __init__(self) -> None:
        self._model = SentenceTransformer(EMBED_MODEL)
        self._tables: list[TableSchema] = []
        self._vectors: np.ndarray | None = None  # shape (n_tables, embed_dim), L2-normalised.
        self._lock = threading.RLock()

    def build_index(self, tables: list[TableSchema]) -> float:
        """
        Embed all table schemas and replace the existing index atomically.
        Returns embed latency in milliseconds.

        param tables: List of TableSchema objects to index.
        """
        texts = [t.to_text() for t in tables]

        t0 = time.perf_counter()
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        latency_ms = (time.perf_counter() - t0) * 1000

        with self._lock:
            self._tables = tables
            self._vectors = np.array(vectors)

        return latency_ms

    def save(self, store_dir: str) -> None:
        """
        Persist the current index (vectors + table metadata) to disk.
        Creates store_dir if it does not exist.

        param store_dir: Directory path to write vectors.npy and tables.json.
        """
        with self._lock:
            if self._vectors is None or not self._tables:
                raise RuntimeError("Nothing to save — index is empty.")
            vectors = self._vectors.copy()
            tables = self._tables[:]

        os.makedirs(store_dir, exist_ok=True)
        np.save(os.path.join(store_dir, VECTORS_FILE), vectors)

        tables_data = [t.model_dump() for t in tables]
        with open(os.path.join(store_dir, TABLES_FILE), "w") as f:
            json.dump(tables_data, f)

    def load(self, store_dir: str) -> bool:
        """
        Load a previously saved index from disk into memory.
        Returns True if loaded successfully, False if no saved index exists.

        param store_dir: Directory path containing vectors.npy and tables.json.
        """
        vectors_path = os.path.join(store_dir, VECTORS_FILE)
        tables_path = os.path.join(store_dir, TABLES_FILE)

        if not os.path.exists(vectors_path) or not os.path.exists(tables_path):
            return False

        vectors = np.load(vectors_path)
        with open(tables_path) as f:
            tables_data = json.load(f)
        tables = [TableSchema.model_validate(t) for t in tables_data]

        with self._lock:
            self._vectors = vectors
            self._tables = tables

        return True

    def retrieve(self, question: str, top_k: int = 4) -> list[tuple[TableSchema, float]]:
        """
        Return the top-k most relevant tables for a question, with their scores.

        param question: Natural language question from the user.
        param top_k: Number of tables to return.
        """
        with self._lock:
            if self._vectors is None or len(self._tables) == 0:
                raise RuntimeError("Index is empty. Call POST /index first.")
            tables = self._tables
            vectors = self._vectors

        q_vec = self._model.encode([question], normalize_embeddings=True)
        # Dot product of normalised vectors == cosine similarity.
        # If both vectors are already L2-normalised (|a| = |b| = 1), the denominator is always 1 × 1 = 1, so it simplifies to:
        # This is very handy, not much time save but still.
        # they will compute the l2 norme first: v = [3, 4]
        # |v| = sqrt(3² + 4²) = sqrt(9 + 16) = sqrt(25) = 5
        # v_normalised = [3/5, 4/5] = [0.6, 0.8] -< now the l2 norm will be 1.

        
        scores: np.ndarray = (vectors @ q_vec.T).flatten()

        top_k = min(top_k, len(tables))
        top_indices = scores.argsort()[::-1][:top_k]

        return [(tables[i], float(scores[i])) for i in top_indices]

    @property
    def is_ready(self) -> bool:
        """
        Return True if the index has been built and contains at least one table.
        """
        with self._lock:
            return self._vectors is not None and len(self._tables) > 0

    @property
    def table_count(self) -> int:
        """
        Return the number of tables currently indexed.
        """
        with self._lock:
            return len(self._tables)

    @property
    def tables(self) -> list:
        """
        Return a snapshot of all indexed TableSchema objects.
        """
        with self._lock:
            return self._tables[:]


if __name__ == "__main__":
    import sys
    from sql_agent.utils.schema_loader import load_schema
    from sql_agent.config.settings import INDEX_STORE, XLSX_PATH

    r = SchemaRetriever()

    # Try loading persisted index first; build if not found.
    if r.load(INDEX_STORE):
        print(f"Loaded index from '{INDEX_STORE}' — {r.table_count} tables")
    else:
        print(f"No saved index found — building from '{XLSX_PATH}' ...")
        tables = load_schema(XLSX_PATH)
        # print(tables)
        ## 
        ms = r.build_index(tables)
        r.save(INDEX_STORE)
        print(f"Built and saved {r.table_count} tables in {ms:.1f} ms")

    tables = load_schema(XLSX_PATH)
    print(tables)
    
    # Use question from CLI arg or fall back to a default.
    question = " ".join(sys.argv[1:]) or "Which agents handled the most escalations last week?"
    print(f"\nQuestion: {question}\n")

    results = r.retrieve(question, top_k=4)
    for i, (schema, score) in enumerate(results, 1):
        cols = ", ".join(c.name for c in schema.columns)
        print(f"  {i}. {schema.name:<25} score={score:.4f}")
        print(f"     columns: {cols}\n")
