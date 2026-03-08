# SQL Agent — System Design

## 1. High-Level Architecture

```mermaid
graph TB
    Client["Client\n(HTTP)"]
    API["FastAPI\nPOST /query"]
    Cache["In-Memory Cache\n(exact-match, TTL 24h)"]
    Agent["SQL Agent\n(orchestrator)"]
    RAG["RAG Retriever\n(sentence-transformers + cosine)"]
    VectorIndex["Table Metadata\nVector Index\n(numpy, built at startup)"]
    LLM["Claude claude-sonnet-4-6\n(SQL Generator)"]
    Validator["SQL Validator\n(syntax + schema check)"]
    Logger["Structured Logger\n(observability)"]
    SchemaLoader["Schema Loader\n(xlsx → dicts, once at startup)"]

    Client -->|"{ question: str }"| API
    API --> Cache
    Cache -->|"cache hit"| API
    Cache -->|"cache miss"| Agent
    Agent --> RAG
    RAG --> VectorIndex
    VectorIndex -.->|"built from"| SchemaLoader
    RAG -->|"top-k table schemas"| Agent
    Agent -->|"schema + question"| LLM
    LLM -->|"SQL string"| Validator
    Validator -->|"valid"| Agent
    Validator -->|"error + SQL"| Agent
    Agent -->|"retry with error context"| LLM
    Agent --> Logger
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
    participant Agent
    participant RAG
    participant LLM as Claude (claude-sonnet-4-6)
    participant Val as SQL Validator
    participant Log as Logger

    User->>API: POST /query { question }
    API->>Log: log(question, len)
    API->>Cache: lookup(normalize(question))
    alt Cache hit
        Cache-->>API: cached SQL + metadata
        API-->>User: { sql, attempts, latency_ms }
    else Cache miss
        API->>Agent: run(question)
        Agent->>Log: log(attempt=1, strategy=rag_top4)
        Agent->>RAG: retrieve(question, top_k=4)
        RAG-->>Agent: relevant_tables[0..3]
        Agent->>LLM: generate_sql(question, schemas)
        LLM-->>Agent: sql_string

        Agent->>Val: validate(sql, schema)
        alt Valid SQL
            Val-->>Agent: OK
            Agent->>Cache: store(question, sql)
            Agent-->>API: SQLResult
            API-->>User: { sql, attempts, latency_ms }
        else Validation error
            Val-->>Agent: error_message
            Agent->>Log: log(attempt=1, error)

            Agent->>RAG: retrieve(question, top_k=6)
            Agent->>LLM: generate_sql(question, schemas, error)
            LLM-->>Agent: sql_string
            Agent->>Val: validate(sql, schema)
            alt Valid SQL
                Val-->>Agent: OK
                Agent-->>API: SQLResult
                API-->>User: { sql, attempts=2, latency_ms }
            else Still failing
                Agent->>LLM: pick_tables(question, all_table_names)
                LLM-->>Agent: selected_tables
                Agent->>LLM: generate_sql(question, selected_schemas, error)
                LLM-->>Agent: sql_string
                Agent->>Val: validate(sql, schema)
                alt Valid
                    Val-->>Agent: OK
                    Agent-->>API: SQLResult
                    API-->>User: { sql, attempts=3, latency_ms }
                else Max retries exceeded
                    Agent->>Log: WARN max_retries_hit
                    Agent-->>API: MaxRetriesError
                    API-->>User: HTTP 422 { error, last_sql }
                end
            end
        end
    end
```

---

## 4. Agent Loop Detail

```mermaid
flowchart TD
    Start(["Question received"]) --> A1

    A1["Attempt 1\nRAG top-4 tables\nno error context"]
    A1 --> G1["LLM: generate SQL"]
    G1 --> V1{"Validate SQL"}
    V1 -->|"Valid"| Return(["Return SQL ✓"])
    V1 -->|"Error"| ErrCheck1{"Same error\nas last attempt?"}
    ErrCheck1 -->|"Yes (no progress)"| Fail
    ErrCheck1 -->|"No"| A2

    A2["Attempt 2\nRAG top-6 tables\n+ error fed back to LLM"]
    A2 --> G2["LLM: generate SQL\n(with error context)"]
    G2 --> V2{"Validate SQL"}
    V2 -->|"Valid"| Return
    V2 -->|"Error"| ErrCheck2{"Same error\nas last attempt?"}
    ErrCheck2 -->|"Yes (no progress)"| Fail
    ErrCheck2 -->|"No"| A3

    A3["Attempt 3\nLLM picks tables\n(bypasses RAG)\n+ error fed back"]
    A3 --> G3a["LLM: select tables\nfrom all table names"]
    G3a --> G3b["LLM: generate SQL\n(with error context)"]
    G3b --> V3{"Validate SQL"}
    V3 -->|"Valid"| Return
    V3 -->|"Error"| Fail

    Fail(["HTTP 422\nlast SQL + error\nlog WARN"])
```

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
| LLM | Claude claude-sonnet-4-6 | Reliable SQL output, follows "output only SQL" instructions, available via API |
| Max retries | 3 | Balances accuracy vs. 20s latency target |
| Retry strategy | RAG-4 → RAG-6 → LLM picks | Progressively widens context to recover from retrieval misses |
| Cache | Exact-match, TTL 24h, LRU 500 | Handles repeated common queries cheaply |
| Cache miss on failure | Skip caching errors | Don't serve bad SQL from cache |

---

## 11. Production Deployment Architecture

```mermaid
graph TB
    subgraph Client Layer
        Browser["Browser / Dashboard"]
        CLI["CLI Client"]
    end

    subgraph API Layer
        LB["Load Balancer\n(nginx / ALB)"]
        API1["FastAPI Instance 1"]
        API2["FastAPI Instance 2"]
    end

    subgraph Cache Layer
        Redis["Redis\n(shared cache, replaces in-memory\nfor multi-instance)"]
    end

    subgraph LLM Layer
        AnthropicAPI["Anthropic API\n(Claude claude-sonnet-4-6)"]
    end

    subgraph Observability
        Logs["Structured Logs\n(stdout → log aggregator)"]
    end

    Browser --> LB
    CLI --> LB
    LB --> API1
    LB --> API2
    API1 --> Redis
    API2 --> Redis
    API1 --> AnthropicAPI
    API2 --> AnthropicAPI
    API1 --> Logs
    API2 --> Logs
```

> **Current scope:** single-instance with in-memory cache. Redis is the drop-in upgrade for horizontal scaling.
