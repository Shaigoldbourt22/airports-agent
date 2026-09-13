# Understand this project, one piece at a time

Read these in order. Each page is about 200 words and covers one component.
By the end you should understand the whole thing.

| # | Page | What it covers |
|---|---|---|
| 1 | [The big picture](01-big-picture.md) | What the agent is and how the parts connect |
| 2 | [Where the data comes from](02-data-sources.md) | FAA, BTS, OurAirports, Census |
| 3 | [The ETL job](03-etl.md) | How raw files become one database |
| 4 | [The database](04-database.md) | The tables and why they look like that |
| 5 | [Runway spacing](05-runway-spacing.md) | The physics behind the scoring |
| 6 | [The tools](06-tools.md) | The eight functions the model may call |
| 7 | [The scoring formula](07-scoring.md) | How airports get ranked |
| 8 | [The system prompt](08-system-prompt.md) | The rules the model must follow |
| 9 | [The agent loop](09-agent-loop.md) | Function calling, turn by turn |
| 10 | [The web API](10-api.md) | FastAPI endpoints and validation |
| 11 | [Sessions](11-sessions.md) | Chat history per user |
| 12 | [The UI](12-ui.md) | Chat, voice, file upload |
| 13 | [Auth](13-auth.md) | Google sign-in and the eval token |
| 14 | [Telemetry](14-telemetry.md) | Logs you can actually query |
| 15 | [Tests](15-tests.md) | Two layers, because they fail differently |
| 16 | [CI/CD](16-cicd.md) | Test, stage, grade, promote |
| 17 | [Azure setup](17-azure.md) | What runs where |
| 18 | [Weak spots](18-weak-spots.md) | What you should criticise |
