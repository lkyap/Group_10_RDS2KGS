#!/usr/bin/env python3
"""
Generate mapping specifications from graph JSON files.

This script reads *_graph.json files (Spider DB schema graphs)
and outputs *_mapping.json files with nodes and foreign key edges.

Usage:
    python generate_mapping_specs.py --input /path/to/graph_schemas --output /path/to/mapping_specs
"""

import json
from pathlib import Path
import argparse


def generate_mapping_specs(graph_input: Path, mapping_output: Path) -> None:
    """
    Convert graph JSON files into mapping specifications.

    Args:
        graph_input (Path): Directory containing *_graph.json files.
        mapping_output (Path): Directory to save *_mapping.json files.
    """
    mapping_output.mkdir(parents=True, exist_ok=True)

    graph_files = list(graph_input.glob("*_graph.json"))
    if not graph_files:
        print(f"No graph files found in {graph_input}")
        return

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
        for node in graph.get("nodes", []):
            mapping_spec["nodes"].append({
                "id": node["id"],
                "columns": node["columns"],
                "primary_keys": node["primary_keys"]
            })

        # Edges: from foreign keys
        for edge in graph.get("edges", []):
            mapping_spec["edges"].append({
                "from": edge["from"],
                "to": edge["to"],
                "from_column": edge["from_column"],
                "to_column": edge["to_column"],
                "type": "foreign_key"
            })

        out_file = mapping_output / f"{graph['db_id']}_mapping.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(mapping_spec, f, indent=2)

        print(f"Mapping spec saved: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate mapping specs from graph JSON files.")
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to the folder containing *_graph.json files"
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Path to the folder where *_mapping.json files will be saved"
    )
    args = parser.parse_args()

    generate_mapping_specs(args.input, args.output)


if __name__ == "__main__":
    main()
