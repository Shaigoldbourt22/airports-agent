# Data Sources

| Source | What it is and what it gives us | How we fetch it |
|---|---|---|
| BTS On-Time Performance | Per-flight records; gives delays, distances, cancellations, scheduled vs actual times | Monthly PREZIP zip |
| FAA Passenger Boarding | Annual boarding census; gives enplanements, hub class, year-over-year change | Annual XLSX download |
| FAA All-Cargo Airports | Annual cargo census; gives landed weight and cargo rank per airport | Annual XLSX download |
| FAA NPIAS Appendix A | National plan of airport systems; gives the FAA's own five-year development cost estimate per airport | Single XLSX download |
| FAA CATS Form 5100-127 | Each airport's annual financial filing; gives operating revenue split aeronautical and non-aeronautical, expenses, capital spending by category, and debt | HTML report, one request per airport |
| OurAirports | Community airport database; gives codes, locations, runway counts, lengths and spacing | Static CSV download |
| Census ACS 1-year | Metro population by CBSA; gives the five-year growth of the catchment an airport serves | REST API, free key |
| Census Geocoder | Resolves airport coordinates to the metro area containing them | REST API, no key |

## Known gaps

- **Gate counts** — no federal dataset publishes them, so runways stand in as the
  capacity denominator for terminal scoring.
- **Terminal floor area** — no free public dataset carries it for any airport.
- **Foreign carriers** — BTS covers US carriers only, so routes like Condor's ANC–Frankfurt are invisible.
- **All-cargo operations** — BTS On-Time covers scheduled passenger flights on
  reporting US carriers, so freighters are absent. It matters most at Anchorage,
  where most long-haul departures are cargo.
- **"Long haul" distance** — no FAA, BTS, ICAO or IATA standard exists; our 3,000-mile cutoff is a choice.
- **Live constraints** — the database is rebuilt monthly, so same-day runway
  closures and arrival-rate restrictions are not reflected.
- **Slot caps and curfews** — not published as data. Several US airports are held
  below what their runways could take by legal agreement rather than physics,
  and nothing here records it.
- **Deal-level finance** — gate lease terms, bond covenants, debt service
  coverage and airline yields sit in official statements and private agreements,
  not in any per-airport feed.

## A source we wrongly recorded as unavailable

Form 127 was first written off here. Its CSV export returns HTTP 500 on every
form and year tried, and passing `loc_id=BOS` returns the empty form, so the
conclusion was that the data could not be fetched.

Both observations were true and the conclusion was wrong. The export is one
endpoint, and the ignored parameter was the wrong key: the site addresses
airports by an internal numeric id, and BOS is 2352. The HTML report works, for
668 airports back to 1995, and it carries the most useful money in the project.

Two details make the parse survive: line items are matched on their numbering,
which is stable across editions, rather than their wording, which drifts; and
the airport code is read from each report page, because the `loc_id` and
`airportID` dropdowns are sorted differently and pairing them by position maps
BOS to Chevak.
