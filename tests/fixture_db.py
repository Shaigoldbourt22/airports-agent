"""A small database with known values, built from the real schema.

The scoring tests need data that never changes, so the expected score for a
given airport can be written down rather than read back from whatever the last
ETL run produced. Six airports are enough to exercise ranking, the small-base
cargo filter, distance thresholds and missing-data handling.

The schema is read out of etl/build_db.py, so a column added there without a
matching change here fails the tests instead of silently drifting. It is read
as text rather than imported, because importing the ETL would pull in its
data-processing dependencies for no benefit.
"""

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _schema() -> str:
    """The CREATE statements from the ETL, without importing it."""
    source = (ROOT / "etl" / "build_db.py").read_text(encoding="utf-8")
    match = re.search(r'^SCHEMA = """(.*?)"""', source, re.DOTALL | re.MULTILINE)
    if not match:
        raise RuntimeError("SCHEMA not found in etl/build_db.py")
    return match.group(1)


# iata, icao, name, city, state, region, lat, lon, runways, longest_ft, parallel_ft
AIRPORTS = [
    ("BIG", "KBIG", "Big Hub", "Bigtown", "MA", "US-MA", 42.0, -71.0, 4, 11000, 800),
    ("GRW", "KGRW", "Growing Regional", "Growville", "RI", "US-RI", 41.7, -71.4, 2, 8000, 3000),
    ("FLT", "KFLT", "Flat Field", "Flatton", "CT", "US-CT", 41.9, -72.7, 2, 9000, None),
    ("TNY", "KTNY", "Tiny Strip", "Tinyville", "VT", "US-VT", 44.5, -73.2, 1, 5000, None),
    # No runway count, so it cannot be scored and must be reported as such.
    ("NRW", "KNRW", "No Runway Data", "Nowhere", "NH", "US-NH", 43.0, -71.5, 0, None, None),
    ("CGO", "KCGO", "Cargo Field", "Freightburg", "ME", "US-ME", 44.8, -68.8, 2, 11500, None),
]

# iata, year, enplanements, prev_year, pct_change, hub, rank
ENPLANEMENTS = [
    ("BIG", 2025, 20_000_000, 20_100_000, -0.005, "L", 1),
    ("GRW", 2025, 2_000_000, 1_800_000, 0.1111, "S", 2),
    ("FLT", 2025, 3_000_000, 3_000_000, 0.0, "S", 3),
    ("TNY", 2025, 400_000, 380_000, 0.0526, "N", 4),
    ("NRW", 2025, 700_000, 650_000, 0.0769, "N", 5),
    ("CGO", 2025, 500_000, 495_000, 0.0101, "N", 6),
]

# iata, year, landed_lbs, prev_lbs, pct_change, rank
CARGO = [
    ("CGO", 2025, 2_000_000_000, 1_500_000_000, 0.3333, 1),
    ("BIG", 2025, 900_000_000, 1_000_000_000, -0.1, 2),
    ("FLT", 2025, 400_000_000, 380_000_000, 0.0526, 3),
    # Large percentage on a base too small to mean anything.
    ("TNY", 2025, 30_000, 10_000, 2.0, 4),
]

# iata, year, month, departures, arrivals, dep_del15, arr_del15,
# dep_delay_min, arr_delay_min, cancelled, diverted, longhaul_dep
AIRPORT_MONTH = [
    ("BIG", 2026, 6, 10_000, 10_000, 2_000, 1_800, 100_000, 90_000, 100, 20, 500),
    ("BIG", 2026, 7, 12_000, 12_000, 3_600, 3_000, 180_000, 150_000, 240, 30, 700),
    ("GRW", 2026, 6, 2_000, 2_000, 300, 280, 12_000, 11_000, 10, 2, 0),
    ("GRW", 2026, 7, 2_200, 2_200, 330, 300, 13_000, 12_000, 11, 2, 0),
    ("FLT", 2026, 6, 3_000, 3_000, 600, 550, 30_000, 28_000, 30, 5, 0),
    ("TNY", 2026, 6, 400, 400, 40, 35, 1_600, 1_400, 4, 1, 0),
    ("CGO", 2026, 6, 500, 500, 50, 45, 2_000, 1_800, 5, 1, 0),
]

# iata, year, month, hour, sched_arr, actual_arr, sched_dep,
# peak_sched_arr, peak_actual_arr, peak_sched_dep, days
AIRPORT_HOUR = [
    ("BIG", 2026, 6, 8, 1_200, 1_100, 1_250, 50, 38, 52, 30),
    ("BIG", 2026, 6, 17, 1_100, 1_050, 1_150, 45, 40, 48, 30),
    ("GRW", 2026, 6, 9, 200, 195, 210, 12, 11, 13, 30),
    ("FLT", 2026, 6, 9, 300, 295, 310, 15, 14, 16, 30),
    ("TNY", 2026, 6, 10, 40, 40, 42, 3, 3, 3, 30),
    ("CGO", 2026, 6, 2, 60, 58, 62, 5, 5, 5, 30),
]

# origin, dest, year, month, flights, distance_mi
ROUTE_MONTH = [
    ("BIG", "FAR", 2026, 6, 300, 3_400),
    ("BIG", "FAR", 2026, 7, 400, 3_400),
    ("BIG", "MID", 2026, 6, 500, 1_500),
    ("BIG", "NEA", 2026, 6, 900, 400),
    ("GRW", "NEA", 2026, 6, 2_000, 350),
]

SOURCE_META = [
    ("ourairports", "https://example.test/airports", "2026-01-01", "6 test airports"),
    ("faa_enplanements", "https://example.test/enplanements", "2026-01-01", "CY2025"),
    ("faa_cargo", "https://example.test/cargo", "2026-01-01", "CY2025"),
    ("bts_ontime", "https://example.test/ontime", "2026-01-01", "2 months"),
]


def build(path: Path) -> Path:
    """Write the fixture database and return its path."""
    con = sqlite3.connect(path)
    con.executescript(_schema())
    con.executemany("INSERT INTO airport VALUES (?,?,?,?,?,?,?,?,?,?,?)", AIRPORTS)
    con.executemany("INSERT INTO enplanement VALUES (?,?,?,?,?,?,?)", ENPLANEMENTS)
    con.executemany("INSERT INTO cargo VALUES (?,?,?,?,?,?)", CARGO)
    con.executemany(
        "INSERT INTO airport_month VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", AIRPORT_MONTH
    )
    con.executemany(
        "INSERT INTO airport_hour VALUES (?,?,?,?,?,?,?,?,?,?,?)", AIRPORT_HOUR
    )
    con.executemany("INSERT INTO route_month VALUES (?,?,?,?,?,?)", ROUTE_MONTH)
    con.executemany("INSERT INTO source_meta VALUES (?,?,?,?)", SOURCE_META)
    con.commit()
    con.close()
    return path
