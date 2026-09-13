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

The question is which airports would repay a terminal, so the score holds only
what a terminal can serve. The weights are constants in
[app/tools.py](../app/tools.py) and sum to 1:

| Component | Weight | Why |
|---|---|---|
| `growth` | 0.5 | Rising airline demand is the reason to build at all |
| `catchment` | 0.5 | Whether the metro the terminal would serve is growing |

Runway pressure is measured too, but kept out of the score and reported beside
it as `airfield_pressure`, from `load` (0.7) and `spacing` (0.3):

| Component | Weight | Why |
|---|---|---|
| `load` | 0.7 | How hard the existing runways are already worked |
| `spacing` | 0.3 | Whether runway geometry caps arrivals in poor weather |

The two were one score until the separation was forced by its own output.
Boston came first for terminal expansion on the strength of the heaviest runway
load in New England and the tightest parallel spacing, while the answer
explaining the result had to admit that a terminal there would add no flights,
because the runways cap the airport before the gates do. A score that ranks an
airport first on the very measure that makes the project pointless is measuring
the wrong thing. Airfield pressure now travels with an `airfield_constrained`
flag instead, and the prompt requires the answer to say plainly that gates alone
will not add throughput where it is set.

`load` averages enplanements per runway and peak departures per runway. They
were separate components until measurement showed they correlate at **r = 0.92**
nationally: the score was putting half its weight on one underlying quantity
while presenting it as two independent signals.

`catchment` is five-year metro population growth from the Census ACS, matched to
the airport by coordinates through the Census geocoder. It answers a different
question from `growth`: an airline schedule changes yearly, but a terminal has
to serve its metro for decades, and the two disagree usefully. Bangor's
enplanements rose 16% in a metro growing 2.8%; Portland's rose 5% in a metro
growing 5.8%. Metro *population* was tested and rejected — it tracks
enplanements per runway at r = 0.99, so it would have added weight without
adding information.

`growth`, `catchment` and `load` are min-max normalised to 0-100 **within the
candidate set**, so a score is relative to the peers being compared, not a
national rating. Ask for New England and the leader scores against New England.

`spacing` is the exception: it is scored on the FAA separation rule rather than
normalised. Parallels under 1,200 ft apart are worked as a single runway and
score 100; under 2,500 ft they cannot take independent approaches in poor
visibility and score 60; anything else scores 0. Normalising it would make the
worst airport in a set of mildly constrained ones look critical. This is the one
measure that describes a constraint no amount of spending inside the fence can
fix.

## Cost and revenue

Two figures come from the FAA and are reported next to the ranking without
entering it.

`development_need_usd` is the FAA's own five-year estimate of eligible
development cost, from the NPIAS. Divided by annual passengers it gives the
scale of capital a site needs per passenger it already serves — $43 at Boston
against $124 at Burlington. It is needed development rather than funded spend,
and it covers airside work as well as terminal work, so it is not a project
price.

`non_aero_revenue_per_enplanement` comes from each airport's own Form 127
filing: what it earns per passenger from food, retail, parking and car hire.
This is the closest thing available to a return on a terminal, because heavy
traffic with a thin take per head means the passengers are already inside and
the airport is not selling to them. Aeronautical revenue cannot show that, since
landing fees follow aircraft weight rather than the quality of the terminal.

Neither is scored. A cost is not a return, and a whole-airport revenue figure a
year or two behind the flight data cannot be read as one terminal's takings.
They describe an airport; they do not rank it.

What is still missing is worth stating: gate lease terms, bond covenants and
debt service coverage, airline yields, and slot caps or curfews. None is
published per airport in a form that can be fetched, so the agent can say where
demand and constraint are, what capital is needed, and what a site currently
earns per passenger — but never what a specific project would return.

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
  numbers, and requires saying which data is missing instead. Arithmetic counts
  as inventing: the grounding check caught a long-haul share of 4.8% that no
  tool returned, because the model had averaged twelve monthly percentages, and
  a computed average reads as measured when it is not.
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
