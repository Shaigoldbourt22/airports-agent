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
