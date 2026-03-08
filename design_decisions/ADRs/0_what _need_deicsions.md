- 1. Does this can be done simply by a pipeline / deterministic way - instead of agents ? 
- 2. Do we need a RAG ehre ?
    - what is the mebedding method gonna use -> have sentence transformer mini in mind. 
    - if yes, what vector-dp gonna use
    - what chunking methof - one per table -> 
    - what retrival method - cosine will work or something else here.
- 3. what LLM model to choose, how are you going to evaluate the model?
- 4. do we need cache ? - would be helpful because in a company it is expeted to have a repeated same questions asked over the perido or by different people.
    - If I decide to do it, then cache sotrage method ?
    - cache storage duration ? 
    - rollup cache or window cache ?
- 5. how we are going to decide the agent-looping ? max limit and checks
- 6. Prompt Injection _ .ways of prodecting us.





tables are there (table + meta-data about the tables)
|
User will ask a NL question 
|
get the table meta-data 
|
Filter them if possible
| 
create the prompt 
|
ask the LLM to generate the query
| 
self-correction

how it becomes a agent 
