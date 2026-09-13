# Data Sources

| Source | What it is and what it gives us | How we fetch it |
|---|---|---|
| BTS On-Time Performance | Per-flight records; gives delays, distances, cancellations, scheduled vs actual times | Monthly PREZIP zip |
| FAA Passenger Boarding | Annual boarding census; gives enplanements, hub class, year-over-year change | Annual XLSX download |
| FAA All-Cargo Airports | Annual cargo census; gives landed weight and cargo rank per airport | Annual XLSX download |
| FAA NPIAS Appendix A | Five-year development cost estimate per airport | Single XLSX download |
| FAA CATS Form 5100-127 | Annual airport financials: revenue split aeronautical and non-aeronautical, expenses, capital spending, debt | HTML report per airport |
| OurAirports | Community airport database; gives codes, locations, runway counts, lengths and spacing | Static CSV download |
| Census ACS 1-year | Metro population by CBSA; gives the five-year growth of the catchment an airport serves | REST API, free key |
| Census Geocoder | Resolves airport coordinates to the metro area containing them | REST API, no key |

## Known gaps

- **Gate counts** — no federal dataset publishes them, so runways stand in as the
  capacity denominator for terminal scoring.
- **Terminal floor area** — no free public dataset carries it for any airport.
- **Foreign carriers** — BTS covers US carriers only, so routes like Condor's ANC–Frankfurt are invisible.
- **All-cargo operations** — BTS covers scheduled passenger flights only, so
  freighters are absent. It matters most at Anchorage, where most long-haul
  departures are cargo.
- **"Long haul" distance** — no FAA, BTS, ICAO or IATA standard exists; our 3,000-mile cutoff is a choice.
- **Live constraints** — the database is rebuilt monthly, so same-day runway
  closures and arrival-rate restrictions are not reflected.
- **Slot caps and curfews** — not published as data, though they hold some US
  airports below what their runways could take.
- **Deal-level finance** — gate leases, bond covenants and airline yields sit in
  official statements and private agreements, not in any per-airport feed.
