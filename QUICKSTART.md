# Quick Start Guide

Get SQL Agent running locally in 4 steps.

---

## Prerequisites

Before you begin, make sure you have:

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — Python package manager
- **[Ollama](https://ollama.com/download)** — local LLM runtime
- **Schema Excel file** — place it at `data/Customer Service Tables.xlsx`

---

## Step 1 — Install dependencies
```
# 1. Install uv
brew install uv

# 2. Install dependencies
uv sync

# 3. Install Ollama and pull model
brew install ollama
ollama serve  # In one terminal
ollama pull qwen2.5:7b
```

> The server expects Ollama running at `http://localhost:11434`. To use a different model or URL, set the env vars before starting:
> ```bash
> export LLM_MODEL=llama3.2
> export OLLAMA_BASE_URL=http://localhost:11434
> ```

---

## Step 3 — Start the server

```bash
uv run python -m sql_agent.main
```

On first start the server loads the saved index from disk (or prompts you to call `POST /index` if none exists). You should see:

```
============================================================
🚀  SQL Agent
============================================================

📡  API docs : http://localhost:8000/docs
🖥️   UI       : http://localhost:8000/ui

💡  Make sure Ollama is running: ollama serve
============================================================
```

---

## Environment variables

(all can be set in config/setting.py also )
| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | `qwen2.5:7b` | Ollama model to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `LLM_TEMPERATURE` | `0.1` | LLM sampling temperature |
| `SCHEMA_PATH` | `data/Customer Service Tables.xlsx` | Path to schema Excel file |
| `INDEX_STORE` | `index_store/` | Directory to save/load the vector index |
| `CACHE_FILE` | `cache/query_cache.json` | Path to the query result cache |
| `MAX_REACT_STEPS` | `8` | Max agentic ReAct tool calls per query |
