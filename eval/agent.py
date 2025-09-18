
from __future__ import annotations
from pathlib import Path
from typing import Optional
import re
import os

from openai import OpenAI
from .config import DEFAULT_LLM_MODEL, SPIDER_DIR
from .schema_utils import load_tables_json, build_schema_block_for_db

PROMPTS_DIR = Path("llm_prompts")

_SYSTEM = (
    "You are a careful data engineering assistant. "
    "You produce safe, READ-ONLY Cypher for Neo4j. "
    "Return ONLY the Cypher code, no explanations."
)

def _strip_code_fences(text: str) -> str:
    m = re.search(r"```(?:cypher)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()

def _dynamic_prompt(db_id: str) -> Optional[str]:
    tables_json = SPIDER_DIR / "tables.json"
    if not tables_json.exists():
        return None
    items = load_tables_json(tables_json)
    by_id = {it["db_id"]: it for it in items}
    if db_id not in by_id:
        return None
    schema_block = build_schema_block_for_db(db_id, by_id)
    return (
        "You are a data modeling assistant. You are given a database schema in graph form.\n\n"
        f"{schema_block}\n\n"
        "Your job is to answer the user question by producing a **read-only** Cypher query over a Neo4j graph.\n"
        "- Node labels are PascalCase versions of SQL table names (e.g., table `movie_cast` -> label `MovieCast`).\n"
        "- Follow foreign keys as relationships in the direction child -> parent with an upper-snake relationship type.\n"
        "- If the question asks for counts, return a single scalar `count`.\n"
        "- Never write data; only MATCH/WHERE/RETURN.\n"
    )

def _base_prompt(db_id: str) -> Optional[str]:
    manual = PROMPTS_DIR / f"{db_id}_llm_prompt.txt"
    if manual.exists():
        return manual.read_text(encoding="utf-8").strip()
    return _dynamic_prompt(db_id)

def generate_cypher(question: str, db_id: str, model: str = DEFAULT_LLM_MODEL) -> Optional[str]:
    base = _base_prompt(db_id)
    if not base:
        return None

    user = (
        f"{base}\n\n"
        f"User question: {question}\n\n"
        "Rules:\n"
        "- Your Cypher must be READ-ONLY (MATCH/RETURN/WHERE, no writes).\n"
        "- If counting, return a single scalar as `count` (e.g., `RETURN count(n) AS count`).\n"
        "- Do not include explanations, only return the Cypher code."
    )

    if not os.getenv("OPENAI_API_KEY"):
        return None

    client = OpenAI()
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        text = resp.choices[0].message.content or ""
        cypher = _strip_code_fences(text)
        if "match" in cypher.lower() and "return" in cypher.lower():
            return cypher
        return None
    except Exception:
        return None
