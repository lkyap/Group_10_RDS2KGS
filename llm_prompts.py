"""
llm_prompts.py
   Converts mapping specification JSON files into LLM prompt text files.

 Description:
   - Reads all *_mapping.json files from: mapping_specs/
   - Builds a natural language prompt for each database schema
   - Saves them as text files in: llm_prompts/

 How to Run:
   1. Place this file in the project root.
   2. Make sure *_mapping.json files exist inside mapping_specs/.
   3. In VS Code, run this file.

 Output:
   - Creates llm_prompts/ folder.
   - Generates one *_llm_prompt.txt file for each *_mapping.json file.

Note: Run the llm_prompts.py after mapping_specs.py.   
"""
import json
from pathlib import Path
 
BASE_DIR = Path(__file__).parent
MAPPING_INPUT = BASE_DIR / "mapping_specs"
LLM_PROMPT_OUTPUT = BASE_DIR / "llm_prompts"
LLM_PROMPT_OUTPUT.mkdir(parents=True, exist_ok=True)
 
mapping_files = list(MAPPING_INPUT.glob("*_mapping.json"))
 
for mf in mapping_files:
    with open(mf, "r", encoding="utf-8") as f:
        mapping = json.load(f)
 
    prompt = f"""
You are a data modeling assistant. You are given a database schema.
Nodes represent tables with columns and primary keys.
Edges represent foreign key relationships.
 
Your task is to:
1. Identify potential fact tables
2. Identify dimension tables
3. Suggest a star-schema / dimensional model
4. Describe key relationships
 
Database ID: {mapping['db_id']}
Nodes: {json.dumps(mapping['nodes'], indent=2)}
Edges: {json.dumps(mapping['edges'], indent=2)}
"""
 
    prompt_file = LLM_PROMPT_OUTPUT / f"{mapping['db_id']}_llm_prompt.txt"
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
 
    print(f"LLM prompt saved: {prompt_file}")