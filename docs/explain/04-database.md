# 4. The database

One SQLite file: `data/airports.db`. No server, no password, no cloud
database. It is committed to the repo, so you can clone and immediately ask
questions.

Seven tables:

| Table | One row per | Holds |
|---|---|---|
| `airport` | airport | name, state, coordinates, runway count, longest runway, parallel spacing |
| `enplanement` | airport-year | passengers, previous year, % change, hub class |
| `cargo` | airport-year | landed weight, % change, rank |
| `airport_month` | airport-month | flights, delays, cancellations, diversions |
| `airport_hour` | airport-month-hour | scheduled vs actual arrivals, peak departures |
| `route_month` | route-month | flight count and distance |
| `catchment` | airport | metro name, population, five-year growth |
| `source_meta` | source | URL, fetch date, coverage |

`source_meta` matters more than it looks. It lets the agent answer "how fresh
is this?" honestly instead of guessing.

`airport_hour` is the clever one. For each hour of the day it stores the
busiest single hour that month, both as scheduled and as actually flown. The
gap between them is demand the runways could not absorb.

The app opens the file with `mode=ro&immutable=1`, meaning read-only with
locking switched off entirely. It also checks the file's timestamp on every
query, so when the monthly job drops in a new file the app reconnects with no
restart.
