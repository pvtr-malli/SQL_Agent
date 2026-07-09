# SQL Agent — System Design

## 1. High-Level Architecture

```mermaid
flowchart TB
    Client(["Client\n(HTTP / Gradio UI)"])
    API["FastAPI\nPOST /query"]
    Cache[("Query Cache\nfile-backed, normalised key")]
    Guard["Injection Guard\nblocklist + length check"]

    subgraph DET ["  Deterministic Tries  "]
        direction LR
        RAG["RAG Retriever\ntry 1 → top-4 tables\ntry 2 → top-6 tables"]
        LLM["LLM\nSQL Generator"]
        Val["SQL Validator\nsyntax · tables · columns"]
        RAG --> LLM --> Val
    end

    subgraph AGT ["  Agentic Recovery — try 3  "]
        direction LR
        React["ReAct Loop\n≤ 8 steps"]
        Tools["search_tables\nget_table_schemas\nvalidate_sql"]
        React <-->|"tool calls"| Tools
    end

    VectorIndex[("Vector Index\nnumpy · persisted to disk")]
    SchemaLoader["Schema Loader\nxlsx → TableSchema"]

    Client -->|"POST /query { question }"| API
    API -->|"lookup"| Cache
    Cache -->|"hit → 200"| API
    Cache -->|"miss"| Guard
    Guard -->|"400 blocked"| API
    Guard -->|"clean"| RAG
    RAG <-.->|"cosine search"| VectorIndex
    VectorIndex -.->|"built from"| SchemaLoader
    Val -->|"valid → 200"| API
    Val -->|"try 1 error"| RAG
    Val -->|"try 2 error"| React
    React -->|"200 OK"| API
    React -->|"422 exhausted"| API
    API -->|"{ sql, attempts, latency_ms }"| Client
```

---

## 2. Startup Sequence

```mermaid
sequenceDiagram
    participant App as FastAPI App
    participant Loader as Schema Loader
    participant Embedder as Embedder (MiniLM)
    participant Index as Vector Index

    App->>Loader: load_schema("Customer Service Tables.xlsx")
    Loader-->>App: table_metadata: list[TableSchema]
    App->>Embedder: embed(table_metadata)
    Embedder-->>Index: vectors + table_ids (stored in memory)
    Note over App,Index: Done once at startup — not per request.
```

---

## 3. Request Flow (Per Query)

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Cache
    participant Graph as LangGraph
    participant RAG
    participant LLM as LLM
    participant Val as SQL Validator
    participant React as Agentic Recover (ReAct)
    participant Log as Logger

    User->>API: POST /query { question }
    API->>Cache: lookup(normalize(question))
    alt Cache hit
        Cache-->>API: cached SQL
        API-->>User: { sql, cache_hit=true, latency_ms }
    else Cache miss
        API->>Graph: run(question)
        Graph->>Graph: inject_check (blocklist + length)
        alt Injection detected
            Graph-->>API: status_code=400
            API-->>User: HTTP 400 { error }
        else Clean
            Graph->>RAG: retrieve(question, top_k=4)
            RAG-->>Graph: relevant_tables[0..3]
            Graph->>LLM: generate_sql(question, schemas)
            LLM-->>Graph: sql_string
            Graph->>Val: validate(sql, retrieved_tables)
            alt Valid SQL (attempt 1 or 2)
                Val-->>Graph: OK
                Graph->>Cache: store(question, sql)
                Graph-->>API: SQLResult
                API-->>User: { sql, attempts, latency_ms }
            else Validation error (attempts 1–2)
                Val-->>Graph: error_message
                Graph->>Graph: retry_prep (increment attempt)
                Graph->>RAG: retrieve(question, top_k=6)
                Graph->>LLM: generate_sql(question, schemas, error)
                LLM-->>Graph: sql_string
                Graph->>Val: validate(sql, retrieved_tables)
            end
            opt Still failing after attempt 2 → Agentic Recovery
                Graph->>React: agentic_recover(question, error)
                loop ReAct loop (≤ MAX_REACT_STEPS=8)
                    React->>LLM: reason + pick tool
                    alt search_tables
                        LLM->>React: search_tables(query)
                        React->>RAG: retrieve(query, top_k=5)
                        RAG-->>React: table names
                    else get_table_schemas
                        LLM->>React: get_table_schemas([t1, t2, ...])
                        React-->>LLM: full schema text (batched)
                    else validate_sql
                        LLM->>React: validate_sql(sql)
                        React-->>LLM: "valid" or error description
                    else no tool call
                        LLM-->>React: final SQL answer
                    end
                end
                React-->>Graph: { sql, validation_error=None }
                Graph->>Cache: store(question, sql)
                Graph-->>API: SQLResult
                API-->>User: { sql, attempts, react_steps, latency_ms }
            end
            opt All paths exhausted
                Graph-->>API: status_code=422
                API-->>User: HTTP 422 { error, last_sql }
            end
        end
    end
```

---

## 4. LangGraph Node Structure

```mermaid
flowchart TD
    START(["START"]) --> cache_check

    cache_check["cache_check\nNormalise + lookup file cache"]
    cache_check -->|"hit"| END_HIT(["END — 200 cache hit"])
    cache_check -->|"miss"| inject_check

    inject_check["inject_check\nBlocklist regex + max length\nLayer 1 injection guard"]
    inject_check -->|"injection / too long"| END_400(["END — 400 Bad Request"])
    inject_check -->|"clean"| retrieve1

    subgraph TRY1 ["Attempt 1 — Deterministic (RAG narrow)"]
        retrieve1["retrieve\nRAG top-4 tables\n(narrow, high precision)"]
        generate1["generate\nLLM call\nschema + question"]
        validate1{"validate\nsyntax + table + column"}
        retrieve1 --> generate1 --> validate1
    end

    validate1 -->|"valid"| END_OK(["END — 200 OK\nwrite to cache"])
    validate1 -->|"error"| retry_prep

    retry_prep["retry_prep\nincrement attempt\nshift error → previous_error"]

    retry_prep --> retrieve2

    subgraph TRY2 ["Attempt 2 — Deterministic (RAG wider)"]
        retrieve2["retrieve\nRAG top-6 tables\n(wider net)"]
        generate2["generate\nLLM call\nschema + question + error context"]
        validate2{"validate\nsyntax + table + column"}
        retrieve2 --> generate2 --> validate2
    end

    validate2 -->|"valid"| END_OK
    validate2 -->|"error"| agentic_recover

    subgraph TRY3 ["Attempt 3 — Agentic Recovery (ReAct)"]
        agentic_recover["agentic_recover\nLLM reasons autonomously\nover ≤ 8 steps"]
        T1["search_tables(query)\nsemantic search, top-5"]
        T2["get_table_schemas(names[])\nfull schema text, batched"]
        T3["validate_sql(sql)\nsyntax + schema check"]
        agentic_recover --> T1
        agentic_recover --> T2
        agentic_recover --> T3
        T1 -->|"LLM picks next tool"| agentic_recover
        T2 --> agentic_recover
        T3 --> agentic_recover
    end

    agentic_recover -->|"LLM emits final SQL\n(no tool call)"| END_AGENTIC(["END — 200 OK\nwrite to cache"])
    agentic_recover -->|"MAX_REACT_STEPS hit\nor empty SQL"| END_422(["END — 422\nlast SQL + error"])
```

### Node responsibilities summary

| Node | Role | Output keys |
|---|---|---|
| `cache_check` | Exact-match cache lookup | `sql`, `cache_hit`, `status_code` |
| `inject_check` | Prompt injection guard (regex blocklist) | `status_code`, `error_message` |
| `retrieve` | RAG retrieval (top-4 or top-6) | `tables` |
| `generate` | LLM SQL generation | `sql` |
| `validate` | 4-layer SQL validation | `validation_error`, `tables_used` |
| `retry_prep` | Increment attempt, shift error context | `attempt`, `previous_error` |
| `agentic_recover` | ReAct loop with 3 tools; autonomous fix | `sql`, `tables`, `validation_error=None` |

### Agentic recover — tool contracts

| Tool | Args | Returns |
|---|---|---|
| `search_tables` | `query: str` | Top-5 table names by semantic similarity |
| `get_table_schemas` | `table_names: list[str]` | Full schema text for all tables (batched) |
| `validate_sql` | `sql: str` | `"valid"` or error description string |

---

## 5. RAG Pipeline Detail

```mermaid
flowchart LR
    subgraph Startup ["Startup (once)"]
        XLSX["Customer Service\nTables.xlsx"] --> Parse["Parse Table Metadata\n(name, columns, descriptions)"]
        Parse --> Embed["Embed each table\nall-MiniLM-L6-v2"]
        Embed --> Index["In-memory index\n{ table_id → vector }"]
    end

    subgraph PerRequest ["Per Request"]
        Q["User question"] --> EmbedQ["Embed question"]
        EmbedQ --> Cosine["Cosine similarity\nvs all table vectors"]
        Index --> Cosine
        Cosine --> TopK["Top-k tables\n(k=4 default, k=6 on retry)"]
        TopK --> Schema["Render schema text\nfor LLM prompt"]
    end
```

---

## 7. Data Flow Summary

| Stage | Input | Output | Latency Budget |
|---|---|---|---|
| Cache lookup | Normalized question | SQL (hit) or miss | < 1 ms |
| RAG retrieval | Question embedding | Top-k table schemas | < 500 ms |
| SQL generation (attempt 1) | Question + schemas | SQL string | LLM time (excluded) |
| SQL validation | SQL string + schema | OK or error message | < 50 ms |
| SQL generation (retry) | Question + schemas + error | SQL string | LLM time (excluded) |
| **Total (excluding LLM)** | | | **< 1s target** |

---

## 8. API Contract

See [design_decisions/api_design.md](design_decisions/api_design.md) for full request/response contracts.

| Endpoint | Method | Purpose |
|---|---|---|
| `/index` | POST | Rebuild vector index — drops all previous embeddings |
| `/retrieve` | GET | Inspect which tables RAG selects for a question (no LLM) |
| `/query` | POST | Generate SQL for a natural language question |

---

## 9. Observability Signals

| Signal | Log Level | When |
|---|---|---|
| Request received | INFO | Every request |
| Cache hit | INFO | Cache hit path |
| Tables retrieved | INFO | After RAG, per attempt |
| SQL generated | DEBUG | After each LLM call |
| Validation error | WARNING | Per failed attempt |
| Same error repeated (no progress) | WARNING | Early stop triggered |
| Max retries hit | WARNING | Quality degradation signal |
| Total latency | INFO | End of every request |

---

## 10. Key Design Decisions Summary

| Decision | Choice | Why |
|---|---|---|
| Agent vs deterministic pipeline | Agentic loop | Table selection is non-deterministic; multi-step questions need planning |
| RAG scope | Schema-level only | Output is SQL, not data; row-level RAG is out of scope |
| Embedding model | `all-MiniLM-L6-v2` | CPU-only, fast, strong for short metadata text |
| Vector store | Numpy in-memory | 8 tables — no FAISS/Chroma overhead needed |
| LLM | Configurable via `LLM_MODEL` env var | Swappable — any model served via compatible API |
| Max retries | 3 | Balances accuracy vs. 20s latency target |
| Retry strategy | RAG-4 → RAG-6 → LLM picks | Progressively widens context to recover from retrieval misses |
| Cache | Exact-match, TTL 24h, LRU 500 | Handles repeated common queries cheaply |
| Cache miss on failure | Skip caching errors | Don't serve bad SQL from cache |
