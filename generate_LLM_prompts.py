import json
from pathlib import Path

def generate_llm_prompts(mapping_input: Path, llm_prompt_output: Path) -> None:
    """Generate LLM prompt text files from mapping spec JSONs."""
    llm_prompt_output.mkdir(parents=True, exist_ok=True)
    mapping_files = list(mapping_input.glob("*_mapping.json"))

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

        prompt_file = llm_prompt_output / f"{mapping['db_id']}_llm_prompt.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        print(f"LLM prompt saved: {prompt_file}")


if __name__ == "__main__":
    MAPPING_INPUT = Path("../data/mapping_specs")
    LLM_PROMPT_OUTPUT = Path("../data/llm_prompts")
    generate_llm_prompts(MAPPING_INPUT, LLM_PROMPT_OUTPUT)
