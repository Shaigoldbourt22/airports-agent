"""Build the local SQLite database from public aviation sources.

Sources:
  OurAirports        airport reference: name, city, state, region, coordinates
  OurAirports        runways: count and longest runway per airport
  FAA enplanements   annual passengers, year-over-year change, hub class
  FAA all-cargo      annual landed weight
  BTS On-Time        per-flight records, aggregated before storage

Per-flight rows are never stored. They are collapsed into three aggregates
that every KPI is computed from, which keeps the database under ~25 MB.

Usage:
    python etl/build_db.py               # 12 months of BTS
    python etl/build_db.py --months 3    # faster, loses seasonality
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import openpyxl

# Runs as a script inside the ETL container, so the sibling module is imported
# by path rather than as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import census  # noqa: E402
import cats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_DIR", ROOT / "data")) / "airports.db"
CACHE = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "airports_etl"

OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/{name}.csv"
FAA_PAGE = "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger"
BTS_ONTIME = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)
NPIAS = (
    "https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/npias/"
    "current/ARP-NPIAS-2025-2029-AppendixA.xlsx"
)

# No public dataset publishes gate counts or terminal floor area. Terminal
# pressure is measured instead from peak concurrent aircraft, which is what a
# terminal must physically accommodate, and which every airport reports weekly.

SCHEMA = """
CREATE TABLE airport (
    iata          TEXT PRIMARY KEY,
    icao          TEXT,
    name          TEXT NOT NULL,
    city          TEXT,
    state         TEXT,
    region        TEXT,
    latitude      REAL,
    longitude     REAL,
    runway_count  INTEGER,
    longest_ft    INTEGER,
    -- Distance between the closest pair of parallel runways. Under FAA rules
    -- parallels closer than 2,500 ft cannot take independent approaches in
    -- poor visibility, and below 1,200 ft they work as a single runway. This
    -- is why some airports lose arrival capacity the moment the weather turns.
    parallel_ft   INTEGER
);

CREATE TABLE enplanement (
    iata          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    enplanements  INTEGER NOT NULL,
    prev_year     INTEGER,
    pct_change    REAL,
    hub           TEXT,
    rank          INTEGER,
    PRIMARY KEY (iata, year)
);

CREATE TABLE cargo (
    iata          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    landed_lbs    INTEGER NOT NULL,
    prev_lbs      INTEGER,
    pct_change    REAL,
    rank          INTEGER,
    PRIMARY KEY (iata, year)
);

-- One row per airport per month. Drives congestion and reliability KPIs.
CREATE TABLE airport_month (
    iata          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    departures    INTEGER NOT NULL DEFAULT 0,
    arrivals      INTEGER NOT NULL DEFAULT 0,
    dep_del15     INTEGER NOT NULL DEFAULT 0,
    arr_del15     INTEGER NOT NULL DEFAULT 0,
    dep_delay_min INTEGER NOT NULL DEFAULT 0,
    arr_delay_min INTEGER NOT NULL DEFAULT 0,
    cancelled     INTEGER NOT NULL DEFAULT 0,
    diverted      INTEGER NOT NULL DEFAULT 0,
    longhaul_dep  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (iata, year, month)
);

-- Peak-hour capacity analysis: what the schedule asks for versus what was flown.
-- peak_sched_dep is the terminal-pressure input: aircraft needing a stand at once.
CREATE TABLE airport_hour (
    iata          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    hour          INTEGER NOT NULL,
    sched_arr     INTEGER NOT NULL DEFAULT 0,
    actual_arr    INTEGER NOT NULL DEFAULT 0,
    sched_dep     INTEGER NOT NULL DEFAULT 0,
    peak_sched_arr INTEGER NOT NULL DEFAULT 0,
    peak_actual_arr INTEGER NOT NULL DEFAULT 0,
    peak_sched_dep INTEGER NOT NULL DEFAULT 0,
    days          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (iata, year, month, hour)
);

-- One row per directed route per month. Drives distance-based questions.
CREATE TABLE route_month (
    origin        TEXT NOT NULL,
    dest          TEXT NOT NULL,
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    flights       INTEGER NOT NULL,
    distance_mi   INTEGER NOT NULL,
    PRIMARY KEY (origin, dest, year, month)
);

-- The metro area an airport draws on, and how fast it is growing. Runway
-- counts describe capacity today; this describes the demand a terminal built
-- now would serve. Population level is deliberately absent: it tracks
-- enplanements per runway almost exactly, so it would add weight to the score
-- without adding information.
CREATE TABLE catchment (
    iata          TEXT PRIMARY KEY,
    cbsa          TEXT NOT NULL,
    metro         TEXT NOT NULL,
    population    INTEGER NOT NULL,
    prev_pop      INTEGER NOT NULL,
    pop_growth    REAL NOT NULL,   -- percent over `years`, as pct_change is
    years         TEXT NOT NULL
);

CREATE TABLE source_meta (
    source        TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    fetched       TEXT NOT NULL,
    coverage      TEXT
);

-- The FAA's own estimate of eligible development cost over five years, one row
-- per airport in the national plan. This is the only cost figure in the
-- database: everything else measures demand or constraint, none of it says
-- what building anything would take. Divided by annual enplanements it gives
-- capital needed per passenger served, which does not move with traffic.
--
-- It is *needed* development, not committed or funded spend, and it covers
-- airside work as well as terminal work, so it cannot be read as a terminal
-- price. It is published every two years, so it is coarser in time than the
-- monthly flight data.
CREATE TABLE development_need (
    iata          TEXT PRIMARY KEY,
    period        TEXT NOT NULL,
    estimate_usd  INTEGER NOT NULL,
    role          TEXT,
    service_level TEXT
);

-- What an airport earns and spends, from its own FAA Form 127 filing. The
-- rest of the database measures demand and physical constraint; this is the
-- only place that says whether a site makes money from the passengers it
-- already has.
--
-- non_aeronautical_revenue is the terminal's own commercial take: food,
-- retail, parking, rental cars. Divided by enplanements it shows spend per
-- passenger, and a busy airport with a low figure is under-monetising traffic
-- it already holds, which is what a terminal renovation is meant to fix.
-- Aeronautical revenue cannot show that, because landing fees track aircraft
-- weight rather than the quality of the terminal.
CREATE TABLE financials (
    iata                     TEXT NOT NULL,
    year                     INTEGER NOT NULL,
    aeronautical_revenue     INTEGER,
    terminal_food_beverage   INTEGER,
    terminal_retail          INTEGER,
    parking_ground_transport INTEGER,
    non_aeronautical_revenue INTEGER,
    operating_revenue        INTEGER,
    operating_expenses       INTEGER,
    operating_income         INTEGER,
    capex_terminal           INTEGER,
    capex_total              INTEGER,
    total_debt               INTEGER,
    PRIMARY KEY (iata, year)
);

CREATE INDEX idx_month_iata ON airport_month(iata);
CREATE INDEX idx_hour_iata ON airport_hour(iata);
CREATE INDEX idx_route_origin ON route_month(origin);
CREATE INDEX idx_enpl_year ON enplanement(year);
CREATE INDEX idx_airport_state ON airport(state);
"""

LONGHAUL_MI = 3000

# How long BTS keeps revising a month after publishing it. Beyond this the
# figures stop moving, so a cached archive of that month stays valid.
BTS_SETTLES_AFTER_MONTHS = 6

# Set by --refresh to force every source to be fetched again.
CACHE_MAX_AGE_OVERRIDE: int | None = None

# Geocoding costs one request per airport, so only airports large enough to
# appear in a ranking are looked up.
CATCHMENT_MIN_ENPLANEMENTS = 250_000

# Form 127 costs one request per airport too, and filings run a year or two
# behind, so recent years are tried in turn until one has data.
FINANCIALS_MIN_ENPLANEMENTS = 250_000
CATS_YEARS = (2024, 2023, 2022)


def log(msg: str) -> None:
    print(msg, flush=True)


def download(url: str, name: str, max_age_days: int = 30) -> Path:
    """Fetch a URL into the cache directory, reusing a copy that is still fresh.

    Caching matters: a full run pulls twelve BTS monthly archives of roughly
    250 MB each, so reusing them turns a half-hour rebuild into a minute. But a
    cache with no expiry is worse than none, because the run stops reflecting
    the sources and nothing says so. Anything older than max_age_days is
    fetched again.

    Pass max_age_days=0 to force a refetch.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if CACHE_MAX_AGE_OVERRIDE is not None:
        max_age_days = CACHE_MAX_AGE_OVERRIDE
    if path.exists() and path.stat().st_size > 0:
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days <= max_age_days:
            log(f"  cached  {name} ({age_days:.0f}d old)")
            return path
        log(f"  stale   {name} ({age_days:.0f}d old), refetching")
    log(f"  fetching {name}")
    tmp = path.with_suffix(path.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "airports-agent/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    # Rename only once the body is complete, so an interrupted download cannot
    # leave a truncated file that later runs treat as a valid cache hit.
    tmp.replace(path)
    return path


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    radius = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(a))


def _parallel_spacing_ft(ends: list[tuple[str, float, float]]) -> int | None:
    """Closest distance between two parallel runways, in feet.

    Runways are parallel when their numbers match, so 28L and 28R are a pair.
    Distance is measured between the two approach thresholds, which is the
    centreline separation for parallels.
    """
    by_heading: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for ident, lat, lon in ends:
        number = "".join(ch for ch in ident if ch.isdigit())
        if number:
            by_heading[number.zfill(2)].append((lat, lon))

    best = None
    for points in by_heading.values():
        for i, first in enumerate(points):
            for second in points[i + 1:]:
                feet = _haversine_mi(*first, *second) * 5280
                if feet > 50 and (best is None or feet < best):
                    best = feet
    return int(best) if best else None


def load_airports(con: sqlite3.Connection) -> set[str]:
    """Airport reference and runway geometry from OurAirports."""
    log("airports (OurAirports)")
    ap_path = download(OURAIRPORTS.format(name="airports"), "airports.csv")
    rw_path = download(OURAIRPORTS.format(name="runways"), "runways.csv")

    runways: dict[str, list[int]] = defaultdict(list)
    ends: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    with open(rw_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ident = row["airport_ident"]
            try:
                runways[ident].append(int(float(row["length_ft"] or 0)))
            except ValueError:
                continue
            if row["closed"] == "1":
                continue
            for side in ("le", "he"):
                lat, lon = row[f"{side}_latitude_deg"], row[f"{side}_longitude_deg"]
                if lat and lon:
                    ends[ident].append(
                        (row[f"{side}_ident"] or "", float(lat), float(lon))
                    )

    rows = []
    with open(ap_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            iata = (row["iata_code"] or "").strip()
            if not iata or row["iso_country"] != "US":
                continue
            if row["type"] not in ("large_airport", "medium_airport", "small_airport"):
                continue
            lengths = [x for x in runways.get(row["ident"], []) if x > 0]
            rows.append((
                iata,
                row["gps_code"] or None,
                row["name"],
                row["municipality"] or None,
                (row["iso_region"] or "").replace("US-", "") or None,
                row["iso_region"] or None,
                float(row["latitude_deg"]) if row["latitude_deg"] else None,
                float(row["longitude_deg"]) if row["longitude_deg"] else None,
                len(lengths),
                max(lengths) if lengths else None,
                _parallel_spacing_ft(ends.get(row["ident"], [])),
            ))

    con.executemany(
        "INSERT OR REPLACE INTO airport VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("ourairports", OURAIRPORTS.format(name="airports"),
         date.today().isoformat(), f"{len(rows)} US airports"),
    )
    log(f"  {len(rows):,} US airports")
    return {r[0] for r in rows}


def load_catchment(con: sqlite3.Connection) -> None:
    """Metro population growth for airports that carry meaningful traffic.

    Only airports above the enplanement floor are geocoded: the geocoder is one
    request per airport, and an airport too small to rank is not worth the call.
    A missing key or an unreachable API leaves the table empty rather than
    failing the build, because every other answer still works without it.
    """
    log("catchment (Census ACS)")
    try:
        current = census.metro_population(census.CURRENT_YEAR)
        baseline = census.metro_population(census.BASELINE_YEAR)
    except census.CensusUnavailable as exc:
        log(f"  skipped: {exc}")
        return
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log(f"  skipped, Census unreachable: {type(exc).__name__}: {exc}")
        return

    airports = con.execute(
        "SELECT a.iata, a.latitude, a.longitude FROM airport a "
        "JOIN enplanement e ON e.iata = a.iata "
        "WHERE e.enplanements >= ? AND a.latitude IS NOT NULL",
        (CATCHMENT_MIN_ENPLANEMENTS,),
    ).fetchall()

    years = f"{census.BASELINE_YEAR}-{census.CURRENT_YEAR}"
    rows, redefined = [], 0
    for iata, latitude, longitude in airports:
        cbsa, metro = census.locate(latitude, longitude)
        if not cbsa:
            continue
        change = census.growth(current, baseline, cbsa)
        if change is None:
            redefined += 1
            continue
        name, population = current[cbsa]
        _, previous = baseline[cbsa]
        rows.append((iata, cbsa, metro or name, population, previous, change, years))

    con.executemany("INSERT OR REPLACE INTO catchment VALUES (?,?,?,?,?,?,?)", rows)
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("census_acs", census.ACS.format(year=census.CURRENT_YEAR),
         date.today().isoformat(),
         f"{len(rows)} airports, ACS {years}"),
    )
    log(f"  {len(rows):,} airports matched to metro areas")
    if redefined:
        log(f"  {redefined} skipped: metro boundary changed since {census.BASELINE_YEAR}")


def faa_links() -> dict[str, str]:
    """Scrape the FAA statistics page for current spreadsheet URLs."""
    req = urllib.request.Request(FAA_PAGE, headers={"User-Agent": "airports-agent/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        html = resp.read().decode("utf-8", "replace")
    import re

    out = {}
    for href in re.findall(r'href="([^"]+\.xlsx)"', html):
        url = href if href.startswith("http") else "https://www.faa.gov" + href
        out[href.rsplit("/", 1)[-1].lower()] = url
    return out


def load_enplanements(con: sqlite3.Connection, links: dict[str, str]) -> None:
    log("enplanements (FAA)")
    matches = sorted(
        (n for n in links if "commercial-service-enplanements" in n), reverse=True
    )
    if not matches:
        log("  no enplanement file found on FAA page")
        return
    name = matches[0]
    path = download(links[name], name)
    year = int("".join(c for c in name if c.isdigit())[:4])

    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        rank, _ro, _st, iata, _city, _apname, _sl, hub, cur, prev, pct = r[:11]
        if not iata or not isinstance(cur, int):
            continue
        rows.append((iata, year, cur, prev if isinstance(prev, int) else None,
                     float(pct) if isinstance(pct, (int, float)) else None,
                     hub, rank if isinstance(rank, int) else None))

    con.executemany("INSERT OR REPLACE INTO enplanement VALUES (?,?,?,?,?,?,?)", rows)
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("faa_enplanements", links[name], date.today().isoformat(), f"CY{year}"),
    )
    log(f"  {len(rows):,} airports, CY{year}")


def load_cargo(con: sqlite3.Connection, links: dict[str, str]) -> None:
    log("cargo (FAA)")
    matches = sorted((n for n in links if "all-cargo-airports" in n), reverse=True)
    if not matches:
        log("  no cargo file found on FAA page")
        return
    name = matches[0]
    path = download(links[name], name)
    year = int("".join(c for c in name if c.isdigit())[:4])

    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        rank, _ro, _ado, _st, iata, _apname, _city, _sl, _hub, cur, prev, pct = r[:12]
        if not iata or not isinstance(cur, int):
            continue
        rows.append((iata, year, cur, prev if isinstance(prev, int) else None,
                     float(pct) if isinstance(pct, (int, float)) else None,
                     rank if isinstance(rank, int) else None))

    con.executemany("INSERT OR REPLACE INTO cargo VALUES (?,?,?,?,?,?)", rows)
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("faa_cargo", links[name], date.today().isoformat(), f"CY{year}"),
    )
    log(f"  {len(rows):,} airports, CY{year}")


def load_development_need(con: sqlite3.Connection) -> None:
    """FAA NPIAS Appendix A: five-year eligible development cost per airport.

    Column positions differ from the enplanement workbooks, and the FAA has
    moved them between editions, so the header row is located and read by name
    rather than by index.
    """
    log("development need (FAA NPIAS)")
    try:
        path = download(NPIAS, "npias-appendix-a.xlsx")
    except Exception as exc:  # noqa: BLE001 - one optional source, not the run
        log(f"  skipped: {type(exc).__name__}: {exc}")
        return

    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows_iter = ws.iter_rows(values_only=True)
    header = None
    for row in rows_iter:
        cells = [str(c).strip() if c is not None else "" for c in row]
        if sum(1 for c in cells if c) >= 4:
            header = cells
            break
    if not header:
        log("  no header row found")
        return

    def column(*needles: str) -> int | None:
        for i, name in enumerate(header):
            lowered = name.lower()
            if all(n in lowered for n in needles):
                return i
        return None

    i_code = column("locid") or column("loc", "id")
    i_cost = column("development")
    if i_code is None or i_cost is None:
        log(f"  unexpected columns: {[c for c in header if c]}")
        return
    i_role, i_svc = column("role"), column("svc")
    # The header cell wraps across lines in the workbook, so the period is
    # pulled out of it rather than used as written.
    label = " ".join(header[i_cost].split())
    period = label.replace("Development Estimate", "").strip() or "2025-2029"

    rows = []
    for row in rows_iter:
        code = row[i_code]
        cost = row[i_cost]
        if not code or not isinstance(cost, (int, float)):
            continue
        rows.append((
            str(code).strip().upper(), period, int(cost),
            row[i_role] if i_role is not None else None,
            row[i_svc] if i_svc is not None else None,
        ))

    con.executemany("INSERT OR REPLACE INTO development_need VALUES (?,?,?,?,?)", rows)
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("faa_npias", NPIAS, date.today().isoformat(), f"NPIAS {period}"),
    )
    log(f"  {len(rows):,} airports, {period}")


def load_financials(con: sqlite3.Connection) -> None:
    """FAA Form 127 filings, for airports big enough to appear in a ranking.

    One HTTP request per airport, so this is limited the same way catchment is.
    Filings run a couple of years behind, so recent years are tried in turn
    until one returns data.
    """
    log("financials (FAA CATS Form 127)")
    wanted = {row[0] for row in con.execute(
        "SELECT iata FROM enplanement WHERE enplanements >= ?",
        (FINANCIALS_MIN_ENPLANEMENTS,),
    )}
    for year in CATS_YEARS:
        rows = cats.fetch_all(year, wanted=wanted, log=log)
        if rows:
            break
    else:
        log("  no filings found")
        return

    con.executemany(
        f"INSERT OR REPLACE INTO financials VALUES ({','.join('?' * (2 + len(cats.FIELDS)))})",
        [(r["iata"], r["year"], *(r[f] for f in cats.FIELDS)) for r in rows],
    )
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("faa_cats", cats.BASE, date.today().isoformat(),
         f"{len(rows)} airports, FY{year}"),
    )
    log(f"  {len(rows)} airports, FY{year}")


def _hour(hhmm: str) -> int | None:
    if not hhmm or not hhmm.strip():
        return None
    try:
        return int(float(hhmm)) // 100 % 24
    except ValueError:
        return None


def load_bts_month(con: sqlite3.Connection, year: int, month: int) -> bool:
    """Aggregate one month of BTS On-Time data into the monthly/hourly tables."""
    url = BTS_ONTIME.format(year=year, month=month)
    name = f"ontime_{year}_{month:02d}.zip"
    # One archive per calendar month, around 250 MB each, so how long a copy is
    # kept is decided by the month it covers rather than by when it was
    # downloaded. BTS revises a month for a while after first publishing it and
    # then leaves it alone, so recent months are refetched and settled ones are
    # not, however long they have sat in the cache.
    today = date.today()
    months_old = (today.year - year) * 12 + today.month - month
    max_age = 7 if months_old <= BTS_SETTLES_AFTER_MONTHS else 3650
    try:
        path = download(url, name, max_age_days=max_age)
    except Exception as exc:  # noqa: BLE001 - source availability varies
        log(f"  {year}-{month:02d} unavailable: {exc}")
        return False

    month_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hour_stats: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    day_hour_sched: dict[tuple[str, int, str], int] = defaultdict(int)
    day_hour_act: dict[tuple[str, int, str], int] = defaultdict(int)
    day_hour_dep: dict[tuple[str, int, str], int] = defaultdict(int)
    routes: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])

    with zipfile.ZipFile(path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as fh:
            for row in csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1")):
                o, d = row["Origin"], row["Dest"]
                cancelled = row["Cancelled"] == "1.00"
                diverted = row["Diverted"] == "1.00"
                try:
                    dist = int(float(row["Distance"] or 0))
                except ValueError:
                    dist = 0

                mo, md = month_stats[o], month_stats[d]
                mo["departures"] += 1
                md["arrivals"] += 1
                if cancelled:
                    mo["cancelled"] += 1
                    md["cancelled"] += 1
                if diverted:
                    mo["diverted"] += 1
                    md["diverted"] += 1
                if dist >= LONGHAUL_MI:
                    mo["longhaul_dep"] += 1
                if row["DepDel15"] == "1.00":
                    mo["dep_del15"] += 1
                if row["ArrDel15"] == "1.00":
                    md["arr_del15"] += 1
                for key, field, tgt in (("DepDelay", "dep_delay_min", mo),
                                        ("ArrDelay", "arr_delay_min", md)):
                    try:
                        v = float(row[key] or 0)
                        if v > 0:
                            tgt[field] += int(v)
                    except ValueError:
                        pass

                if not cancelled:
                    day = row["FlightDate"]
                    sh, ah = _hour(row["CRSArrTime"]), _hour(row["ArrTime"])
                    dh = _hour(row["CRSDepTime"])
                    if sh is not None:
                        hour_stats[(d, sh)]["sched_arr"] += 1
                        day_hour_sched[(d, sh, day)] += 1
                    if ah is not None:
                        hour_stats[(d, ah)]["actual_arr"] += 1
                        day_hour_act[(d, ah, day)] += 1
                    if dh is not None:
                        hour_stats[(o, dh)]["sched_dep"] += 1
                        day_hour_dep[(o, dh, day)] += 1
                    r = routes[(o, d)]
                    r[0] += 1
                    r[1] = dist

    peak_sched: dict[tuple[str, int], int] = defaultdict(int)
    peak_act: dict[tuple[str, int], int] = defaultdict(int)
    peak_dep: dict[tuple[str, int], int] = defaultdict(int)
    days_seen: dict[tuple[str, int], set[str]] = defaultdict(set)
    for (ap, hr, day), n in day_hour_sched.items():
        peak_sched[(ap, hr)] = max(peak_sched[(ap, hr)], n)
        days_seen[(ap, hr)].add(day)
    for (ap, hr, day), n in day_hour_act.items():
        peak_act[(ap, hr)] = max(peak_act[(ap, hr)], n)
    for (ap, hr, day), n in day_hour_dep.items():
        peak_dep[(ap, hr)] = max(peak_dep[(ap, hr)], n)
        days_seen[(ap, hr)].add(day)

    con.executemany(
        "INSERT OR REPLACE INTO airport_month VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(ap, year, month, s["departures"], s["arrivals"], s["dep_del15"],
          s["arr_del15"], s["dep_delay_min"], s["arr_delay_min"],
          s["cancelled"], s["diverted"], s["longhaul_dep"])
         for ap, s in month_stats.items()],
    )
    con.executemany(
        "INSERT OR REPLACE INTO airport_hour VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(ap, year, month, hr, s["sched_arr"], s["actual_arr"], s["sched_dep"],
          peak_sched[(ap, hr)], peak_act[(ap, hr)], peak_dep[(ap, hr)],
          len(days_seen[(ap, hr)]))
         for (ap, hr), s in hour_stats.items()],
    )
    con.executemany(
        "INSERT OR REPLACE INTO route_month VALUES (?,?,?,?,?,?)",
        [(o, d, year, month, n, dist) for (o, d), (n, dist) in routes.items()],
    )
    con.commit()
    log(f"  {year}-{month:02d}: {len(month_stats):,} airports, {len(routes):,} routes")
    return True


def latest_bts_months(count: int) -> list[tuple[int, int]]:
    """BTS publishes roughly 10 weeks in arrears, so start three months back."""
    today = date.today()
    y, m = today.year, today.month
    for _ in range(3):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    out = []
    for _ in range(count):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=12,
                        help="how many months of BTS On-Time data to load")
    parser.add_argument("--refresh", action="store_true",
                        help="ignore cached downloads and fetch every source again")
    args = parser.parse_args()

    if args.refresh:
        global CACHE_MAX_AGE_OVERRIDE
        CACHE_MAX_AGE_OVERRIDE = 0

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # SQLite cannot run over SMB: Azure Files does not support the byte-range
    # locks it needs. Build on local container disk, then copy the finished
    # file to the share. The copy is atomic enough for a single reader.
    work = Path(tempfile.gettempdir()) / "airports.building"
    if work.exists():
        work.unlink()

    con = sqlite3.connect(work)
    con.executescript(SCHEMA)

    load_airports(con)
    links = faa_links()
    load_enplanements(con, links)
    load_cargo(con, links)
    load_development_need(con)
    load_financials(con)
    load_catchment(con)
    con.commit()

    log(f"BTS On-Time ({args.months} months)")
    loaded = 0
    for y, m in latest_bts_months(args.months):
        if load_bts_month(con, y, m):
            loaded += 1
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("bts_ontime", BTS_ONTIME, date.today().isoformat(), f"{loaded} months"),
    )

    con.commit()
    con.execute("VACUUM")
    con.close()

    if loaded == 0:
        log("no BTS months loaded, keeping the existing database")
        work.unlink()
        return 1

    shutil.copy2(work, DB_PATH)
    work.unlink()
    size_mb = DB_PATH.stat().st_size / (1 << 20)
    log(f"\n{DB_PATH} built, {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
