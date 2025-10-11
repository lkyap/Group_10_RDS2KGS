"""
mapping_to_yfiles.py
   Converts mapping specification JSON files into yFiles-compatible graph JSON files.

 Description:
   - Reads all *_mapping.json files from: mapping_specs/
   - Converts tables (nodes) and foreign key links (edges)
   - Saves them as yFiles-ready graph JSON files in: yfiles_graphs/

 How to Run:
   1. Place this file in the project root.
   2. Make sure *_mapping.json files exist inside mapping_specs/.
   3. In VS Code, run this file.

 Output:
   - Creates yfiles_graphs/ folder.
   - Generates one *_yfiles.json file for each *_mapping.json file.

Note: Run the mapping_to_yFiles.py after llm_prompts.py.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
MAPPING_INPUT = BASE_DIR / "mapping_specs"
YFILES_OUTPUT = BASE_DIR / "yfiles_graphs"
YFILES_OUTPUT.mkdir(parents=True, exist_ok=True)

# Get all mapping JSON files
mapping_files = list(MAPPING_INPUT.glob("*_mapping.json"))
print(f"Found {len(mapping_files)} mapping files")

for mf in mapping_files:
    with open(mf, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    db_id = mapping["db_id"]

    # Build yFiles-compatible graph structure
    ygraph = {
        "id": db_id,
        "nodes": [],
        "edges": []
    }

    # Create nodes
    for node in mapping["nodes"]:
        ygraph["nodes"].append({
            "id": node["id"],
            "label": f"{node['id']}\\nPK: {', '.join(node['primary_keys'])}"
        })

    # Create edges
    for edge in mapping["edges"]:
        ygraph["edges"].append({
            "from": edge["from"],
            "to": edge["to"],
            "label": f"{edge['from_column']} → {edge['to_column']}"
        })

    # Save to JSON
    out_file = YFILES_OUTPUT / f"{db_id}_yfiles.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(ygraph, f, indent=2)

    print(f"yFiles graph saved: {out_file}")
