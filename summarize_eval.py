# summarize_eval.py
# Read runs/eval_tosql/results.csv and print per-DB & overall accuracies.
# Also writes runs/eval_tosql/summary.txt and summary.md

import csv, sys
from pathlib import Path
from collections import defaultdict

CSV_PATH = Path("runs/eval_tosql/results.csv")

def to_bool(x):
    if x is None: return False
    s = str(x).strip().lower()
    return s in ("true","1","yes","y","t")

def fmt(v):
    return f"{v:.2f}"

def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_PATH
    if not path.exists():
        print(f"CSV not found: {path}")
        sys.exit(1)

    by_db = defaultdict(lambda: {"N":0,"rowcount_true":0,"exact_checked":0,"exact_true":0})
    overall = {"N":0,"rowcount_true":0,"exact_checked":0,"exact_true":0}

    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            db = row["db_id"]
            rc_match = to_bool(row.get("rowcount_match"))
            ex_checked = to_bool(row.get("exact_match_checked"))
            ex_match = to_bool(row.get("exact_match")) if ex_checked else False

            by_db[db]["N"] += 1
            overall["N"] += 1
            if rc_match:
                by_db[db]["rowcount_true"] += 1
                overall["rowcount_true"] += 1
            if ex_checked:
                by_db[db]["exact_checked"] += 1
                overall["exact_checked"] += 1
                if ex_match:
                    by_db[db]["exact_true"] += 1
                    overall["exact_true"] += 1

    # Print per-DB table
    print("DB, N, Rowcount Acc, Exact Acc")
    lines = []
    dbs_sorted = sorted(by_db.items(), key=lambda kv: kv[0].lower())
    for db, m in dbs_sorted:
        N = m["N"] or 1
        rc = m["rowcount_true"]/N
        ex_den = m["exact_checked"] or 1
        ex = m["exact_true"]/ex_den
        print(f"{db}, {N}, {fmt(rc)}, {fmt(ex)}")
        lines.append((db, N, rc, ex, m["exact_checked"], m["exact_true"]))

    # Overall
    rc_overall = overall["rowcount_true"]/(overall["N"] or 1)
    ex_overall = overall["exact_true"]/(overall["exact_checked"] or 1)
    print("\nOVERALL")
    print(f"Rowcount Acc: {fmt(rc_overall)}")
    print(f"Exact Acc:    {fmt(ex_overall)} (checked {overall['exact_checked']}/{overall['N']})")

    # Write summaries
    out_dir = Path("runs/eval_tosql")
    out_dir.mkdir(parents=True, exist_ok=True)
    txt = out_dir / "summary.txt"
    md  = out_dir / "summary.md"

    with open(txt, "w", encoding="utf-8") as f:
        f.write("DB, N, Rowcount Acc, Exact Acc\n")
        for db, N, rc, ex, ex_checked, ex_true in lines:
            f.write(f"{db}, {N}, {fmt(rc)}, {fmt(ex)}\n")
        f.write("\nOVERALL\n")
        f.write(f"Rowcount Acc: {fmt(rc_overall)}\n")
        f.write(f"Exact Acc:    {fmt(ex_overall)} (checked {overall['exact_checked']}/{overall['N']})\n")

    with open(md, "w", encoding="utf-8") as f:
        f.write("# Eval Summary\n\n")
        f.write("| Database | N | Rowcount Acc | Exact Acc |\n|---|---:|---:|---:|\n")
        for db, N, rc, ex, ex_checked, ex_true in lines:
            f.write(f"| {db} | {N} | {fmt(rc)} | {fmt(ex)} |\n")
        f.write("\n**Overall**  \n")
        f.write(f"- Rowcount Acc: **{fmt(rc_overall)}**\n")
        f.write(f"- Exact Acc: **{fmt(ex_overall)}** (checked {overall['exact_checked']}/{overall['N']})\n")

    print(f"\nWrote: {txt}")
    print(f"Wrote: {md}")

if __name__ == "__main__":
    main()
