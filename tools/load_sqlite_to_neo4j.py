# tools/load_sqlite_to_neo4j.py
# Minimal loader: creates one label per table, one node per row (capped),
# and FK-based edges with type :FK (stores a 'key' property to avoid dupes).
import argparse, sqlite3, re
from typing import Dict, List, Tuple
from neo4j import GraphDatabase

def norm_ident(s: str) -> str:
    # keep original for labels/props, but this helps with messages
    return re.sub(r"\W+", "_", s)

def list_tables(conn) -> List[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [r[0] for r in cur.fetchall()]

def table_columns(conn, table: str):
    # returns list of (name, is_pk)
    cols = []
    for cid, name, ctype, notnull, dflt_value, pk in conn.execute(f"PRAGMA table_info('{table}')"):
        cols.append((name, bool(pk)))
    return cols

def table_pk(conn, table: str) -> List[str]:
    return [name for (name, is_pk) in table_columns(conn, table) if is_pk]

def table_fks(conn, table: str) -> List[Tuple[str, str, str]]:
    # returns list of (from_col, to_table, to_col)
    fks = []
    for row in conn.execute(f"PRAGMA foreign_key_list('{table}')"):
        # id, seq, table, from, to, on_update, on_delete, match
        _, _, ref_table, from_col, to_col, *_ = row
        fks.append((from_col, ref_table, to_col))
    return fks

def backtick(name: str) -> str:
    return f"`{name.replace('`','``')}`"

def load(sqlite_db: str, uri: str, user: str, password: str, rows_per_table: int = 200):
    drv = GraphDatabase.driver(uri, auth=(user, password))
    conn = sqlite3.connect(sqlite_db)
    conn.row_factory = sqlite3.Row

    tables = list_tables(conn)
    print(f"Found {len(tables)} tables")

    # 1) Create nodes (and uniqueness constraints)
    with drv.session() as s:
        for t in tables:
            pk_cols = table_pk(conn, t)

            # Always select SQLite rowid as a stable surrogate id
            q = f"SELECT rowid AS __rid, * FROM '{t}' LIMIT {int(rows_per_table)}"

            if len(pk_cols) == 1:
                pk = pk_cols[0]
                # unique constraint on the real PK
                try:
                    s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{t}) REQUIRE n.{pk} IS UNIQUE")
                except Exception as e:
                    print(f"[warn] constraint for {t}({pk}): {e}")

                for row in conn.execute(q):
                    props = dict(row)  # includes __rid and all columns
                    s.run(
                        f"MERGE (n:{t} {{ {pk}: $pk }}) SET n += $props",
                        pk=props.get(pk),
                        props=props,
                    )
            else:
                # no single-column PK -> use SQLite rowid as surrogate and make it unique
                try:
                    s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{t}) REQUIRE n.__rid IS UNIQUE")
                except Exception as e:
                    print(f"[warn] constraint for {t}(__rid): {e}")

                for row in conn.execute(q):
                    props = dict(row)  # includes __rid and all columns
                    s.run(
                        f"MERGE (n:{t} {{ __rid: $__rid }}) SET n += $props",
                        __rid=props["__rid"],
                        props=props,
                    )

    # 2) Create relationships for single-column FKs
    with drv.session() as s:
        for t in tables:
            fks = table_fks(conn, t)
            if not fks:
                continue
            pk_map = {tbl: table_pk(conn, tbl) for tbl in tables}
            for from_col, to_table, to_col in fks:
                # only handle single-column PK on target
                if len(pk_map.get(to_table, [])) != 1 or pk_map[to_table][0] != to_col:
                    print(f"[skip] FK {t}.{from_col} -> {to_table}.{to_col} (target PK not single-column)")
                    continue

                # pull FK rows (with source rowid so we can match the exact source node)
                q = f"SELECT rowid AS __rid, {from_col} AS fkval FROM '{t}' WHERE {from_col} IS NOT NULL LIMIT {int(rows_per_table)}"
                for r in conn.execute(q):
                    fkval = r["fkval"]
                    rid   = r["__rid"]
                    key   = f"{t}.{from_col}->{to_table}:{fkval}"

                    cy = (
                        f"MATCH (a:{t} {{ __rid: $rid }}), (b:{to_table} {{ {to_col}: $fk }}) "
                        f"MERGE (a)-[:FK {{key:$key}}]->(b)"
                    )
                    s.run(cy, rid=rid, fk=fkval, key=key)

    conn.close()
    drv.close()
    print("Done loading.")


    

            

    
            
                    
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Load a single SQLite DB into Neo4j (nodes + FK edges)")
    ap.add_argument("--sqlite-db", required=True)
    ap.add_argument("--neo4j-uri", required=True)
    ap.add_argument("--neo4j-user", required=True)
    ap.add_argument("--neo4j-password", required=True)
    ap.add_argument("--rows-per-table", type=int, default=200)
    args = ap.parse_args()
    load(args.sqlite_db, args.neo4j_uri, args.neo4j_user, args.neo4j_password, args.rows_per_table)
