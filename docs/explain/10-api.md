# 10. The web API

`app/main.py` is a small FastAPI app. Five endpoints:

| Endpoint | Does |
|---|---|
| `GET /` | Serves the chat page |
| `POST /api/chat` | Ask a question, get an answer |
| `GET /api/sessions` | List your past chats |
| `GET /api/sessions/{id}` | Reopen one |
| `DELETE /api/sessions/{id}` | Delete one |
| `GET /healthz` | Says "ok" — used by the deploy pipeline |

Every request body is validated by Pydantic before any code runs. That is the
security boundary:

- Message text capped at 4,000 characters, 40 messages per request.
- At most 5 attachments, each under 8 MB.
- File types restricted to an allowlist: PNG, JPEG, WebP, GIF, PDF, plain
  text, CSV. Anything else is rejected.
- Attachment data must decode as valid base64, checked strictly.

`POST /api/chat` calls the agent, maps each failure type to the right HTTP
status (503 not configured, 429 quota, 422 blocked, 502 upstream), then saves
both the question and the answer to the session store and returns the reply
with a session id.

One optional field: `trace`. It is only populated when `EXPOSE_TRACE=1`, which
the evaluation deployment sets so tests can inspect tool calls. Production
leaves it off, because the trace exposes query internals to end users.
