# CLAUDE.md — Project Instructions

## Design File
**Always read and follow [design.md](design.md) before making any implementation decisions.**
If `design.md` exists, treat it as the source of truth for architecture, module structure, naming conventions, and technical decisions. Do not deviate from it without explicit user approval.

---

## Project: Agentic SQL Agent (Take-Home Assignment)

### What We Are Building
A modular, self-correcting SQL agent that:
1. Takes natural language questions from users
2. Generates SQL queries against customer service tables (from `Customer Service Tables.xlsx`)
3. Detects when retrieved information is insufficient and self-corrects (re-plans, refines, or re-retrieves)
4. Is wrapped in a production-ready API (FastAPI preferred)

### Two Core Parts

**Part 1 — Agent Architecture & Retrieval**
- Use table metadata to understand schema
- Generate SQL for scenarios defined in the `Scenarios` sheet
- Implement self-correction: retrieval confidence checks, answer validation, fallback queries, or iterative re-retrieval
- Output: SQL query (data processing not required)

**Part 2 — Production API & Observability**
- Wrap agent in a FastAPI (or gRPC) API with clean request/response contracts
- Latency target: < 20s for retrieval and reasoning-preparation (excluding LLM generation time)
- Add observability: latency tracking, logging, and signals for retrieval quality degradation

### Data
- `Customer Service Tables.xlsx` contains:
  - **Table Metadata** — schema/metadata for each table
  - **Scenarios** — test cases the agent must handle
  - **`*_tbl` sheets** — the actual tables for SQL generation

---

## Evaluation Priorities (in order)
1. System Design & Architecture — modular, clear RAG workflow, failure handling
2. Retrieval Understanding — embeddings, LLMs, reasoning strategies
3. Engineering Quality — clarity, structure, maintainability
4. Performance & Scalability — latency, concurrency awareness
5. Critical Thinking — justify decisions, acknowledge trade-offs
6. Documentation — clear for both technical and non-technical readers

---

## What NOT to Do
- Do not fine-tune LLMs
- Do not build large-scale distributed systems
- Do not target perfect LLM inference latency
- Do not implement enterprise-grade monitoring stacks
- Keep scope focused — clarity of design over completeness

---

## General Principles
- Document all assumptions, limitations, and ideas for improvement
- A partial or simplified implementation is acceptable if clearly documented
- Prioritize clarity of design and sound engineering judgment over completeness
- Any open-source or API-based LLM may be used
- Any RAG framework (e.g., LangChain) may be used

## 🎨 Code Style Guidelines

### Core Development Principles
**CRITICAL: Keep code simple and efficient - DO NOT over-engineer!**

- ✅ Write straightforward, readable code
- ✅ Optimize for efficiency when needed
- ❌ Avoid unnecessary abstractions
- ❌ Don't add features "for future flexibility"
- ❌ No premature optimization
- ❌ Keep it minimal and functional

**Rule of thumb:** If it's not explicitly required, don't build it.

### Function Docstrings
Always use this format for function docstrings:

```python
def function_name(param1: int, param2: str) -> bool:
    """
    Brief description of what the function does.

    param param1: Description of param1.
    param param2: Description of param2.
    """
```

**Requirements:**
- Always include type hints in function signature.
- Use multi-line docstring format (even for single line descriptions).
- Document parameters using `param parameter_name: description` format.
- Include return type hint (use `-> None` for void functions).

### Punctuation Rules
- Always end comments with a period (`.`).
- Always end list items in markdown files with a period (`.`).
- All sentences and descriptions must be properly punctuated.

### Type Hints (Python 3.13)
- Use built-in collection types directly: `list`, `dict`, `set`, `tuple`.
- DO NOT import from `typing` for basic collections.
- Use `typing` only for advanced types like `Optional`, `Union`, `Callable`, etc.

```python
# ✅ Correct (Python 3.9+).
def process_items(items: list[str]) -> dict[str, int]:
    pass

# ❌ Wrong - don't import List, Dict.
from typing import List, Dict
def process_items(items: List[str]) -> Dict[str, int]:
    pass
```