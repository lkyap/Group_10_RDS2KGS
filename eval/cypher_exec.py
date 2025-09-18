
from __future__ import annotations
from typing import Optional
from neo4j import GraphDatabase

def run_cypher_count(uri: str, user: str, password: str, cypher: str) -> Optional[int]:
    """
    Execute a read-only Cypher and expect a single row with a single integer 'count'.
    Returns None on failure/mismatch.
    """
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run(cypher)
            records = list(result)
        driver.close()

        if not records:
            return None
        rec = records[0]
        if "count" in rec.keys():
            return int(rec["count"])
        vals = rec.values()
        if not vals:
            return None
        return int(list(vals)[0])
    except Exception:
        return None
