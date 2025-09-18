# eval/eval_user_questions.py
# Minimal, count-only evaluator:
# - loads Spider questions (dev split)
# - executes SQL on SQLite and wraps as COUNT(*)
# - tries to read a matching Cypher file and get count from Neo4j 
# - writes a CSV + Markdown summary in eval/output/

import json, sqlite3, csv, hashlib, re
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import (
    SPIDER_DIR, SPIDER_DB_DIR, OUTPUT_DIR,
    SPLIT, QUESTIONS_PER_DB, INCLUDED_DB_IDS,
    CYPHER_MODE, CYPHER_ROOT,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
)

# Neo4j is optional: if driver isn't installed or Neo4j isn't running, we still produce results
NEO4J_OK = False
try:
    from neo4j import GraphDatabase
    NEO4J_OK = True
except Exception:
    pass


def spider_split_path(split: str) -> Path:
    if split == "dev":
        return SPIDER_DIR / "dev.json"
    elif split == "train":
        return SPIDER_DIR / "train_spider.json"
    else:
        raise ValueError(f"Unknown split: {split}")


def load_spider_items() -> List[Dict[str, Any]]:
    path = spider_split_path(SPLIT)
    if not path.exists():
        raise SystemExit(
            f"[setup] {path} not found. Make sure the Spider zip has been extracted "
            f"so {SPIDER_DIR} contains dev.json/train_spider.json and database/."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def make_qid(db_id: str, question: str, sql_obj: Dict[str, Any]) -> str:
    key = f"{db_id}|{question}|{sql_obj.get('query','')}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def pick_subset(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if INCLUDED_DB_IDS:
        items = [x for x in items if x["db_id"] in INCLUDED_DB_IDS]
    if QUESTIONS_PER_DB and QUESTIONS_PER_DB > 0:
        by_db: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            by_db.setdefault(it["db_id"], []).append(it)
        trimmed: List[Dict[str, Any]] = []
        for db_id, bucket in by_db.items():
            trimmed.extend(bucket[:QUESTIONS_PER_DB])
        return trimmed
    return items


def sqlite_db_path(db_id: str) -> Path:
    p = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"
    if not p.exists():
        raise FileNotFoundError(f"SQLite not found for {db_id}: {p}")
    return p


def run_sql_count(db_id: str, sql_text: str) -> Optional[int]:
    wrapped = f"SELECT COUNT(*) FROM ({sql_text}) AS t"
    conn = sqlite3.connect(sqlite_db_path(db_id))
    try:
        cur = conn.execute(wrapped)
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return None
    finally:
        conn.close()


def cypher_file_path(db_id: str, qid: str) -> Path:
    return CYPHER_ROOT / db_id / f"{qid}.cypher"


def get_cypher(db_id: str, qid: str) -> Optional[str]:
    if CYPHER_MODE == "precomputed":
        p = cypher_file_path(db_id, qid)
        return p.read_text(encoding="utf-8").strip() if p.exists() else None
    elif CYPHER_MODE == "agent":
        # placeholder for your agent later
        return None
    else:
        raise ValueError(f"Unknown CYPHER_MODE={CYPHER_MODE}")


class Neo4jRunner:
    def __init__(self, uri: str, user: str, password: str):
        if not NEO4J_OK:
            raise RuntimeError("neo4j driver not installed (pip install neo4j)")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def run_count(self, cypher: str) -> Optional[int]:
        try:
            with self.driver.session() as session:
                res = session.run(cypher)
                rows = res.data()
                if not rows:
                    return 0
                row = rows[0]
                # look for any int-like value in the first row
                for _, v in row.items():
                    try:
                        return int(v)
                    except Exception:
                        continue
                return None
        except Exception:
            return None

    def close(self):
        try:
            self.driver.close()
        except Exception:
            pass


def main():
    items = load_spider_items()
    items = pick_subset(items)

    # Helpful setup check
    if not SPIDER_DB_DIR.exists():
        raise SystemExit(
            f"[setup] {SPIDER_DB_DIR} not found. Ensure the Spider dataset is extracted "
            "so database/<db_id>/<db_id>.sqlite is present."
        )

    # Optional Neo4j
    neo = None
    if CYPHER_MODE in ("precomputed", "agent") and NEO4J_OK:
        try:
            neo = Neo4jRunner(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        except Exception:
            neo = None

    rows: List[Dict[str, Any]] = []
    per_db: Dict[str, Dict[str, int]] = {}

    for it in items:
        db_id = it["db_id"]
        question = it["question"]
        sql_obj = it["sql"]
        qid = make_qid(db_id, question, sql_obj)

        sql_text = sql_obj.get("query")  # most Spider dumps include this
        if not sql_text:
            status = "NO_SQL_TEXT"
            sql_cnt = None
            cy_cnt = None
            match = None
        else:
            sql_cnt = run_sql_count(db_id, sql_text)

            cypher = get_cypher(db_id, qid)
            if not cypher:
                status = "NO_CYPHER"
                cy_cnt = None
                match = None
            else:
                # ensure it RETURNs a single count
                if not re.search(r"\bRETURN\b", cypher, flags=re.IGNORECASE):
                    cypher = f"{cypher}\nWITH collect(*) AS _r RETURN size(_r) AS count"
                cy_cnt = neo.run_count(cypher) if neo else None
                match = (sql_cnt is not None and cy_cnt is not None and int(sql_cnt) == int(cy_cnt))
                status = "MATCH" if match else "MISMATCH"

        rows.append(dict(
            db_id=db_id, qid=qid, status=status, question=question,
            sql_count=sql_cnt, cypher_count=cy_cnt, match=match
        ))
        st = per_db.setdefault(db_id, dict(total=0, match=0, fail=0, no_sql=0, no_cypher=0))
        st["total"] += 1
        if status == "MATCH":
            st["match"] += 1
        elif status == "MISMATCH":
            st["fail"] += 1
        elif status == "NO_SQL_TEXT":
            st["no_sql"] += 1
        elif status == "NO_CYPHER":
            st["no_cypher"] += 1

    # Write CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / f"user_eval_{SPLIT}_counts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["db_id","qid","status","question","sql_count","cypher_count","match"])
        w.writeheader()
        w.writerows(rows)

    # Write Markdown summary
    md_lines = ["# User Questions — Count Match Summary", ""]
    md_lines.append("| Database | #Evaluated | #Match | #Fail | #No SQL | #No Cypher | Match % |")
    md_lines.append("|---|---:|---:|---:|---:|---:|---:|")

    total = dict(total=0, match=0, fail=0, no_sql=0, no_cypher=0)
    for db_id in sorted(per_db.keys()):
        st = per_db[db_id]
        pct = (100.0 * st["match"] / st["total"]) if st["total"] else 0.0
        md_lines.append(f"| {db_id} | {st['total']} | {st['match']} | {st['fail']} | {st['no_sql']} | {st['no_cypher']} | {pct:.1f}% |")
        for k in total:
            total[k] += st.get(k, 0)
    tot_pct = (100.0 * total["match"] / total["total"]) if total["total"] else 0.0
    md_lines.append(f"| **TOTAL** | **{total['total']}** | **{total['match']}** | **{total['fail']}** | **{total['no_sql']}** | **{total['no_cypher']}** | **{tot_pct:.1f}%** |")

    md_path = OUTPUT_DIR / f"user_eval_{SPLIT}_summary.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Saved:\n- {csv_path}\n- {md_path}\nDone.")


if __name__ == "__main__":
    main()
