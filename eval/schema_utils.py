
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any

def load_tables_json(tables_json_path: Path) -> List[Dict[str, Any]]:
    data = tables_json_path.read_text(encoding="utf-8")
    import json
    return json.loads(data)

def build_schema_block_for_db(db_id: str, tables_index: Dict[str, Dict[str, Any]]) -> str:
    """
    Build a human-readable schema block:
      - Node labels are PascalCase(table_name)
      - Relationship type is UPPER_SNAKE of parent (referenced) table name
        (direction: child -> parent)
    """
    meta = tables_index[db_id]
    tables = meta["table_names_original"]
    columns = meta["column_names_original"]  # [ [table_idx, col_name], ... ]
    col_table = [t for t, _c in columns]     # table index per column
    fks = meta["foreign_keys"]               # [ [col_idx_parent, col_idx_child], ...]

    # columns per table
    table_cols: Dict[int, List[str]] = {i: [] for i in range(len(tables))}
    for ci, (ti, cname) in enumerate(columns):
        if ti == -1:
            continue
        table_cols[ti].append(cname)

    # nodes
    nodes_lines = []
    for ti, tname in enumerate(tables):
        cols = table_cols.get(ti, [])
        cols_str = ", ".join(cols) if cols else "(no columns?)"
        nodes_lines.append(f"- {to_pascal(tname)}({cols_str})")

    # edges
    edges_lines = []
    for (p_idx, c_idx) in fks:
        p_ti = col_table[p_idx]
        c_ti = col_table[c_idx]
        if p_ti == -1 or c_ti == -1:
            continue
        p_table = to_pascal(tables[p_ti])
        c_table = to_pascal(tables[c_ti])
        rel = to_upper_snake(tables[p_ti])  # type from parent table
        edges_lines.append(f"- ({c_table})-[:{rel}]->({p_table})")

    schema = [
        "Nodes (tables):",
        *nodes_lines,
        "",
        "Edges (foreign keys):" if edges_lines else "Edges (foreign keys): (none)",
        *(edges_lines if edges_lines else []),
    ]
    return "\n".join(schema)

def to_pascal(name: str) -> str:
    parts = [p for p in name.replace('-', '_').split('_') if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)

def to_upper_snake(name: str) -> str:
    return "_".join([p.upper() for p in name.replace('-', '_').split('_') if p])
