- Prompt injection -> for safely only allowing select SQL queries.
    - Do analysis for more injection ways and solution specific to each one of them.
- If needed, go to ANN (vector DB) approach
- Plan a effecient re-indexing process.
    - becuase while doing re-try we can do increasemental re-index. only change the modified tables. Need time to implement this.
- Analysis to choose what model wil be performing better.
    - I need to generate and validate the GT SQL for better mmodel evaluation.
- Prompt Tuning
- cache -> if we have more time, we can analysis the cache hit rate and time duration what will be helpful and everything. -> I feel this wil be a huge cost and time saver.
    - can think of better retrival and storage here.



**-> need to update the design if you make some change.**
- production diagram need improvement.