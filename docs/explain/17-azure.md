# 17. Azure setup

Everything sits in one resource group, `airports-agent-rg`.

**Container registry** — holds two images: the web app and the ETL job. Both
tagged by commit SHA, so you can always tell what is running.

**Container Apps environment** — the shared network and logging home for
everything below.

**The production app** (`airports-agent`) — the FastAPI container. Google
sign-in in front of it. One replica, on purpose. Scales to zero when nobody is
using it, which is why the first request of the day is slow.

**The evaluation app** (`airports-agent-eval`) — the same image, no sign-in, a
bearer token instead, and `EXPOSE_TRACE=1` so tests can see tool calls. It
writes its sessions to a different directory so test traffic never lands in
real history.

**The ETL job** — a Container Apps *job*, not an app. It has no web server; it
wakes on a cron schedule (`0 6 8 * *`, the 8th of each month), rebuilds the
database, and exits. The 8th is chosen because BTS publishes about ten weeks
behind, so a fresh month is reliably available.

**Azure Files share** — a single storage share mounted at `/data` in both the
job and the app. The job writes the database, the app reads it. This is the
SMB share that caused all the SQLite locking pain.

**Log Analytics** — collects stdout, queried with KQL.
