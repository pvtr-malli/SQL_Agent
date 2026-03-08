# ADR-008: Caching Strategy Decision

## Status

Accepted

---

## Context

Can we do the job by simply a determistic pipeline, not by agents ? 

## Decision

- **Take the agentic way **

## Rationale

The simple pipeline would be something like this 
```
Question → retrieve schema → generate SQL → validate the SQL -> recall the llm -> return
```

- But this is not powerful enough to validate the output query, **Table selection is non-deterministic** -> we need something which checks the output SQL and take the reviews and decide to re-run the pipeline.
- Questions are multi-step — "find agents who received escalations AND have CSAT below 3" requires the agent to reason across 4 tables. It needs to plan, not just need hte question and run.

So how the agentic flow will be:
```
Question
  │
  ▼
[Plan] Which tables do I need?
  │
  ▼
[Act] Generate SQL using retrieved schema
  │
  ▼
[Observe] Is this SQL valid? Does it reference real columns?
  │
  ├── YES → return SQL
  │
  └── NO → [Reason] What went wrong? Wrong table? Bad join?
              │
              ▼
           [Re-plan] Fix it and try again (up to 3x)
```