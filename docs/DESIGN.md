# Design

- **AI service**: Google Gemini free tier, function calling to pick tools and explain rankings.
- **Voice recognition**: browser Web Speech API, on-device when available, text chat as fallback.
- **Deployment**: Azure only — single Container App serving both the API and chat UI.
- **Testing**: pytest unit tests for scoring, golden-question tests for agent answers.
- **Data sources**: see [DATA_SOURCES.md](DATA_SOURCES.md).
- **Scoring**: deterministic weighted KPI of congestion, unmet demand, growth; LLM only explains.
