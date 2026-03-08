import os

# Project root = three levels up from this file (config/ → sql_agent/ → project root).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Paths ---
XLSX_PATH = os.getenv("SCHEMA_PATH", os.path.join(_PROJECT_ROOT, "data", "Customer Service Tables.xlsx"))
INDEX_STORE = os.getenv("INDEX_STORE", os.path.join(_PROJECT_ROOT, "index_store"))

# --- Retriever ---
EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K_DEFAULT = 4

# --- Index persistence filenames ---
VECTORS_FILE = "vectors.npy"
TABLES_FILE = "tables.json"

# --- Query cache ---
CACHE_FILE = os.getenv("CACHE_FILE", os.path.join(_PROJECT_ROOT, "cache", "query_cache.json"))

# --- LLM (Ollama) ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL",  "http://localhost:11434")
LLM_MODEL       = os.getenv("LLM_MODEL",        "qwen2.5:7b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
MAX_REACT_STEPS = int(os.getenv("MAX_REACT_STEPS",   "8"))
