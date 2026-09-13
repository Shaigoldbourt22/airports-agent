# 16. CI/CD

`.github/workflows/deploy.yml`. Every push to main goes through this.

1. **test** — install and run `pytest`. Fixture database, no API key. Fast.
2. **staging** — build one container image tagged with the commit SHA, deploy
   it to the *evaluation* app, then poll `/healthz` until it answers 200.
3. **golden** — run `pytest -m llm` against that running evaluation app.
4. **app** — if the golden questions passed, point production at **that exact
   image**. Not a rebuild. The artefact the tests passed against is the
   artefact users get.

That is eval-then-promote: a bad answer blocks the deploy, not just a bad
unit test.

The ETL image is handled separately, and carefully. A `changes` job uses a
path filter to see whether `etl/`, `Dockerfile.etl` or `requirements-etl.txt`
changed. Only then is the ETL image rebuilt and the scheduled job repointed at
it. And the job is **never started** by a push — the monthly cron is the only
thing that triggers a data fetch. There is a manual "Run workflow" button with
`run_etl=true` for when you really want one.

No secrets are stored for Azure. GitHub authenticates with OIDC: it presents a
short-lived token proving which repo and branch it is, and Azure trusts a
federated credential matching that exact subject.
