# 2. Where the data comes from

Four free public sources. No paid data, no scraping tricks.

**OurAirports** — a community-maintained list of every airport on Earth. We
take the US ones: name, city, state, coordinates, and every runway with its
length and the exact position of both ends. Those runway-end coordinates are
what lets us compute how far apart parallel runways sit.

**FAA enplanements** — an annual spreadsheet of how many passengers boarded at
each US airport, plus last year's figure, the percentage change, and the hub
class (large, medium, small, non-hub). This is the demand signal.

**FAA all-cargo** — the same idea for freight, measured in landed weight.

**BTS On-Time Performance** — the big one. One row per commercial flight in the
US: scheduled time, actual time, delay, cancellation, distance. A single month
is a few million rows. We download twelve months.

**US Census (ACS)** — metro area population now and five years ago, so we know
whether the region an airport serves is growing or shrinking.

Two honest limits. BTS only sees US carriers, so foreign airlines are
invisible. And nobody publishes gate counts or terminal floor area for free,
which is awkward for a tool about terminal expansion.
