SQL Agent — Latency Benchmark
Questions : 15  |  Target non-LLM p99 < 20s
Model     : qwen2.5:7b

Loading weights: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 103/103 [00:00<00:00, 14137.02it/s]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
Key                     | Status     |  | 
------------------------+------------+--+-
embeddings.position_ids | UNEXPECTED |  | 

Notes:
- UNEXPECTED    :can be ignored when loading from different task/architecture; not ok if you expect identical arch.
Index ready — 9 tables

```
#    St   Att     RAG     LLM    Val   nonLLM    Total  Question
────────────────────────────────────────────────────────────────────────────────────────────────────
1    ok 1      101   4343   1.9     111    4454      How many tickets are currently open?
2    ok 1      237   1200   0.3     239    1439      List all agents and their email addresses.
3    ok 1       29   1420   1.0      31    1452      What are the most recent 10 tickets created?
4    ok 1       26   1038   2.0      31    1069      How many tickets were closed last week?
5    ok 1        8   1127   0.6      11    1139      Show all customers from the United States.
6    ok 1       48   2740   3.0      54    2794      Which agent has resolved the most tickets this month?
7    ok 1       29   1633   2.0      34    1667      What is the average resolution time per ticket status?
8    ok 1       55   2337   2.4      60    2397      How many tickets per product category were opened in the las…
[validate] FAIL — unknown table: customers_tbl
9    ok 2       55   3873   6.1      66    3939      List customers who have more than 5 open tickets.
[validate] FAIL — unknown table: priorities_tbl
10   ok 2       61   4206   4.3      69    4276      What percentage of tickets are escalated by priority level?
[validate] FAIL — unknown table: customers_tbl
11   ok 2       85   5868   4.7      94    5962      List the top 5 customers by number of open tickets in the pa…
12   ok 1       54   3880   3.0      59    3939      Which agents handled the most escalated tickets last quarter…
[validate] FAIL — unknown table: customers_tbl
13   ok 2       50   5767   4.3      58    5825      For each customer tier, show the percentage of tickets that …
14   ok 1       47   2382   2.4      52    2433      Which product categories have the highest ticket reopen rate…
[validate] FAIL — unknown table: categories_tbl
[validate] FAIL — unknown table: agents_tbl
[validate] FAIL — unknown table: agents_tbl
15   ok 3      100  18870   9.4     141   19012  [A] Which agents resolved the most tickets in the product catego…

────────────────────────────────────────────────────────────────────────────────────────────────────
  Percentile Summary  (all times in ms)
────────────────────────────────────────────────────────────────────────────────────────────────────
  Metric                         avg          p25          p50          p75          p90          p99
  ────────────────────────────────────────────────────────────────────────────────────────────
  RAG retrieval          avg=     66  p25=     38  p50=     54  p75=     73  p90=    100  p99=    218  ms
  LLM calls (total)      avg=   4046  p25=   1526  p50=   2740  p75=   4274  p90=   5828  p99=  17050  ms
  Validation             avg=      3  p25=      2  p50=      2  p75=      4  p90=      6  p99=      9  ms
  Agentic loop (1 runs)  avg=   7511  p25=   7511  p50=   7511  p75=   7511  p90=   7511  p99=   7511  ms
  ────────────────────────────────────────────────────────────────────────────────────────────
  Non-LLM latency        avg=     74  p25=     43  p50=     59  p75=     82  p90=    129  p99=    225  ms  ← ✓ PASS (target <20s)
  Overall latency        avg=   4120  p25=   1559  p50=   2794  p75=   4365  p90=   5907  p99=  17185  ms

  Runs: 15  |  OK: 15  |  Fail: 0  |  Agentic triggered: 1
────────────────────────────────────────────────────────────────────────────────────────────────────

```