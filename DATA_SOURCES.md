# Data Sources

## Used

| Source | What it is and what it gives us | How we fetch it |
|---|---|---|
| BTS On-Time Performance | Per-flight records; gives delays, distances, cancellations, scheduled vs actual times | Monthly PREZIP zip |
| FAA Passenger Boarding | Annual boarding census; gives enplanements, hub class, year-over-year change | Annual XLSX download |
| FAA All-Cargo Airports | Annual cargo census; gives landed weight and cargo rank per airport | Annual XLSX download |
| Airport terminal maps | Published by each airport authority; gives gate counts, where any exist | Manual, via Wikipedia citation |

## Available, not used yet

| Source | What it is and what it gives us | How we fetch it |
|---|---|---|
| FAA OPSNET | FAA air traffic counting system; gives monthly operations and delays per airport | Form POST, HTML table |
| FAA Airport Capacity Profiles | FAA runway throughput study; gives hourly capacity for major airports | Static PDF download |
| FAA Airport Categories | Legal hub definitions; gives thresholds that sort airports into size classes | Static web page |
| FAA NPIAS | National airport plan; gives which airports count as public-use infrastructure | Static report download |
| FAA NASR / Form 5010 | Official facility register; gives runway counts, lengths and surfaces | 28-day cycle zip |
| FAA NOTAM API | Live notices; gives current arrival-rate and runway restrictions | REST API, free key |
| BTS T-100 Segment | Per-route traffic report; gives passengers, freight and mail tonnage | Annual PREZIP zip |
| BTS latest-available table | Publication tracker; gives how stale each BTS dataset currently is | Static web page |
| OurAirports | Community airport database; gives codes, coordinates, regions and runway details | Static CSV download |

## Rejected

| Source | Why |
|---|---|
| FAA ASPM | Richest congestion data, but login-only, so results are not reproducible |
| Wikidata | Queried for gate counts; property P7538 is empty for every airport we need |

## Known gaps

- **Gate counts for MHT and PWM** — unpublished anywhere, so both are excluded from terminal scoring.
- **Terminal floor area** — no free public dataset carries it for any airport.
- **Foreign carriers** — BTS covers US carriers only, so routes like Condor's ANC–Frankfurt are invisible.
- **"Long haul" distance** — no FAA, BTS, ICAO or IATA standard exists; our 3,000-mile cutoff is a choice.
