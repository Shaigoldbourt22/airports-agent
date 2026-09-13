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

## The investment question

For a given region the agent returns a ranked shortlist, and for each airport
four things an analyst needs before committing capital:

| | Answers |
|---|---|
| **Score** | Is demand rising, and will the metro still need the terminal in twenty years? |
| **Airfield pressure** | Would extra gates actually add flights, or do the runways cap it first? |
| **Development need** | What scale of capital does the FAA say the site requires? |
| **Revenue per passenger** | Is the airport already selling well to the traffic it has? |

They stay separate on purpose. Rolled into one number, a site with strong demand
and a saturated airfield is indistinguishable from one where building works —
and those are opposite investments.

The score itself ranks demand, not returns. Project costs and their payback are
not published per airport, so the agent maps where the opportunity is and what
it would take, and says plainly that the final return is outside the data.

## Scoring methodology

Weights are constants in [app/tools.py](../app/tools.py) and sum to 1.

| Score | Weight | | Airfield pressure | Weight |
|---|---|---|---|---|
| `growth` | 0.5 | | `load` | 0.7 |
| `catchment` | 0.5 | | `spacing` | 0.3 |

`growth` is the year-on-year change in enplanements; `catchment` is five-year
metro population growth from the Census ACS, matched by coordinates through the
Census geocoder. They answer different questions — airline schedules move
yearly, a terminal serves its metro for decades — and disagree usefully: Bangor
grew 16% in a metro growing 2.8%, Portland 5% in a metro growing 5.8%.

**Airfield pressure is deliberately not in the score.** Boston has the heaviest
runway load in New England and the weakest demand case; scored together it leads
a terminal ranking, which is exactly where gates cannot help. It carries an
`airfield_constrained` flag instead, and the prompt requires the answer to say
that a terminal alone adds no flights there.

Three decisions worth defending:

- **`load` is one component, not two.** Enplanements per runway and peak
  departures per runway correlate at **r = 0.92** nationally, so scoring them
  separately would double the weight on one quantity while presenting it as two
  signals. Metro *population* is excluded for the same reason — r = 0.99 against
  enplanements per runway.
- **Scores are peer-relative.** `growth`, `catchment` and `load` are min-max
  normalised within the candidate set, so ask for New England and the leader
  scores against New England, not the nation.
- **`spacing` is a rule, not a normalisation.** Parallels under 1,200 ft apart
  are worked as a single runway and score 100; under 2,500 ft they lose
  independent approaches in poor visibility and score 60; otherwise 0.
  Normalising would make the worst airport in a mildly constrained set look
  critical.

Airports below 250,000 enplanements are excluded as noise. Any airport missing
an input is returned under `unscored_missing_data` with the reason, and the
prompt requires naming it — the airport that cannot be scored is often the one
worth investigating. Gate counts are published by no federal dataset, so the
score measures the demand a terminal would serve rather than how full the
existing one is, and the agent may never invent a gate number.

## Cost and revenue

Two FAA figures are reported next to the ranking without entering it.

`development_need_usd` (NPIAS) is the FAA's five-year estimate of eligible
development cost. Per passenger it shows the scale of capital a site needs: $43
at Boston against $124 at Burlington. It is needed rather than funded spend and
covers airside work too, so it is not a project price.

`non_aero_revenue_per_enplanement` (Form 127) is what an airport earns per
passenger from food, retail, parking and car hire. Heavy traffic with a thin
take per head means the passengers are already inside and the airport is not
selling to them — which landing fees, tied to aircraft weight, cannot show.

Neither is scored: a cost is not a return, and a whole-airport figure a year
behind the flight data is not one terminal's takings. Gate leases, bond
covenants, airline yields and slot caps are published per airport nowhere, so
the agent can say where demand and constraint are, but never what a project
would return.

## Where AI is used, and where it is not

The model **chooses tools and writes prose**. It never computes.

- Every figure comes from a tool result. The prompt
  ([prompts/system.md](../prompts/system.md)) forbids estimating, recalling, or
  doing arithmetic — an average of twelve monthly figures is a number no tool
  returned, and it reads as measured when it is not.
- Scores, rankings, delay rates and filters are plain SQL and a fixed formula,
  asserted reproducible by [tests/test_tools.py](../tests/test_tools.py).
- The prompt carries the domain judgement: normalise congestion rather than
  comparing raw volume, explain causes physically, name chosen thresholds as
  ours, and commit to a verdict when asked to compare.

Uploaded files are treated as data, never instructions, and the agent flags any
file that tries to change its rules.

## Key tradeoffs

**SQLite over a hosted database.** One file, replaced atomically by the ETL job.
But it sits on an SMB share that ignores byte-range locks, so it is opened
`immutable=1` and the app runs a single replica. Right for an analyst tool,
wrong for scale.

**Precomputed over live API calls.** Fast, reproducible, and a BTS outage cannot
break it. The data is a month behind, which for capital planning is irrelevant.

**Function calling over text-to-SQL.** A fixed tool set cannot be talked into a
query we did not intend, and each tool is testable. The limit: a question
outside the tools cannot be answered at all.

**Runways as the airfield denominator.** Available for every airport, but blind
to terminal floor area. An airport can be runway-rich and gate-poor and this
scoring will not see it.

**A model as test judge.** Golden answers are prose with no single correct
wording, so a second Gemini call grades them against a rubric. Cheaper than
hand-review, but non-deterministic — which is why the deterministic tests exist
separately.

## Testing and delivery

- **Deterministic** ([tests/test_tools.py](../tests/test_tools.py)) — scoring is
  reproducible, weights sum to 1, scores match their components. Blocks the
  pipeline.
- **Golden questions** ([tests/golden.yaml](../tests/golden.yaml)) — the four
  assignment questions with required tool calls and a rubric, run against a
  deployed evaluation app.

[The pipeline](../.github/workflows/deploy.yml) builds one image, deploys it to
the evaluation app, asks it the golden questions, and promotes **that same
image** to production only if it answers them.

## Assumptions and scope

- US airports only, US carriers only. BTS does not see foreign carriers, so
  routes like Condor's ANC-Frankfurt are invisible, and all-cargo operators are
  excluded too — which matters most at Anchorage, where most long-haul
  departures are freight.
- "Long haul" is 3,000 miles. No FAA, BTS, ICAO or IATA standard exists; the
  agent states the value and says it is ours.
- FAA enplanement figures are preliminary.
- Gate counts and terminal floor area are absent from every free source, so
  terminal need is scored from demand, not measured from capacity.

Voice input uses the browser Web Speech API, on-device where available, with
text chat as the fallback.

Data sources: [DATA_SOURCES.md](DATA_SOURCES.md).
