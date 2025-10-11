
# Knowledge Graph End-to-End Toolkit

This repository combines the relational-data extraction pipeline (`main.py`) with
the yFiles Vue front-end so you can generate, evaluate, and visualise knowledge
graphs in a single run.

## Prerequisites

- Python 3.10+ available on your `PATH`
- Node.js 18+ and npm
- Neo4j Desktop (local) or Neo4j Aura credentials (if you want to load the
  generated metagraph)

## Pipeline Outputs

After a successful run the workspace will contain:

- `extracted_output/`
  - `rds_schema/` – relational schemas exported as JSON
  - `rds_data/` – relational row data in JSON form
  - `kgs_schema/` – knowledge-graph schema JSON returned by the LLM (metadata)
  - `kgs_data/` – knowledge-graph instance data mapped from the RDS export
- `evaluation_summary/evaluation_summary.csv` – per-database metrics with a
  `KGS` column matching the corresponding `*_kgs_data.json` file.

The yFiles Vue app consumes the `kgs_data` (real data) and `kgs_schema`
(metadata) JSON directly from `extracted_output/`, and the evaluation sidebar
reads the CSV to display schema/relationship completeness scores.

## One-Click Execution

1. Double-click `run_end_to_end.bat` (Windows) or run `python run_end_to_end.py`
   from the project root. A desktop window appears for credential entry.
2. Provide:
   - OpenAI API key (required for the GPT-5 based extraction steps)
   - Neo4j Bolt URI, user, and password (defaults are pre-filled from
     `cred.env`, if available)
3. Click **Run End-to-End**. The launcher will:
   - write `cred.env` with the supplied values
   - create/refresh the `.venv` environment and install Python dependencies
   - execute `main.py` to populate `extracted_output/` and
     `evaluation_summary/`
   - install Node dependencies (first run only), build the Vue front-end, and
     serve the compiled site at <http://127.0.0.1:4173/>
4. Your default browser will open the interactive yFiles interface. Leave the
   console window open while exploring; press Enter in the console when you’re
   ready to stop the preview server.

## Neo4j Integration

If you provide valid Neo4j credentials, `main.py` will reset the specified
database and load the first generated schema as a metagraph so you can inspect
it side-by-side with the yFiles UI. Leave the credentials blank to skip this
step.

## Manual Operation

If you prefer to run the pieces yourself:

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

Then browse to <http://127.0.0.1:4173/>.
