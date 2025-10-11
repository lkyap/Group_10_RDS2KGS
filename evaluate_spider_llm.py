#!/usr/bin/env python3
"""
Evaluation: User Questions (No hard-coding)
------------------------------------------
- Reads Spider dev.json user questions.
- For each database (db_id), takes up to N questions (default 10).
- Extracts relational schema from the SQLite DB (tables, columns, FKs).
- Uses an LLM to generate a *Cypher* query for each question given the schema and graph-mapping rules.
- Executes SQL (SQLite) and Cypher (Neo4j) and compares results (counts + samples).
- Prints a concise report and writes a JSON file with full details.

Requirements:
- Env: OPENAI_API_KEY (for LLM)
- Running Neo4j on bolt://localhost:7687 (or change via CLI args/env)
- Python packages: openai (>=1.0), neo4j, sqlite3 (stdlib)

Usage examples:
    python evaluate_spider_llm.py \
        --spider_json data/spider/dev.json \
        --spider_root data/spider/database \
        --neo4j_uri bolt://localhost:7687 \
        --neo4j_user neo4j \
        --neo4j_pass <your_password> \
        --per_db 10 \
        --out evaluation_spider_llm.json
"""

import os
import json
import argparse
import sqlite3
from typing import Dict, List, Any, Tuple

# OpenAI >= 1.0 SDK
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from neo4j import GraphDatabase


GRAPH_RULES = """
Assume the relational DB was converted to a property graph using these rules:
1) Each table becomes a node label with the same name (snake_case stays the same).
2) Each row becomes a node. All columns are node properties with identical names.
3) For each FOREIGN KEY tA.col -> tB.id, create a relationship:
     (tA)-[:FK_tA_col__tB_id]->(tB)
   Direction: from the child (table with FK) to the parent (referenced table).
4) If a table has multiple FKs, multiple relationships exist accordingly.
5) Primary key column is typically named 'id' (or as per schema).
Return Cypher compatible with Neo4j, no explanations, just a single Cypher statement.
"""


def extract_sqlite_schema(db_path: str) -> Dict[str, Any]:
    """Introspect a SQLite DB into a minimal JSON schema (tables, columns, PKs, FKs)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # list tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r[0] for r in cur.fetchall()]

    schema: Dict[str, Any] = {"tables": {}}

    for t in tables:
        # columns
        cur.execute(f"PRAGMA table_info('{t}')")
        cols = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "dflt_value": c[4], "pk": c[5]} for c in cur.fetchall()]

        # fks
        cur.execute(f"PRAGMA foreign_key_list('{t}')")
        fks = [{"id": fk[0], "seq": fk[1], "table": fk[2], "from": fk[3], "to": fk[4]} for fk in cur.fetchall()]

        schema["tables"][t] = {"columns": cols, "foreign_keys": fks}

    conn.close()
    return schema


class LlmCypherGenerator:
    def __init__(self, model: str = "gpt-4o-mini"):
        if OpenAI is None:
            raise RuntimeError("openai package not available. Please `pip install openai` >= 1.0")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def question_to_cypher(self, question: str, schema: Dict[str, Any]) -> str:
        schema_str = json.dumps(schema, indent=2)
        user = f"""You are given a relational schema (SQLite) and a natural language question.
{GRAPH_RULES}

Schema (JSON):
{schema_str}

Question:
{question}

Return only the Cypher query. No prose.
"""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You generate accurate Cypher queries for Neo4j based on a relational schema mapped to a graph."},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        cypher = resp.choices[0].message.content.strip()
        # best-effort: if fenced in code, strip fences
        if cypher.startswith("```"):
            cypher = cypher.strip("`")
            # remove possible 'cypher\n' header
            parts = cypher.split("\n", 1)
            cypher = parts[1] if len(parts) > 1 else parts[0]
        return cypher


class SpiderLlmEvaluator:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_pass: str, per_db: int = 10):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
        self.per_db = per_db
        self.gen = LlmCypherGenerator()

    def run_sql(self, db_path: str, sql: str) -> List[Tuple]:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
        return rows

    def run_cypher(self, cypher: str) -> List[Any]:
        with self.driver.session() as sess:
            res = sess.run(cypher)
            return [record.data() for record in res]

    def evaluate(self, spider_json: str, spider_root: str) -> Dict[str, Any]:
        with open(spider_json, "r") as f:
            data = json.load(f)

        # count per db
        taken: Dict[str, int] = {}
        report: Dict[str, Any] = {"items": []}

        for item in data:
            db_id = item["db_id"]
            if taken.get(db_id, 0) >= self.per_db:
                continue

            question = item["question"]
            sql = item["query"]
            db_path = os.path.join(spider_root, db_id, f"{db_id}.sqlite")

            try:
                schema = extract_sqlite_schema(db_path)
            except Exception as e:
                report["items"].append({
                    "db_id": db_id, "question": question, "sql": sql,
                    "error": f"Schema extraction failed: {e}"
                })
                continue

            # generate Cypher dynamically via LLM
            try:
                cypher = self.gen.question_to_cypher(question, schema)
            except Exception as e:
                report["items"].append({
                    "db_id": db_id, "question": question, "sql": sql,
                    "error": f"LLM generation failed: {e}"
                })
                continue

            # execute SQL and Cypher
            try:
                sql_rows = self.run_sql(db_path, sql)
            except Exception as e:
                report["items"].append({
                    "db_id": db_id, "question": question, "sql": sql, "cypher": cypher,
                    "error": f"SQL exec failed: {e}"
                })
                continue

            try:
                cy_rows = self.run_cypher(cypher)
            except Exception as e:
                report["items"].append({
                    "db_id": db_id, "question": question, "sql": sql, "cypher": cypher,
                    "sql_count": len(sql_rows),
                    "error": f"Cypher exec failed: {e}"
                })
                continue

            # Compare counts as a first-pass exact metric
            match = (len(sql_rows) == len(cy_rows))
            report["items"].append({
                "db_id": db_id,
                "question": question,
                "sql": sql,
                "cypher": cypher,
                "sql_count": len(sql_rows),
                "cypher_count": len(cy_rows),
                "match": match,
                "sql_sample": sql_rows[:5],
                "cypher_sample": cy_rows[:5],
            })

            taken[db_id] = taken.get(db_id, 0) + 1

        return report

    def close(self):
        self.driver.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spider_json", required=True, help="Path to Spider json (e.g., data/spider/dev.json)")
    ap.add_argument("--spider_root", default="data/spider/database", help="Root folder containing DB folders")
    ap.add_argument("--neo4j_uri", default="bolt://localhost:7687")
    ap.add_argument("--neo4j_user", default="neo4j")
    ap.add_argument("--neo4j_pass", required=True)
    ap.add_argument("--per_db", type=int, default=10, help="Max questions per database")
    ap.add_argument("--out", default="evaluation_spider_llm.json")
    args = ap.parse_args()

    ev = SpiderLlmEvaluator(args.neo4j_uri, args.neo4j_user, args.neo4j_pass, args.per_db)
    report = ev.evaluate(args.spider_json, args.spider_root)

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote report to {args.out}")

    # small console summary
    total = len(report["items"])
    matched = sum(1 for it in report["items"] if it.get("match") is True)
    failed = sum(1 for it in report["items"] if it.get("error"))
    print(f"Total evaluated: {total} | Exact matches: {matched} | Errors: {failed}")

    ev.close()


if __name__ == "__main__":
    main()
