
# Data Science Capstone Project - RDS to KGS

Total 5 scripts 

1. SchemaDataExtractor.py
2. LLMPrompt.py
3. LLMAgent.py
4. kgscreate.py
5. main.py

Before running the main.py, do the following steps:

1. Save all the files under the same folder. 
2. Set your API_KEY in the local environment. In your VScode terminal, type in " $env:OPENAI_API_KEY = 'put your api key here' " . Remove the double quotes when you key into terminal.
3. Under main.py, replace the password of your neo4j.
4. Replace the database directory to the database that you would like to convert
5. You should be running smoothly if you did the above steps correctly.

To view the metagraph, do the following
1. Open Google Chrome, type in localhost:7474
2. Login with your password for Neo4j
3. Under neo4j database, you should see the metagraph
4. If you face error, create a new database in neo4j, and remember the password and the host. Then use the same host after you visited localhost:7474. 


# Team contribution

| Member Name | Student ID | Tasks for the project | Skills contributed to the team & project | 
| :------- | :------: | -------: | -------: |
| Liang Kooi Yap | 24332936 | Completed end to end pipeline by using LLM prompt (Approach 2), Completed evaluation section for schema completeness and relationship completeness, Visualization of metagraph using Neo4j, documentation in Github | Organize & host client meetings, tracking overall project progress, researching skills to solve the problem, provide guidance to other team members | 
| Shijin Wang | 24417624 | Virsualisation & merged the upstream components and visualization into a single end-to-end application | Front-end engineering (Vue, yFiles), graph visualization, and layout tuning. Performance optimisation (incremental rendering, light client layout), debugging, and error handling. Clear communication & demos. Report & presentation writing.|
| Felix Mavrodoglu | 23720305 | Built SQLite schema extraction and validation scripts, set up Git LFS for large Spider dataset, delegated and coordinated tasks for Approach 1, attended client meetings and led presentations | Python scripting, Git LFS, JSON handling, workflow organisation and coordination, presentation and client communication |
| Evanna Susan | 24486841 | I contributed to the rule-based schema-to-graph pipeline by developing mapping_specs.py to standardize node IDs, manage metadata, and ensure foreign key fidelity, and to llm_prompts.py by designing schema summarization logic for LLM enrichment. I also identified potential data biases affecting knowledge graph construction.| Python, JSON handling, critical thinking, collaboration, and attention to detail. |
| Diksha Sagar | 24353947 | Designed and implemented User-Question Evaluation (SQL↔Cypher) to check answer parity on Spider DBs (eval_user_questions_auto.py); authored schema-constrained SQL→Cypher prompts for deterministic translation; built Neo4j KG loader & verification for labels/properties (load_kgs_to_neo4j.py); produced run logs, figures, and presentation content | Python (sqlite3, pandas), Neo4j/Cypher, schema-grounded LLM prompts, experiment design & result canonicalisation, reproducible logging, documentation & presentation |


