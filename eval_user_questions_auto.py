#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-evaluator for user questions (RDS vs KG)

How to run:
# both at once (since dev_full.json only has these two, --all is fine)
python eval_user_questions_auto.py --all --per 10
# or individually
python eval_user_questions_auto.py --db bird_cars --per 10
python eval_user_questions_auto.py --db cinema --per 10

What it does:
1) Read SQL from Spider (dev.json or spider.zip).
2) Read your KG schema from kgs_schema_generated/spider_<db>_kgs.json
   to know the exact node labels, properties, and relationship types.
3) Use an LLM to translate each SQL -> Cypher for Neo4j (guided by the schema).
4) Run SQL on SQLite (RDS ground truth) and Cypher on Neo4j (KG loaded from
   kgs_schema_generated/* and kgs_data_generated/*).
5) Compare the two result sets and write a pass/fail report.

Outputs:
- runs/auto_eval/results.csv         (summary)
- runs/auto_eval/details.jsonl       (sample rows)
- runs/auto_eval/cyphers_<db>.jsonl  (SQL -> generated Cypher)

Prereqs:
- cred.env with OPENAI_API_KEY, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
- Neo4j already loaded from kgs_schema_generated/* + kgs_data_generated/*
- Spider dev.json or spider.zip
"""

import os, json, sqlite3, csv, zipfile, re, argparse, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase

REPO = Path(__file__).resolve().parent
RUN_DIR = REPO / "runs" / "auto_eval"
RUN_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = RUN_DIR / "results.csv"

SPIDER_DIR = REPO / "data" / "spider"
SPIDER_ZIP = REPO / "data" / "spider.zip"
KGS_DIR = REPO / "kgs_schema_generated"
DB_DIR = REPO / "db_dataset"

@dataclass
class Item:
    db_id: str
    question: str
    sql: str

def jflex(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(json.loads(raw))

def load_spider_dev() -> List[Dict[str, Any]]:
    p = SPIDER_DIR / "dev.json"
    if p.exists():
        return jflex(p.read_text(encoding="utf-8"))
    if SPIDER_ZIP.exists():
        with zipfile.ZipFile(SPIDER_ZIP, "r") as z:
            cands = [n for n in z.namelist() if n.endswith("dev.json")]            or [n for n in z.namelist() if "dev.json" in n]
            if not cands:
                raise FileNotFoundError("dev.json not found in data/spider.zip")
            return jflex(z.read(cands[0]).decode("utf-8"))
    raise FileNotFoundError("Spider dev not found. Put dev.json in data/spider/ or spider.zip in data/.")

def get_db_ids_from_kgs() -> List[str]:
    ids = []
    for p in KGS_DIR.glob("*_kgs.json"):
        name = p.stem.replace("_kgs","");
        name = name.replace("spider_","");
        ids.append(name)
    return sorted(set(ids))

def pick_items(dev: List[Dict[str, Any]], db_id: str, per: int) -> List[Item]:
    rows = [r for r in dev if r.get("db_id")==db_id]
    out: List[Item] = []
    for r in rows:
        q = (r.get("question") or "").strip()
        sql = (r.get("query") or "").strip()
        sl = sql.lower()
        if not sl.startswith(("select","with")):
            continue
        if any(tok in sl for tok in (" union "," intersect "," except ")):
            continue
        out.append(Item(db_id=db_id, question=q, sql=sql))
        if len(out) >= per:
            break
    return out

def sqlite_path(db_id: str) -> Path:
    p1 = DB_DIR / f"spider_{db_id}.sqlite"
    if p1.exists(): return p1
    p2 = DB_DIR / f"{db_id}.sqlite"
    if p2.exists(): return p2
    raise FileNotFoundError(f"SQLite DB for {db_id} not found under {DB_DIR}")

def rds_query(sqlite_p: Path, sql: str) -> Tuple[List[str], List[Tuple[str,...]]]:
    con = sqlite3.connect(str(sqlite_p))
    try:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = rows[0].keys() if rows else [d[0] for d in cur.description] if cur.description else []
        data = [tuple("" if v is None else str(v) for v in (row[c] for c in cols)) for row in rows]
        data.sort()
        return list(cols), data
    finally:
        con.close()

def load_schema_json(db_id: str) -> Dict[str, Any]:
    for name in (f"spider_{db_id}_kgs.json", f"{db_id}_kgs.json"):
        p = KGS_DIR / name
        if p.exists():
            return jflex(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"KG schema JSON not found for {db_id} in {KGS_DIR}")

def cypher_from_llm(client: OpenAI, model: str, kg_schema: Dict[str, Any], sql: str) -> str:
    nodes = kg_schema.get("nodes") or kg_schema.get("entities") or []
    edges = kg_schema.get("edges") or kg_schema.get("relationships") or []
    schema_summary = {
        "nodes": [
            {
                "label": n.get("id") or n.get("entity") or n.get("label") or n.get("name"),
                "key": n.get("key"),
                "properties": [ (p.get("name") if isinstance(p,dict) else p) for p in (n.get("properties") or []) ]
            } for n in (nodes if isinstance(nodes, list) else [])
        ],
        "edges": [
            {
                "source": e.get("source") or e.get("Source_Entity") or e.get("Source_Table"),
                "target": e.get("target") or e.get("Target_Entity") or e.get("Target_Table"),
                "type":   e.get("relationship") or e.get("Relationship") or e.get("type"),
                "source_column": e.get("source_column") or e.get("Source_Column"),
                "target_column": e.get("target_column") or e.get("Target_Column"),
            } for e in (edges if isinstance(edges, list) else [])
        ]
    }
    system = (
        "You are a precise SQL->Cypher translator for Neo4j.\n"
        "You MUST use ONLY the provided node labels, relationship types, and property names.\n"
        "Return ONE Cypher query only. No comments, no fences."
    )
    user = (
        "Knowledge-graph schema:\n" + json.dumps(schema_summary, indent=2)
        + "\n\nTranslate this SQL (SQLite semantics) into Cypher for Neo4j.\n"
          "Rules:\n"
          "- Use exact labels from nodes[*].label.\n"
          "- Use exact property names listed.\n"
          "- For joins, follow edges: source_column on source node equals target_column on target node.\n"
          "- Use DISTINCT/aggregation to match SQL. Preserve ORDER BY and LIMIT.\n"
          "- Return ONLY the Cypher statement.\n\n"
          f"SQL:\n{sql}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.0,
    )
    text = resp.choices[0].message.content.strip()
    text = re.sub(r"^```(?:cypher)?\s*|\s*```$","",text, flags=re.I|re.M).strip()
    parts = [p for p in re.split(r";\s*\n?", text) if p.strip()]
    return parts[0]

def run_cypher(driver, cypher: str) -> Tuple[List[str], List[Tuple[str,...]]]:
    with driver.session() as session:
        result = session.run(cypher)
        records = list(result)
        if not records:
            return [], []
        keys = list(records[0].keys())
        rows = []
        for rec in records:
            row = []
            for k in keys:
                v = rec[k]
                try:
                    if hasattr(v, "labels"):   # Node
                        row.append(json.dumps({"labels": sorted(list(v.labels)), **dict(v)}, sort_keys=True))
                    elif hasattr(v, "type"):   # Relationship
                        row.append(json.dumps({"type": v.type, **dict(v)}, sort_keys=True))
                    else:
                        row.append("" if v is None else str(v))
                except Exception:
                    row.append("" if v is None else str(v))
            rows.append(tuple(row))
        rows.sort()
        return keys, rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="Single db_id (e.g., cinema)")
    ap.add_argument("--all", action="store_true", help="Evaluate all db_ids from kgs_schema_generated")
    ap.add_argument("--per", type=int, default=10, help="Questions per DB")
    ap.add_argument("--model", default="gpt-4o-mini", help="OpenAI chat model to use")
    args = ap.parse_args()

    if not args.db and not args.all:
        print("Specify --db <name> or --all"); sys.exit(1)

    load_dotenv(REPO / "cred.env")
    api_key = os.getenv("OPENAI_API_KEY")
    neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO_4J_URI")
    neo4j_user = os.getenv("NEO4J_USER")
    neo4j_pass = os.getenv("NEO4J_PASSWORD")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set (cred.env)")
    if not (neo4j_uri and neo4j_user and neo4j_pass):
        raise SystemExit("NEO4J_* not set (cred.env)")

    client = OpenAI(api_key=api_key)
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

    dev = load_spider_dev()
    db_ids = get_db_ids_from_kgs() if args.all else [args.db]
    db_ids = [d for d in db_ids if any(r.get("db_id")==d for r in dev)]
    if not db_ids:
        raise SystemExit("No matching db_ids between kgs_schema_generated and Spider dev.json")

    write_header = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fcsv:
        w = csv.writer(fcsv)
        if write_header:
            w.writerow(["db_id","ok","rds_rows","kg_rows","note","question","sql","cypher"])

        for db_id in db_ids:
            items = pick_items(dev, db_id, args.per)
            if not items:
                print(f"[{db_id}] No items picked."); continue

            schema = load_schema_json(db_id)
            cypher_out = (RUN_DIR / f"cyphers_{db_id}.jsonl").open("a", encoding="utf-8")
            details_out = (RUN_DIR / "details.jsonl").open("a", encoding="utf-8")

            sqlite_p = sqlite_path(db_id)
            print(f"\n=== {db_id} : {len(items)} questions ===")

            for it in items:
                # SQLite
                try:
                    r_cols, r_rows = rds_query(sqlite_p, it.sql)
                except Exception as e:
                    note = f"RDS_ERROR: {e}"
                    w.writerow([db_id, False, 0, 0, note, it.question, it.sql, ""])
                    details_out.write(json.dumps({"db_id":db_id,"question":it.question,"sql":it.sql,"error":note})+"\n")
                    continue

                # Generate Cypher
                try:
                    cypher = cypher_from_llm(client, args.model, schema, it.sql)
                except Exception as e:
                    note = f"LLM_ERROR: {e}"
                    w.writerow([db_id, False, len(r_rows), 0, note, it.question, it.sql, ""])
                    details_out.write(json.dumps({"db_id":db_id,"question":it.question,"sql":it.sql,"error":note})+"\n")
                    continue

                # Execute Cypher
                try:
                    k_cols, k_rows = run_cypher(driver, cypher)
                except Exception as e:
                    note = f"KG_EXEC_ERROR: {e}"
                    w.writerow([db_id, False, len(r_rows), 0, note, it.question, it.sql, cypher])
                    details_out.write(json.dumps({"db_id":db_id,"question":it.question,"sql":it.sql,"cypher":cypher,"error":note})+"\n")
                    cypher_out.write(json.dumps({"db_id":db_id,"sql":it.sql,"cypher":cypher})+"\n")
                    continue

                ok = (r_rows == k_rows)
                note = "" if ok else "mismatch"
                w.writerow([db_id, ok, len(r_rows), len(k_rows), note, it.question, it.sql, cypher])
                details_out.write(json.dumps({
                    "db_id": db_id,
                    "question": it.question,
                    "sql": it.sql,
                    "cypher": cypher,
                    "rds_cols": r_cols, "rds_rows": r_rows[:5],
                    "kg_cols": k_cols, "kg_rows": k_rows[:5],
                    "ok": ok, "note": note
                })+"\n")
                cypher_out.write(json.dumps({"db_id":db_id,"sql":it.sql,"cypher":cypher})+"\n")

            cypher_out.close()
            details_out.close()

    print(f"\n✅ Wrote summary CSV: {CSV_PATH}")
    print(f"📝 Details JSONL   : {RUN_DIR/'details.jsonl'}")
    print(f"🧷 Cypher per-DB   : runs/auto_eval/cyphers_<db>.jsonl")
    print("Done.")

if __name__ == "__main__":
    main()
