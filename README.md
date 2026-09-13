# Airport Investment Intelligence Agent

An agent that helps analysts find US airports where modernization is most
likely to pay off. It answers in prose, but every figure comes from a
deterministic tool, never from the model.

**Try it:** [airports-agent.victoriousgrass-4e3f5a75.eastus.azurecontainerapps.io](https://airports-agent.victoriousgrass-4e3f5a75.eastus.azurecontainerapps.io)
— sign in with any Google account. Sign-in only separates one person's chat
history from another's; it is not a restriction.

**Source:** [github.com/Shaigoldbourt22/airports-agent](https://github.com/Shaigoldbourt22/airports-agent)

Design and scoring methodology: [docs/DESIGN.md](docs/DESIGN.md).
Data sources: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # add your GEMINI_API_KEY
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Then open http://localhost:8000.

`data/airports.db` is committed, so there is nothing to download first. It is a
snapshot; the deployed app refreshes its own copy monthly. To rebuild it:

```powershell
.\.venv\Scripts\pip install -r requirements-etl.txt
.\.venv\Scripts\python etl\build_db.py --months 12
```

Downloads are cached, so a second run takes about a minute rather than half an
hour. Add `--refresh` to fetch every source again.

## Tests

```powershell
pytest              # deterministic scoring checks, no API calls
pytest -m llm       # golden questions against a deployment; needs AGENT_URL
```

## Layout

| Path | What lives there |
|---|---|
| `app/` | FastAPI service, agent loop, tools, session store |
| `prompts/` | The system prompt |
| `etl/` | Builds `data/airports.db` from FAA, BTS, OurAirports and Census sources |
| `static/` | Chat UI |
| `tests/` | Scoring tests and the golden questions |
| `deploy/` | Script that creates the scheduled ETL job |
