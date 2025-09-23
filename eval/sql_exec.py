
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

def run_sql_count(sqlite_path: Path, sql_text: str) -> Optional[int]:
    """
    Run COUNT(*) over the gold SQL: SELECT COUNT(*) FROM (<sql_text>) t;
    Returns an integer or None on failure.
    """
    wrapped = f"SELECT COUNT(*) AS count FROM ({sql_text}) t"
    try:
        con = sqlite3.connect(str(sqlite_path))
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(wrapped)
        row = cur.fetchone()
        con.close()
        if row is None:
            return None
        return int(row[0])
    except Exception:
        return None
