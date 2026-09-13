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
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_DIR", ROOT / "data")) / "airports.db"
CACHE = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "airports_etl"

OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/{name}.csv"
FAA_PAGE = "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger"
BTS_ONTIME = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
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
    longest_ft    INTEGER
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

CREATE TABLE source_meta (
    source        TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    fetched       TEXT NOT NULL,
    coverage      TEXT
);

CREATE INDEX idx_month_iata ON airport_month(iata);
CREATE INDEX idx_hour_iata ON airport_hour(iata);
CREATE INDEX idx_route_origin ON route_month(origin);
CREATE INDEX idx_enpl_year ON enplanement(year);
CREATE INDEX idx_airport_state ON airport(state);
"""

LONGHAUL_MI = 3000


def log(msg: str) -> None:
    print(msg, flush=True)


def download(url: str, name: str) -> Path:
    """Fetch a URL into the cache directory, reusing an existing copy."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        log(f"  cached  {name}")
        return path
    log(f"  fetching {name}")
    req = urllib.request.Request(url, headers={"User-Agent": "airports-agent/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(path, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    return path


def load_airports(con: sqlite3.Connection) -> set[str]:
    """Airport reference and runway geometry from OurAirports."""
    log("airports (OurAirports)")
    ap_path = download(OURAIRPORTS.format(name="airports"), "airports.csv")
    rw_path = download(OURAIRPORTS.format(name="runways"), "runways.csv")

    runways: dict[str, list[int]] = defaultdict(list)
    with open(rw_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ident = row["airport_ident"]
            try:
                runways[ident].append(int(float(row["length_ft"] or 0)))
            except ValueError:
                continue

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
            ))

    con.executemany(
        "INSERT OR REPLACE INTO airport VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )
    con.execute(
        "INSERT OR REPLACE INTO source_meta VALUES (?,?,?,?)",
        ("ourairports", OURAIRPORTS.format(name="airports"),
         date.today().isoformat(), f"{len(rows)} US airports"),
    )
    log(f"  {len(rows):,} US airports")
    return {r[0] for r in rows}


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
    try:
        path = download(url, name)
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
    args = parser.parse_args()

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
