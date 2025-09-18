
from __future__ import annotations
from typing import Dict, Any, List
from .config import SPIDER_DIR, INCLUDED_DB_IDS, QUESTIONS_PER_DB, SPLIT
import json

def load_split_items() -> List[Dict[str, Any]]:
    """
    Load Spider split:
      - dev.json if SPLIT == "dev"
      - train_spider.json if SPLIT == "train"
    """
    if SPLIT == "dev":
        p = SPIDER_DIR / "dev.json"
    elif SPLIT == "train":
        p = SPIDER_DIR / "train_spider.json"
    else:
        raise ValueError("SPLIT must be 'dev' or 'train'")

    items = json.loads(p.read_text(encoding="utf-8"))

    if INCLUDED_DB_IDS:
        items = [it for it in items if it["db_id"] in INCLUDED_DB_IDS]

    if QUESTIONS_PER_DB is not None:
        bydb: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            bydb.setdefault(it["db_id"], []).append(it)
        trimmed = []
        for db_id, arr in bydb.items():
            trimmed.extend(arr[:QUESTIONS_PER_DB])
        items = trimmed

    return items
