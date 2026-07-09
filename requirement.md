# Take-Home Assignment: Agentic AI Systems

## 1. Introduction

This take-home assignment consists of three independent parts designed to evaluate your ability to bridge research concepts, production-grade engineering, and practical system design in the context of Agentic AI systems.

**Parts:**
1. Agent Architecture & Retrieval Design
2. Production API & Performance Optimization

We understand the allocated time may not be sufficient to build a fully production-ready system. You are encouraged to prioritize **clarity of design**, **sound engineering judgment**, and **thoughtful trade-offs** over completeness.

You can use any AI Tools that you have handy to complete this assignment.

**Compute Expectations:**
This assignment is designed to be completed on a standard local development environment (CPU-only). Paid cloud compute or Colab Pro is not required.

Please document assumptions, limitations, and ideas for improvement you would pursue with more time.

---

## 2. Evaluation Criteria

Your submission will be evaluated based on:

| # | Criterion | Description |
|---|-----------|-------------|
| 1 | **System Design & Architecture** | Quality of modular design, clarity of RAG workflow, and reasoning behind failure handling and self-correction |
| 2 | **Retrieval Understanding** | Effective use of retrieval methods, embeddings, LLMs, and reasoning strategies |
| 3 | **Engineering Quality** | Code clarity, structure, maintainability, and adherence to software engineering best practices |
| 4 | **Performance & Scalability Awareness** | Understanding of latency, concurrency, and production constraints |
| 5 | **Critical Thinking & Trade-offs** | Ability to justify technical decisions and recognize limitations |
| 6 | **Documentation & Communication** | Clear explanations for both technical and non-technical stakeholders |

> Your participation in the next interview round will depend on the overall quality of your submission. All candidates will receive constructive feedback.

---

## Part 1: Agent Architecture & Retrieval Design

### Objective
Evaluate your ability to design a modular, self-correcting agent capable of handling multi-step reasoning queries over technical documents.

Self-correction may include techniques such as retrieval confidence checks, answer validation heuristics, fallback queries, or iterative re-retrieval.

### Instructions

**Data:** A dataset has been provided — `Customer Service Tables.xlsx`
- **Table Metadata** – Provides the metadata of each table
- **Scenarios** – Test cases the app will be tested against
- **`*_tbl`** – Different tables from which the query has to be generated

**Implement a modular agent architecture that:**
- Generates the necessary SQL & data for the questions mentioned in the scenarios
- Can detect when retrieved information does not sufficiently answer the user's question
- Re-plans or refines its retrieval or reasoning strategy ("self-correction")

**You are free to choose:**
- Any open-source or API-based LLM
- Any RAG frameworks like LangChain

**Notes:**
- The data is a sample; the outcome can just be a SQL query — no need for data processing
- A partial or simplified implementation is acceptable if clearly documented

---

## Part 2: Production API & Performance Optimization

### Objective
Assess your ability to move from prototype to production-oriented systems.

### Instructions

- **Provide a Deployment Architecture for Production**
- **Wrap your agent in an API** (e.g., FastAPI or gRPC):
  - Clean request/response contracts
  - Basic error handling
- **Latency target:** < 20s for retrieval and reasoning-preparation (excluding full LLM generation time)
- **Add a basic observability hook**, such as:
  - Latency tracking
  - Simple logging or metrics
  - Signals for retrieval quality degradation or drift

---

## Part 3: Ideas for Improvement

Provide your views on whether **Fine-Tuning can improve model accuracy & reduce response time**.
*(No code required — just an approach)*

---

## 3. What We Are NOT Expecting

- Fine-tuning large language models
- Large-scale distributed systems
- Perfect latency benchmarks on full LLM inference
- Enterprise-grade monitoring stacks

