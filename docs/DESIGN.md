# Design

What the agent is and how to run it: [README](../README.md).
This document covers the reasoning behind it.

## How it fits together

```
Browser (chat, voice, file upload)
  -> FastAPI  app/main.py        auth, session history, request validation
  -> Agent    app/agent.py       Gemini 2.5 Flash, function calling loop
  -> Tools    app/tools.py       fixed SQL and the scoring formula
  -> SQLite   data/airports.db   built monthly by etl/build_db.py
```

The database is rebuilt by a scheduled Container Apps job on the 8th of each
month, ten weeks behind BTS publication so a fresh month is always available.
It lands on an Azure Files share that the web app reads.

## Scoring methodology

`rank_expansion_candidates` scores terminal-expansion candidates with four
weighted components. The weights are constants in [app/tools.py](../app/tools.py)
and sum to 1:

| Component | Weight | Why |
|---|---|---|
| `load` | 0.35 | How hard the existing runways are already worked |
| `growth` | 0.25 | Rising airline demand is the reason to build at all |
| `catchment` | 0.25 | Whether the metro the terminal would serve is growing |
| `spacing` | 0.15 | Whether runway geometry caps arrivals in poor weather |

`load` averages enplanements per runway and peak departures per runway. They
were separate components until measurement showed they correlate at **r = 0.92**
nationally: the score was putting half its weight on one underlying quantity
while presenting it as two independent signals. Collapsing them left room for a
factor that genuinely differs, and the remaining components now correlate no
higher than 0.38.

`catchment` is five-year metro population growth from the Census ACS, matched to
the airport by coordinates through the Census geocoder. It answers a different
question from `growth`: an airline schedule changes yearly, but a terminal has
to serve its metro for decades, and the two disagree usefully. Bangor's
enplanements rose 16% in a metro growing 2.8%; Portland's rose 5% in a metro
growing 5.8%. Metro *population* was tested and rejected — it tracks
enplanements per runway at r = 0.99, so it would have added weight without
adding information.

`load`, `growth` and `catchment` are min-max normalised to 0-100 **within the
candidate set**, so a score is relative to the peers being compared, not a
national rating. Ask for New England and the leader scores against New England.

`spacing` is the exception: it is scored on the FAA separation rule rather than
normalised. Parallels under 1,200 ft apart are worked as a single runway and
score 100; under 2,500 ft they cannot take independent approaches in poor
visibility and score 60; anything else scores 0. Normalising it would make the
worst airport in a set of mildly constrained ones look critical. This is the one
component that measures a constraint no amount of spending inside the fence can
fix.

An airport missing any input is never silently dropped. It is returned under
`unscored_missing_data` with the specific input it lacks, and the prompt
requires the answer to name it: the airport that cannot be scored is often the
one worth investigating.

Airports below 250,000 annual enplanements are excluded; below that the
percentage swings are noise rather than signal.

Runways are the capacity denominator. Gates would be the honest measure, but no
federal dataset publishes gate counts, so runways stand in. The agent is
instructed never to invent a gate number.

`cargo_growth` applies the same idea in reverse: a minimum landed weight filters
out airports posting +100% on a few tonnes, and the excluded ones are returned
so the filter can be reported rather than hidden.

## Where AI is used, and where it is not

The model **chooses tools and writes prose**. It never computes.

- Every figure in an answer comes from a tool result. The system prompt in
  [prompts/system.md](../prompts/system.md) forbids estimating or recalling
  numbers, and requires saying which data is missing instead.
- Scores, rankings, delay rates and filters are plain SQL and a fixed formula.
  The same question always returns the same score, which is asserted by
  [tests/test_tools.py](../tests/test_tools.py).
- The prompt carries the domain judgement: normalise congestion rather than
  comparing raw volume, explain causes physically (runway spacing under FAA
  separation rules), name chosen thresholds as ours, and commit to a verdict
  when asked to compare.

Uploaded files are treated as data, never as instructions, and the agent is told
to flag a file that tries to change its rules.

## Key tradeoffs

**SQLite over a hosted database.** One file, no server, and the ETL job can
replace it atomically. The cost is that it sits on an SMB share, which does not
honour the byte-range locks SQLite normally takes; the volume is mounted `nobrl`
and the app runs a single replica. Fine for an analyst tool, wrong for scale.

**Precomputed database over live API calls.** Answers are fast and reproducible,
and a BTS outage cannot break a demo. The data is a month behind, which for
capital-planning questions is irrelevant.

**Function calling over text-to-SQL.** A fixed set of tools cannot be talked
into a query we did not intend, and each one is independently testable. The
limit is that a question outside the tools cannot be answered at all.

**Runways as the capacity denominator.** Defensible and available for every
airport, but it ignores terminal floor area and gate count entirely. An airport
can be runway-rich and gate-poor, and this scoring will not see it.

**A model as test judge.** The golden answers are prose with no single correct
wording, so a second Gemini call grades them against a rubric. Cheaper than
hand-review, but it is a non-deterministic gate — which is why the deterministic
scoring tests exist separately and run on every push.

## Testing and delivery

Two layers, because they fail differently:

- **Deterministic** ([tests/test_tools.py](../tests/test_tools.py)) — scoring is
  reproducible, weights sum to 1, scores match their components, ranking is
  ordered and bounded. Runs on every push and blocks the pipeline.
- **Golden questions** ([tests/golden.yaml](../tests/golden.yaml)) — the four
  assignment questions, each with required tool calls and a rubric. Run against
  a deployed evaluation app.

The pipeline in [.github/workflows/deploy.yml](../.github/workflows/deploy.yml)
builds one image, deploys it to the evaluation app, asks it the golden
questions, and promotes **that same image** to production only if it answers
them. The ETL image is rebuilt only when ETL code changes, and a data fetch is
never triggered by a push.

## Assumptions and scope

- US airports only, US carriers only. BTS does not see foreign carriers, so
  routes like Condor's ANC-Frankfurt are invisible.
- "Long haul" is 3,000 miles. No FAA, BTS, ICAO or IATA standard exists; the
  agent states the value and says it is ours.
- FAA enplanement figures are preliminary.
- Gate counts and terminal floor area are absent from every free source, so
  terminal capacity is approximated, not measured.

Voice input uses the browser Web Speech API, on-device where available, with
text chat as the fallback.

Data sources and known gaps: [DATA_SOURCES.md](DATA_SOURCES.md).
