"""
schema_to_graph.py
    Converts schema.json files (from extract.ipynb output) into graph JSON files.

Input Folder:
    artifacts/runs/spider/<db_id>/schema.json

Output Folder:
    artifacts/runs/graph_schemas/<db_id>_graph.json

How to run:
1. Place this file in the project root.
2. Make sure all schema.json files are inside artifacts/runs/spider/
3. In VS Code, run this file.
4. The generated *_graph.json files will appear in artifacts/runs/graph_schemas/

Note: Run the schema_to_graph.py after extract.ipynb and before mapping_specs.py.
"""
import json
from pathlib import Path

# Path where extract.ipynb saved schema.json files
SCHEMA_ROOT = Path("/artifacts/runs/spider")
GRAPH_OUTPUT = SCHEMA_ROOT.parent / "graph_schemas"
GRAPH_OUTPUT.mkdir(parents=True, exist_ok=True)

# Find all schema.json files in the subfolders
schema_files = list(SCHEMA_ROOT.rglob("schema.json"))

for sf in schema_files:
    with open(sf, "r", encoding="utf-8") as f:
        schema = json.load(f)

    db_id = schema["db_id"]
    tables = schema["tables"]
    foreign_keys = schema["foreign_keys"]

    # Build nodes
    nodes = []
    for t in tables:
        nodes.append({
            "id": t["name"],
            "columns": [c["name"] for c in t["columns"]],
            "primary_keys": t["primary_key"]
        })

    # Build edges
    edges = []
    for fk in foreign_keys:
        edges.append({
            "from": fk["from_table"],
            "to": fk["to_table"],
            "from_column": fk["from_column"],
            "to_column": fk["to_column"]
        })

    graph = {
        "db_id": db_id,
        "nodes": nodes,
        "edges": edges
    }

    out_file = GRAPH_OUTPUT / f"{db_id}_graph.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    print(f"Graph saved: {out_file}")
