# 6. The tools

A "tool" here is just a Python function the model is allowed to call. There
are eight, all in `app/tools.py`, all plain SQL.

| Tool | Answers |
|---|---|
| `data_coverage` | What is in the database and when was it fetched? |
| `airport_profile` | Basic facts about one airport |
| `traffic_and_delays` | Monthly flights, delay rates, cancellations |
| `peak_hour_demand` | Busiest hour scheduled vs actually flown |
| `route_distance_mix` | How much of the traffic is long haul |
| `cargo_growth` | Fastest-growing freight airports |
| `compare_airports` | Several airports side by side |
| `rank_expansion_candidates` | The ranking, with scores |

They are collected in a `REGISTRY` dictionary. The agent builds Gemini's
function declarations straight from that dictionary and from each function's
type hints and docstring — so the docstring you read is literally what the
model reads. Adding a tool means writing one function; nothing else changes.

Why fixed functions instead of letting the model write SQL? Two reasons. A
fixed function cannot be talked into a query we did not intend, and each one
can be unit-tested. The cost is real: a question outside these eight cannot be
answered at all. That is a trade we made on purpose.

Errors inside a tool are caught and returned to the model as data, so it can
say "that airport is not in the database" instead of crashing.
