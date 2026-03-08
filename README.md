# SQL Agent

A natural language to SQL agent built with LangGraph, RAG-based schema retrieval, and an agentic ReAct recovery loop.

## Introduction

**SQL Agent** is a service that lets anyone query a relational database using plain English — no SQL knowledge needed. You type a question like *"How many tickets are currently open?"* and the agent figures out which tables to look at, writes the SQL, validates it, and returns the result.

### ✨ Features

- 🗣️ **Natural language interface** — ask questions in plain English, get SQL answers back
- 🔍 **Smart schema retrieval (RAG)** — only the relevant table schemas are sent to the LLM, keeping prompts focused and costs low
- 🔄 **Automatic retry** — if the first SQL attempt fails validation, the agent refines and retries up to 3 times
- 🤖 **Agentic self-correction** — on repeated failure, a ReAct loop lets the LLM use tools to inspect the schema and fix its own query
- 🛡️ **Injection protection** — blocklist + SELECT-only enforcement prevents destructive SQL from ever being executed
- ⚡ **Query cache** — identical questions are served from cache instantly, skipping the LLM entirely
- 📊 **Latency benchmarking** — built-in benchmark script reports per-component timings (RAG, LLM, validation, agentic) with p25–p99 percentiles

### ⚡ Performance

> Measured on 15 questions (simple → complex), model: `qwen2.5:7b`, 9 tables

- 🔍 **RAG retrieval:** ~54 ms median, ~218 ms p99
- 🤖 **SQL generation (LLM):** ~2.7 s median, ~17 s p99
- ✅ **Validation:** ~2 ms median, ~9 ms p99
- 🔄 **Non-LLM pipeline:** ~59 ms median, ~225 ms p99 ✅ *(target < 20 s)*
- 🎯 **Success rate:** 15 / 15 (100%) — hardest query required agentic loop

---

## Documentation

### System Design
- [System Design](design.md) — architecture overview, request flow, LangGraph node structure, RAG pipeline, and API contract

### Production Deployment
- [AWS Deployment Architecture](aws_deployment.md) — production deployment diagram on AWS (ECS Fargate, ElastiCache, EFS, S3, CloudWatch)

### Architecture Decision Records (ADRs)
Key decisions made during design, with context and reasoning:

| ADR | Decision |
|---|---|
| [ADR 001](design_decisions/ADRs/ADR_001_do_we_need_agents.md) | Do we need an agent? |
| [ADR 002](design_decisions/ADRs/ADR_002_do_we_need_rag.md) | Do we need RAG? |
| [ADR 003](design_decisions/ADRs/ADR_003_llm_model_choice.md) | LLM model choice |
| [ADR 004](design_decisions/ADRs/ADR_004_do_we_need_cache.md) | Do we need a cache? |
| [ADR 005](design_decisions/ADRs/ADR_005_agent_loop_limits.md) | Agent loop limits |
| [ADR 006](design_decisions/ADRs/ADR_006_prompt_injection.md) | Prompt injection protection |
| [ADR 007](design_decisions/ADRs/ADR_007_langgraph_nodes.md) | LangGraph node structure |

Additional design docs:
- [API Design](design_decisions/api_design.md) — request/response contracts for all endpoints
- [Design Requirements](design_decisions/design_requirements.md) — functional and non-functional requirements

### Assumptions, Limitations & Improvements
- [thing_to_improve.md](thing_to_improve.md) — documented assumptions, current limitations, and planned improvements

---

## Benchmarking

15 questions (simple → complex), model: `qwen2.5:7b`, 9 tables. Full results: [scripts/1_latency_betchmark.md](scripts/1_latency_betchmark.md)

### Per-component percentiles (ms)

| Component | avg | p25 | p50 | p75 | p90 | p99 |
|---|---:|---:|---:|---:|---:|---:|
| RAG retrieval | 66 | 38 | 54 | 73 | 100 | 218 |
| LLM calls (total) | 4,046 | 1,526 | 2,740 | 4,274 | 5,828 | 17,050 |
| Validation | 3 | 2 | 2 | 4 | 6 | 9 |
| Agentic loop (1 run) | 7,511 | — | — | — | — | 7,511 |
| **Non-LLM latency** | **74** | **43** | **59** | **82** | **129** | **225** ✅ |
| Overall latency | 4,120 | 1,559 | 2,794 | 4,365 | 5,907 | 17,185 |

### Per-question results

| # | Status | Attempts | RAG (ms) | LLM (ms) | Val (ms) | Total (ms) | Question |
|---|---|---|---:|---:|---:|---:|---|
| 1 | ✅ | 1 | 101 | 4,343 | 1.9 | 4,454 | How many tickets are currently open? |
| 2 | ✅ | 1 | 237 | 1,200 | 0.3 | 1,439 | List all agents and their email addresses. |
| 3 | ✅ | 1 | 29 | 1,420 | 1.0 | 1,452 | What are the most recent 10 tickets created? |
| 4 | ✅ | 1 | 26 | 1,038 | 2.0 | 1,069 | How many tickets were closed last week? |
| 5 | ✅ | 1 | 8 | 1,127 | 0.6 | 1,139 | Show all customers from the United States. |
| 6 | ✅ | 1 | 48 | 2,740 | 3.0 | 2,794 | Which agent has resolved the most tickets this month? |
| 7 | ✅ | 1 | 29 | 1,633 | 2.0 | 1,667 | What is the average resolution time per ticket status? |
| 8 | ✅ | 1 | 55 | 2,337 | 2.4 | 2,397 | How many tickets per product category were opened in the last 30 days? |
| 9 | ✅ | 2 | 55 | 3,873 | 6.1 | 3,939 | List customers who have more than 5 open tickets. |
| 10 | ✅ | 2 | 61 | 4,206 | 4.3 | 4,276 | What percentage of tickets are escalated by priority level? |
| 11 | ✅ | 2 | 85 | 5,868 | 4.7 | 5,962 | List the top 5 customers by number of open tickets in the past 90 days… |
| 12 | ✅ | 1 | 54 | 3,880 | 3.0 | 3,939 | Which agents handled the most escalated tickets last quarter? |
| 13 | ✅ | 2 | 50 | 5,767 | 4.3 | 5,825 | For each customer tier, show the percentage of tickets that were escalated. |
| 14 | ✅ | 1 | 47 | 2,382 | 2.4 | 2,433 | Which product categories have the highest ticket reopen rate this year? |
| 15 | ✅ 🤖 | 3 | 100 | 18,870 | 9.4 | 19,012 | Which agents resolved the most tickets in the product categories with the highest reopen rate? |

> 🤖 = agentic ReAct loop triggered &nbsp;|&nbsp; **15/15 success rate** &nbsp;|&nbsp; Non-LLM p99 = 225 ms ✅ (target < 20,000 ms)

---


## Quick Start

```bash
uv sync                              # 1. install dependencies
ollama pull qwen2.5:7b               # 2. pull the LLM model
uv run python -m sql_agent.main      # 3. start the server (index builds on first run)
```

Then ask a question:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many tickets are currently open?"}'
```

Or open the Gradio UI at [http://localhost:8000/ui](http://localhost:8000/ui).

➡️ **Full setup guide with env vars, model options, and index rebuild:** [QUICKSTART.md](QUICKSTART.md)
