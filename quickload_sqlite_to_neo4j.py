#!/usr/bin/env python3
"""
quickload_sqlite_to_neo4j.py
Load a SQLite DB (Spider-style) into Neo4j.
- Tables -> Node labels (exact table name)
- Rows   -> Nodes with all columns as properties
- FKs    -> Relationships from child(table with FK) -> parent(referenced table)
Adds lots of verbose logging and safety checks.
"""

import argparse, sqlite3, sys, time
from typing import Dict, List, Any, Tuple
from neo4j import GraphDatabase

def read_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info('{t}')")
        cols = cur.fetchall()
        # cols: cid, name, type, notnull, dflt_value, pk
        pk_cols = [c[1] for c in cols if c[5] == 1]
        cur.execute(f"PRAGMA foreign_key_list('{t}')")
        fks = [{"from": r[3], "to_table": r[2], "to_col": r[4]} for r in cur.fetchall()]
        schema[t] = {"columns": [c[1] for c in cols], "pk": pk_cols[0] if pk_cols else None, "fks": fks}
    return schema

def clear_db(driver, db):
    print(f"[info] Clearing database '{db}' ...")
    with driver.session(database=db) as sess:
        sess.run("MATCH (n) DETACH DELETE n")
    print("[info] Cleared.")

def create_indexes(driver, db, schema: Dict[str, Any]):
    with driver.session(database=db) as sess:
        for t, info in schema.items():
            pk = info["pk"]
            if pk:
                cy = f"CREATE INDEX IF NOT EXISTS `{t}_{pk}_idx` FOR (n:`{t}`) ON (n.`{pk}`)"
                sess.run(cy)
                print(f"[info] Index ensured on :`{t}`(`{pk}`)")

def load_nodes(conn, driver, db, table: str, columns: List[str], pk: str, limit: int = None):
    cur = conn.cursor()
    q = f"SELECT {', '.join([f'\"{c}\"' for c in columns])} FROM \"{table}\""
    if limit: q += f" LIMIT {int(limit)}"
    cur.execute(q)
    rows = cur.fetchall()
    total = len(rows)
    print(f"[nodes] Loading {total} rows from table '{table}' ...")

    # parameterized MERGE by pk if available else MERGE with full row composite map (slower)
    with driver.session(database=db) as sess:
        tx = sess.begin_transaction()
        count = 0
        for r in rows:
            props = {columns[i]: r[i] for i in range(len(columns))}
            if pk and pk in props and props[pk] is not None:
                cypher = f"MERGE (n:`{table}` {{ `{pk}`: $pk }}) SET n += $props"
                params = {"pk": props[pk], "props": props}
            else:
                cypher = f"MERGE (n:`{table}` {{ _rowhash: $rowhash }}) SET n += $props"
                params = {"rowhash": hash(tuple(props.items())), "props": props}
            tx.run(cypher, **params)
            count += 1
            if count % 1000 == 0:
                tx.commit()
                tx = sess.begin_transaction()
                print(f"[nodes]   committed {count}/{total}")
        tx.commit()
    print(f"[nodes] Done '{table}': {total} rows.")

def load_relationships(conn, driver, db, table: str, pk: str, fks: List[Dict[str, str]], limit: int = None):
    if not fks:
        return
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info('{table}')")
    columns = [c[1] for c in cur.fetchall()]

    if pk is None:
        print(f"[rels] Skipping rels for '{table}' – no PK detected.")
        return

    # Fetch child rows with the PK + all FK columns we need
    select_cols = set([pk])
    for fk in fks:
        select_cols.add(fk["from"])
    sel = ", ".join([f'"{c}"' for c in select_cols])
    q = f"SELECT {sel} FROM \"{table}\""
    if limit: q += f" LIMIT {int(limit)}"
    cur.execute(q)
    rows = cur.fetchall()
    total = len(rows)
    print(f"[rels] Scanning {total} rows from '{table}' for relationships ...")

    with driver.session(database=db) as sess:
        tx = sess.begin_transaction()
        count = 0
        for row in rows:
            row_map = dict(zip([c.strip('"') for c in select_cols.split(", ")], row))
            child_pk_val = row_map.get(pk)

            for fk in fks:
                child_fk_col = fk["from"]
                parent_table = fk["to_table"]
                parent_pk_col = fk["to_col"]
                rel_type = f"FK_{table}_{child_fk_col}__{parent_table}_{parent_pk_col}"

                child_match = f"(c:`{table}` {{ `{pk}`: $child_pk }})"
                parent_match = f"(p:`{parent_table}` {{ `{parent_pk_col}`: $parent_pk }})"
                cypher = f"MERGE {child_match} MERGE {parent_match} MERGE (c)-[:`{rel_type}`]->(p)"
                params = {"child_pk": child_pk_val, "parent_pk": row_map.get(child_fk_col)}
                tx.run(cypher, **params)

            count += 1
            if count % 1000 == 0:
                tx.commit()
                tx = sess.begin_transaction()
                print(f"[rels]   committed {count}/{total}")
        tx.commit()
    print(f"[rels] Done '{table}': processed {total} rows.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite_path", help="Path to SQLite file")
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", required=True)
    ap.add_argument("--db", default="neo4j", help="Neo4j database name (default: neo4j)")
    ap.add_argument("--clear", action="store_true", help="Wipe database before load")
    ap.add_argument("--limit", type=int, default=None, help="Optional row limit per table (for testing)")
    args = ap.parse_args()

    try:
        conn = sqlite3.connect(args.sqlite_path)
    except Exception as e:
        print(f"[error] Unable to open SQLite: {e}", file=sys.stderr)
        sys.exit(2)

    schema = read_schema(conn)
    print("[info] Tables discovered:")
    for t, info in schema.items():
        print(f"  - {t} (pk={info['pk']}, cols={len(info['columns'])}, fks={len(info['fks'])})")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))

    if args.clear:
        clear_db(driver, args.db)

    create_indexes(driver, args.db, schema)

    # Load nodes first
    for t, info in schema.items():
        load_nodes(conn, driver, args.db, t, info["columns"], info["pk"], limit=args.limit)

    # Then relationships
    for t, info in schema.items():
        load_relationships(conn, driver, args.db, t, info["pk"], info["fks"], limit=args.limit)

    # Show a quick summary
    with driver.session(database=args.db) as sess:
        cnt = sess.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        labels = [r["label"] for r in sess.run("CALL db.labels() YIELD label RETURN label ORDER BY label")]
    print(f"[summary] Nodes: {cnt}")
    print(f"[summary] Labels: {labels}")
    print("[done] Load complete.")

if __name__ == "__main__":
    main()
