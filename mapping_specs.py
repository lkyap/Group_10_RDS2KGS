"""
graph_to_mapping.py
   Converts Spider graph schema JSON files into mapping specs.

 Description:
   - Reads all *_graph.json files from: artifacts/runs/graph_schemas
   - Extracts table nodes and foreign key edges
   - Creates mapping specification JSON files
   - Saves them into: mapping_specs/

 How to Run:
   1. Place this file in the project root.
   2. Make sure *_graph.json files exist inside artifacts/runs/graph_schemas.
   3. In VS Code, run this file.

 Output:
   - Creates mapping_specs/ folder.
   - Generates one *_mapping.json file for each *_graph.json file.
"""
import json
from pathlib import Path
 
BASE_DIR = Path(__file__).parent
GRAPH_INPUT = BASE_DIR / "artifacts" / "runs" / "graph_schemas"
MAPPING_OUTPUT = BASE_DIR / "mapping_specs"
MAPPING_OUTPUT.mkdir(parents=True, exist_ok=True)
 
graph_files = list(GRAPH_INPUT.glob("*_graph.json"))
 
for gf in graph_files:
    with open(gf, "r", encoding="utf-8") as f:
        graph = json.load(f)
 
    # Mapping spec
    mapping_spec = {
        "db_id": graph["db_id"],
        "nodes": [],
        "edges": []
    }
 
    # Nodes: pick table name + primary key as node identifier
    for node in graph["nodes"]:
        mapping_spec["nodes"].append({
            "id": node["id"],
            "columns": node["columns"],
            "primary_keys": node["primary_keys"]
        })
 
    # Edges: from foreign keys
    for edge in graph["edges"]:
        mapping_spec["edges"].append({
            "from": edge["from"],
            "to": edge["to"],
            "from_column": edge["from_column"],
            "to_column": edge["to_column"],
            "type": "foreign_key"
        })
 
    out_file = MAPPING_OUTPUT / f"{graph['db_id']}_mapping.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(mapping_spec, f, indent=2)
 
    print(f"Mapping spec saved: {out_file}")