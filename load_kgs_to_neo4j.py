#!/usr/bin/env python3
# Load all KGs from kgs_schema_generated/ + kgs_data_generated/ into Neo4j.
# - Uses node keys if provided in schema; otherwise infers *_id/ID/id.
# - SET n += $props so properties with spaces are handled.
# - Builds relationships using source/target join columns from schema.

# How to run : python load_kgs_to_neo4j.py --wipe --only bird_cars,cinema
# For user questions eval, load bird_cars and cinema only.
# (Remove --wipe if don’t want to clear  DB first.)

import os, re, json, argparse
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

SCHEMA_DIR = Path("kgs_schema_generated")
DATA_DIR   = Path("kgs_data_generated")
ID_HINT = re.compile(r"(?:^id$|_id$|Id$|ID$)", re.I)

def jflex_text(p: Path):
    raw = p.read_text(encoding="utf-8")
    try: return json.loads(raw)
    except json.JSONDecodeError: return json.loads(json.loads(raw))

def node_label(n: dict):
    return n.get("id") or n.get("entity") or n.get("label") or n.get("name")

def node_keys(n: dict):
    k = n.get("key")
    if not k: return []
    if isinstance(k, str):
        return [x.strip() for x in k.split(",") if x.strip()]
    if isinstance(k, (list, tuple)):
        return [str(x) for x in k if str(x).strip()]
    return []

def infer_keys(n: dict):
    names = []
    for p in (n.get("properties") or []):
        names.append(p.get("name") if isinstance(p, dict) else str(p))
    for name in names:
        if name and ID_HINT.search(name):
            return [name]
    return []

def get_edges(schema: dict):
    return schema.get("edges") or schema.get("relationships") or []

def get_nodes(schema: dict):
    return schema.get("nodes") or schema.get("entities") or []

def get_edge_field(e: dict, *names):
    for k in names:
        if e.get(k) is not None: return e.get(k)
    return None

def load_one(driver, schema_path: Path):
    base = schema_path.stem.replace("_kgs","")
    data_path = DATA_DIR / f"{base}_kgs_data.json"
    if not data_path.exists():
        print(f"⚠️  No data for {schema_path.name}, skipping")
        return
    schema = jflex_text(schema_path)
    data   = jflex_text(data_path)

    nodes = get_nodes(schema)
    edges = get_edges(schema)

    label_keys = {}

    with driver.session() as s:
        # nodes
        for n in nodes:
            label = node_label(n)
            if not label: 
                continue
            k = node_keys(n) or infer_keys(n)
            label_keys[label] = k

            rows = data.get(label) or []
            for r in rows:
                if k:
                    pairs = [f"`{col}`: $k{i}" for i, col in enumerate(k)]
                    params = {f"k{i}": r.get(col) for i, col in enumerate(k)}
                    cy = f"MERGE (n:`{label}` {{{', '.join(pairs)}}}) SET n += $props"
                    s.run(cy, **params, props=r)
                else:
                    s.run(f"CREATE (n:`{label}`) SET n += $props", props=r)

        # relationships
        for e in edges:
            src_label = get_edge_field(e, "source", "Source_Entity", "Source_Table")
            tgt_label = get_edge_field(e, "target", "Target_Entity", "Target_Table")
            rel_type  = get_edge_field(e, "relationship", "Relationship", "type") or "REL"
            src_col   = get_edge_field(e, "source_column", "Source_Column")
            tgt_col   = get_edge_field(e, "target_column", "Target_Column")
            if not (src_label and tgt_label and src_col and tgt_col):
                continue

            src_keys = label_keys.get(src_label, [])
            rows = data.get(src_label) or []
            for r in rows:
                if src_col not in r:
                    continue

                tgt_match = f"(b:`{tgt_label}`) WHERE b.`{tgt_col}` = $tgt_val"

                if src_keys:
                    conds = " AND ".join([f"a.`{k}` = $sk{i}" for i,k in enumerate(src_keys)])
                    params = {**{f"sk{i}": r.get(k) for i,k in enumerate(src_keys)},
                              "tgt_val": r.get(src_col)}
                    src_match = f"(a:`{src_label}`) WHERE {conds}"
                else:
                    params = {"src_val": r.get(src_col), "tgt_val": r.get(src_col)}
                    src_match = f"(a:`{src_label}`) WHERE a.`{src_col}` = $src_val"

                cy = f"MATCH {src_match} MATCH {tgt_match} MERGE (a)-[:`{rel_type}`]->(b)"
                s.run(cy, **params)

    print(f"✅ Loaded {schema_path.name} + {data_path.name}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Comma-separated DB ids to load (e.g., bird_cars,cinema)")
    ap.add_argument("--wipe", action="store_true", help="WIPE database before loading")
    ap.add_argument("--uri", help="Override NEO4J_URI")
    ap.add_argument("--user", help="Override NEO4J_USER")
    ap.add_argument("--password", help="Override NEO4J_PASSWORD")
    args = ap.parse_args()

    load_dotenv("cred.env")
    uri = args.uri or os.getenv("NEO4J_URI") or os.getenv("NEO_4J_URI")
    user = args.user or os.getenv("NEO4J_USER")
    pwd  = args.password or os.getenv("NEO4J_PASSWORD")
    assert uri and user and pwd, "Set NEO4J_* env vars or pass --uri/--user/--password"

    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    if args.wipe:
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        print("🧹 Wiped Neo4j database")

    only_set = set(x.strip() for x in (args.only.split(",") if args.only else []) if x.strip())

    for sp in sorted(SCHEMA_DIR.glob("*_kgs.json")):
        db_id = sp.stem.replace("_kgs","").replace("spider_","")
        if only_set and db_id not in only_set:
            continue
        load_one(driver, sp)

    driver.close()
    print("Done.")

if __name__ == "__main__":
    main()

