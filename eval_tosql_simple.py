# eval_tosql_simple.py
# ------------------------------------------------------------------
# SIMPLE Text-to-SQL evaluation for 10 DBs × 10 questions.
# - Loads OPENAI_API_KEY from .env (repo root)
# - Uses runs/user_eval_worklist.json if present; else samples from data/spider/train_spider.json
# - Compares LLM-generated SELECT SQL vs Spider gold SQL
# - Saves: runs/eval_tosql/results.csv and runs/eval_tosql/details.jsonl
import os, json, re, sqlite3, csv, random
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# 0) Load .env manually
ENV_PATH = Path(".env")
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise SystemExit("OPENAI_API_KEY not found. Put it in a .env file at repo root.")

# 1) OpenAI client
from openai import OpenAI
client = OpenAI(api_key=API_KEY)
MODEL = os.environ.get("EVAL_SQL_MODEL", "gpt-5-mini")

# 2) Paths
SPIDER_DIR = Path("data/spider")
TRAIN_SPLIT = SPIDER_DIR / "train_spider.json"
DB_ROOT = SPIDER_DIR / "database"
WORKLIST = Path("runs/user_eval_worklist.json")
OUT_DIR = Path("runs/eval_tosql")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DB_COUNT = 10
PER_DB = 10
RANDOM_SEED = 123

@dataclass
class QItem:
    db_id: str
    sqlite: str
    question: str
    sql_gold: str

def load_worklist_or_sample() -> List[QItem]:
    random.seed(RANDOM_SEED)
    if WORKLIST.exists():
        plan = json.loads(WORKLIST.read_text(encoding="utf-8"))
        items: List[QItem] = []
        for entry in plan.get("selected", []):
            db_id = entry["db_id"]
            sqlite_path = entry["sqlite"]
            for q in entry.get("selected_questions", [])[:PER_DB]:
                if q.get("query") and q.get("question"):
                    items.append(QItem(db_id=db_id, sqlite=sqlite_path,
                                       question=q["question"], sql_gold=q["query"]))
        by_db: Dict[str, List[QItem]] = {}
        for it in items: by_db.setdefault(it.db_id, []).append(it)
        chosen_db_ids = sorted(list(by_db.keys()))[:DB_COUNT]
        final: List[QItem] = []
        for db in chosen_db_ids: final.extend(by_db[db][:PER_DB])
        return final

    if not TRAIN_SPLIT.exists():
        raise FileNotFoundError("Missing runs/user_eval_worklist.json and data/spider/train_spider.json")
    examples = json.loads(TRAIN_SPLIT.read_text(encoding="utf-8"))
    by_db: Dict[str, List[Dict[str, Any]]] = {}
    for ex in examples:
        db_id = ex.get("db_id")
        if not db_id: continue
        db_sqlite = DB_ROOT / db_id / f"{db_id}.sqlite"
        if not db_sqlite.exists(): continue
        if ex.get("question") and ex.get("query"):
            by_db.setdefault(db_id, []).append(ex)
    db_ids = sorted(by_db.keys())[:DB_COUNT]
    items: List[QItem] = []
    for db_id in db_ids:
        sqlite_path = str(DB_ROOT / db_id / f"{db_id}.sqlite")
        for ex in by_db[db_id][:PER_DB]:
            items.append(QItem(db_id=db_id, sqlite=sqlite_path,
                               question=ex["question"], sql_gold=ex["query"]))
    return items

def fetch_schema_dict(sqlite_path: str) -> Dict[str, Any]:
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]
    schema = {"tables": {}, "foreign_keys": []}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})"); cols = [c[1] for c in cur.fetchall()]
        schema["tables"][t] = {"columns": cols}
        cur.execute(f"PRAGMA foreign_key_list({t})")
        for fk in cur.fetchall():
            schema["foreign_keys"].append({
                "from_table": t, "parent_table": fk[2],
                "from_column": fk[3], "parent_column": fk[4]
            })
    con.close()
    return schema

def run_sql(sqlite_path: str, sql: str) -> Tuple[list, list]:
    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    con.close()
    return rows, cols

def is_safe_select(sql: str) -> bool:
    s = sql.strip().lower()
    if not s.startswith("select"): return False
    if ";" in s: return False  # no multi-statements
    banned = ["insert","update","delete","drop","alter","create","attach","pragma"]
    return not any(f" {b} " in f" {s} " for b in banned)

def llm_generate_sql(question: str, schema: Dict[str, Any]) -> str:
    schema_str = json.dumps(schema, indent=2)
    sys_prompt = (
        "You are a SQLite SQL assistant. Generate a single SELECT statement that answers the user question.\n"
        "Rules:\n"
        "1) Output ONLY raw SQL for SQLite (no backticks or markdown).\n"
        "2) Use correct table and column names from the provided schema.\n"
        "3) No table creation, deletion, updates, PRAGMAs, or comments.\n"
        "4) If aggregation or joins are needed, write them explicitly.\n"
        "5) Keep it a single SELECT; no CTEs unless absolutely necessary.\n"
        "6) Use ONLY table and column names that appear in the provided schema JSON; if unsure, prefer the simplest join consistent with foreign keys.\n"
    )
    user_msg = f"Schema (JSON):\n{schema_str}\n\nQuestion:\n{question}\n\nReturn only the SQL."
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ],
    )
    sql = resp.choices[0].message.content.strip()
    # Clean model output
    sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql, flags=re.IGNORECASE|re.MULTILINE).strip()
    sql = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)      # -- comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)      # /* ... */ comments
    sql = sql.strip()
    if sql.endswith(";"): sql = sql[:-1].strip()
    return sql

def rows_to_canonical(rows, cols, max_rows=200):
    if rows is None: return []
    if len(rows) > max_rows: return rows[:max_rows]
    return rows

def compare_results(gold_rows, pred_rows) -> Dict[str, Any]:
    res = {
        "gold_count": len(gold_rows),
        "pred_count": len(pred_rows),
        "rowcount_match": len(gold_rows) == len(pred_rows),
        "exact_match_checked": False,
        "exact_match": None,
    }
    if len(gold_rows) <= 200 and len(pred_rows) <= 200:
        res["exact_match_checked"] = True
        res["exact_match"] = (sorted(gold_rows) == sorted(pred_rows))
    return res

def main():
    items = load_worklist_or_sample()
    print(f"Evaluating {len(items)} questions (aim: {DB_COUNT} DBs × {PER_DB} Qs)")
    csv_path = OUT_DIR / "results.csv"
    jsonl_path = OUT_DIR / "details.jsonl"
    with open(csv_path, "w", newline="", encoding="utf-8") as csvf, open(jsonl_path, "w", encoding="utf-8") as jf:
        writer = csv.writer(csvf)
        writer.writerow(["db_id","question","gold_count","pred_count","rowcount_match","exact_match_checked","exact_match","llm_sql","gold_sql","error"])
        for i, it in enumerate(items, start=1):
            print(f"[{i}/{len(items)}] {it.db_id} — {it.question[:60]}...")
            try:
                schema = fetch_schema_dict(it.sqlite)
                gold_rows, gold_cols = run_sql(it.sqlite, it.sql_gold)
                gold_rows_norm = rows_to_canonical(gold_rows, gold_cols)
                llm_sql = llm_generate_sql(it.question, schema)
                if not is_safe_select(llm_sql):
                    raise ValueError(f"Model produced unsafe SQL: {llm_sql[:160]}")
                pred_rows, pred_cols = run_sql(it.sqlite, llm_sql)
                pred_rows_norm = rows_to_canonical(pred_rows, pred_cols)
                comp = compare_results(gold_rows_norm, pred_rows_norm)
                writer.writerow([it.db_id,it.question,comp["gold_count"],comp["pred_count"],comp["rowcount_match"],comp["exact_match_checked"],comp["exact_match"],llm_sql,it.sql_gold,""])
                jf.write(json.dumps({
                    "db_id": it.db_id, "sqlite": it.sqlite, "question": it.question,
                    "gold_sql": it.sql_gold, "llm_sql": llm_sql,
                    "gold_count": comp["gold_count"], "pred_count": comp["pred_count"],
                    "rowcount_match": comp["rowcount_match"],
                    "exact_match_checked": comp["exact_match_checked"],
                    "exact_match": comp["exact_match"],
                    "gold_sample": gold_rows_norm[:3],
                    "pred_sample": pred_rows_norm[:3],
                }, ensure_ascii=False) + "\n")
            except Exception as e:
                writer.writerow([it.db_id, it.question, "", "", "", "", "", "", it.sql_gold, str(e)])
                jf.write(json.dumps({"db_id": it.db_id, "sqlite": it.sqlite, "question": it.question, "gold_sql": it.sql_gold, "error": str(e)}, ensure_ascii=False) + "\n")
    print("✅ Done.")
    print(f"CSV: {csv_path}")
    print(f"Details: {jsonl_path}")

if __name__ == "__main__":
    main()
