
from __future__ import annotations
import csv
from .config import (
    SPIDER_DB_DIR,
    OUTPUT_DIR,
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    COUNT_ONLY,
)
from .data_loader import load_split_items
from .agent import generate_cypher
from .sql_exec import run_sql_count
from .cypher_exec import run_cypher_count

def main() -> None:
    items = load_split_items()
    out_csv = OUTPUT_DIR / "user_eval_counts.csv"
    out_md  = OUTPUT_DIR / "user_eval_summary.md"

    rows = []
    match_yes = 0
    match_no = 0

    for it in items:
        db_id = it["db_id"]
        qid = it.get("question_id") or it.get("qid") or it.get("id") or ""
        question = it.get("question") or ""
        sql_text = it.get("query")  # gold SQL in dev/train json

        status = ""
        sql_count = ""
        cypher_count = ""
        matched = ""

        if not sql_text or not question:
            status = "NO_SQL_TEXT"
        else:
            sqlite_path = SPIDER_DB_DIR / db_id / f"{db_id}.sqlite"
            if not sqlite_path.exists():
                status = "NO_SQLITE"
            else:
                sql_cnt = run_sql_count(sqlite_path, sql_text)
                if sql_cnt is None:
                    status = "SQL_FAIL"
                else:
                    sql_count = str(sql_cnt)

                    cy = generate_cypher(question, db_id)
                    if not cy:
                        status = "NO_CYPHER"
                    else:
                        kg_cnt = run_cypher_count(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, cy)
                        if kg_cnt is None:
                            status = "CYPHER_FAIL"
                        else:
                            cypher_count = str(kg_cnt)
                            if str(sql_cnt) == str(kg_cnt):
                                status = "MATCH"
                                matched = "True"
                                match_yes += 1
                            else:
                                status = "MISMATCH"
                                matched = "False"
                                match_no += 1

        rows.append({
            "db_id": db_id,
            "qid": qid,
            "status": status,
            "question": question,
            "sql_count": sql_count,
            "cypher_count": cypher_count,
            "match": matched,
        })

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["db_id","qid","status","question","sql_count","cypher_count","match"])
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# User Questions Count Evaluation\n\n")
        f.write(f"- Total items: {total}\n")
        f.write(f"- Matches: {match_yes}\n")
        f.write(f"- Mismatches: {match_no}\n")
        f.write(f"- Skipped/Errors: {total - match_yes - match_no}\n\n")
        f.write("Statuses observed:\n")
        status_counts = {}
        for r in rows:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        for s, c in sorted(status_counts.items()):
            f.write(f"- {s}: {c}\n")

    print("Saved:")
    print(f"- {out_csv}")
    print(f"- {out_md}")
    print("Done.")

if __name__ == "__main__":
    main()
