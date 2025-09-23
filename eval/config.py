
from pathlib import Path

# === PATHS ===
REPO_ROOT = Path(__file__).resolve().parents[1]

# Spider dataset (unzipped already)
SPIDER_DIR = REPO_ROOT / "data" / "spider"            # contains tables.json, dev.json/train_spider.json, database/*
SPIDER_DB_DIR = SPIDER_DIR / "database"

# Outputs
OUTPUT_DIR = REPO_ROOT / "eval" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === EVAL OPTIONS ===
# SPLIT: "dev" or "train"
SPLIT = "dev"

# Limit to specific db_ids (None = all), e.g. ["concert_singer"]
INCLUDED_DB_IDS = None

# Limit questions per DB (None = all)
QUESTIONS_PER_DB = None

# Count-only comparison (gold SQL wrapped as SELECT COUNT(*) FROM (<sql>) t)
COUNT_ONLY = True

# === LLM ===
# Set OPENAI_API_KEY in your environment before running.
DEFAULT_LLM_MODEL = "gpt-4o-mini"   # or "gpt-5-mini" if you have access

# === NEO4J CONNECTION (your local Neo4j where your KG is loaded) ===
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test1234"  # change if different
