# Knowledge Graph End-to-End Toolkit

This repository combines the relational-data extraction pipeline (`main.py`)
with a yFiles + Vue front-end so that you can extract, evaluate, and visualise
knowledge graphs end to end.

## Prerequisites

- Python 3.10 or newer available on `PATH`
- Node.js 18 or newer (which ships with `npm`)
- Neo4j Desktop/Aura credentials (only if you want the optional metagraph load)
- A yFiles for HTML licence package (`yfiles-*.tgz`). Replace the placeholder
  file in `yfiles-vue-integration-basic-master/` with your own licence before
  running the setup script.

## Pipeline Outputs

After a successful run you will find:

- `extracted_output/`
  - `rds_schema/` – relational schema exports (JSON)
  - `rds_data/` – relational data exports (JSON)
  - `kgs_schema/` – LLM-generated knowledge-graph schema metadata (JSON)
  - `kgs_data/` – knowledge-graph instance data mapped from the RDS export (JSON)
- `evaluation_summary/evaluation_summary.csv` – per-database metrics with a
  `KGS` column matching the corresponding `*_kgs_data.json` file

The Vue/yFiles UI reads directly from these folders when rendering graphs.

## First-Time Setup (Windows)

1. Copy your licensed `yfiles-*.tgz` into
   `yfiles-vue-integration-basic-master/` (overwrite the placeholder if present).
2. Double-click `setup_and_run.ps1` (or run
   `powershell -ExecutionPolicy Bypass -File setup_and_run.ps1`).
   - The script creates a `.venv`, installs Python requirements, runs
     `npm install`, and builds the yFiles front-end.
   - Pass `-SkipRun` if you only want to install dependencies without launching
     the UI.
3. When the GUI appears, provide:
   - OpenAI API key (required for the GPT-5 pipeline steps)
   - Neo4j Bolt URI, user, and password (defaults are pre-filled from `cred.env`
     when available)
4. The launcher then:
   - writes your credentials to `cred.env`
   - executes `main.py` to populate `extracted_output/` and `evaluation_summary/`
   - builds the Vue/yFiles front-end and serves it at
     <http://127.0.0.1:4173/>
5. Keep the console window open while exploring the UI; press Enter in that
   window to stop the preview server when you are done.

## Subsequent Runs

Once the environment is prepared, simply double-click `run_end_to_end.bat`
(or run `python run_end_to_end.py`) to reopen the launcher without reinstalling
dependencies.

## Neo4j Integration

When valid Neo4j credentials are supplied, `main.py` resets the specified
database and loads the first generated schema as a metagraph so you can inspect
it alongside the yFiles UI. If you skip credentials, this step is silently
ignored.

## Manual Operation

If you want to run everything manually instead of using the helper scripts:

```powershell
# Configure credentials
Set-Content cred.env @"
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=sk-...
"@

# Python environment & pipeline
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python main.py

# Front-end
cd yfiles-vue-integration-basic-master
npm install
npm run build
cd dist
python -m http.server 4173
```

Then browse to <http://127.0.0.1:4173/>. Press Ctrl+C in the terminal to stop
the preview server.
