# eval/config.py
from pathlib import Path

# === PATHS ===
REPO_ROOT = Path(__file__).resolve().parents[1]

# The Spider ZIP is already in data/spider.zip.
# After your team runs extract.ipynb once, this folder should exist:
SPIDER_DIR = REPO_ROOT / "data" / "spider"            # expects .../spider/database/*.sqlite and dev.json/train_spider.json
SPIDER_DB_DIR = SPIDER_DIR / "database"

# Where we read optional precomputed cypher queries from
CYPHER_ROOT = REPO_ROOT / "eval" / "cypher"

# Where results go
OUTPUT_DIR = REPO_ROOT / "eval" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === EVAL OPTIONS ===
# Which Spider split to use: "dev" (smaller) or "train" (bigger)
SPLIT = "dev"

# How many questions per database (None = all)
QUESTIONS_PER_DB = 10   # start small; you can raise it later

# Limit to certain databases (None = use all in the split)
INCLUDED_DB_IDS = None  # e.g., ["concert_singer"]

# Cypher query mode:
# "precomputed": read cypher from eval/cypher/{db_id}/{qid}.cypher
# "agent": (later) call your LLM/agent to generate cypher
CYPHER_MODE = "precomputed"

# === NEO4J === (fill these when your KG is loaded)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# We compare counts first (your requirement: “100 rows in SQL → 100 in KG”)
COUNT_ONLY = True
