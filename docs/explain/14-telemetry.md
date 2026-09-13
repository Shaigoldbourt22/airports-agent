# 14. Telemetry

`app/telemetry.py` is 50 lines and does one thing: print a JSON object per
event to stdout.

Why that is enough. Azure Container Apps forwards stdout to Log Analytics
automatically. If each line is valid JSON, every field becomes a queryable
column in KQL. No monitoring SDK, no agent sidecar, no extra dependency, no
vendor lock-in. Locally the same lines just show up in your terminal.

Two helpers:

`event(name, **fields)` emits one line. Nulls are dropped so the output stays
readable.

`timed(name, **fields)` is a context manager that wraps a block and logs how
long it took plus whether it succeeded. On failure it records the exception
type and the first 300 characters of the message, then re-raises. Tool calls
and model calls are both wrapped in it, so you can ask "which tool is slow?"
or "how often does Gemini fail?" directly in a query.

The events: `chat_ok`, `chat_failed` (with a reason: rate limited, blocked,
upstream), `tool_call`, `model_call`, `tool_loop_exhausted`, `empty_response`,
`access_denied`, `eval_token_rejected`.

One rule, enforced by convention: **never log message text or attachment
contents.** Only shapes and counts — session id, turn count, reply length,
which tool, which argument names. Not what anyone asked.

This is how the "database is locked" bug was actually found.
