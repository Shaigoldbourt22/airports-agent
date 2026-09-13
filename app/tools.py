"""Deterministic tools the model may call.

Every number an answer contains must come from one of these functions. They run
plain SQL against the database built by etl/build_db.py, and the ranking is a
fixed formula with published weights, so the same question always produces the
same score. The model chooses which tool to call and writes the prose; it never
computes.
"""

from app import db

LONGHAUL_MI = 3000

# Terminal-expansion score. Weights are fixed and sum to 1.
#   growth          rising demand is the reason to build
#   enpl_per_runway passengers carried per physical movement slot
#   peak_per_runway how crowded the single busiest hour already is
# Gate counts would be the ideal denominator, but no federal dataset publishes
# them, so runways stand in as the capacity measure.
WEIGHTS = {"growth": 0.40, "enpl_per_runway": 0.35, "peak_per_runway": 0.25}


def _normalise(values: list[float]) -> list[float]:
    """Min-max to 0-100 within the candidate set. Ties map to 50."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [50.0 for _ in values]
    return [100 * (v - lo) / (hi - lo) for v in values]


def data_coverage() -> dict:
    """What the database holds right now: sources, fetch dates, month range."""
    return db.coverage()


def airport_profile(iata: str) -> dict:
    """Location, runways, latest enplanements and cargo for one airport."""
    iata = iata.upper()
    rows = db.query(
        """
        SELECT a.iata, a.name, a.city, a.state, a.runway_count, a.longest_ft,
               e.year, e.enplanements, e.pct_change, e.hub, e.rank,
               c.landed_lbs, c.rank AS cargo_rank
        FROM airport a
        LEFT JOIN enplanement e ON e.iata = a.iata
        LEFT JOIN cargo c ON c.iata = a.iata AND c.year = e.year
        WHERE a.iata = ?
        ORDER BY e.year DESC LIMIT 1
        """,
        (iata,),
    )
    if not rows:
        return {"error": f"No airport {iata} in the database"}
    return rows[0]


def traffic_and_delays(iata: str, year: int | None = None, month: int | None = None) -> dict:
    """Monthly flight counts, delay rates and cancellations for one airport.

    Omit year and month to get every month held, so seasonality is visible.
    """
    sql = """
        SELECT year, month, departures, arrivals, cancelled, diverted,
               ROUND(100.0 * dep_del15 / NULLIF(departures, 0), 1) AS dep_delay_pct,
               ROUND(100.0 * arr_del15 / NULLIF(arrivals, 0), 1) AS arr_delay_pct,
               ROUND(1.0 * dep_delay_min / NULLIF(dep_del15, 0), 1) AS avg_dep_delay_min
        FROM airport_month WHERE iata = ?
    """
    params: list = [iata.upper()]
    if year:
        sql += " AND year = ?"
        params.append(year)
    if month:
        sql += " AND month = ?"
        params.append(month)
    rows = db.query(sql + " ORDER BY year, month", tuple(params))
    return {"iata": iata.upper(), "months": rows}


def peak_hour_demand(iata: str, year: int | None = None, month: int | None = None) -> dict:
    """The busiest scheduled hour versus what the airport actually delivered.

    The gap between peak scheduled arrivals and peak actual arrivals is unmet
    demand: flights the schedule asked for that the runways could not absorb.
    """
    sql = """
        SELECT year, month, hour, peak_sched_arr, peak_actual_arr, peak_sched_dep,
               peak_sched_arr - peak_actual_arr AS shortfall
        FROM airport_hour WHERE iata = ?
    """
    params: list = [iata.upper()]
    if year:
        sql += " AND year = ?"
        params.append(year)
    if month:
        sql += " AND month = ?"
        params.append(month)
    rows = db.query(sql + " ORDER BY peak_sched_arr DESC LIMIT 5", tuple(params))
    return {"iata": iata.upper(), "busiest_hours": rows}


def route_distance_mix(iata: str, threshold_mi: int = LONGHAUL_MI) -> dict:
    """Share of departures above a distance threshold, by month, plus the routes.

    No aviation body defines "long haul", so the threshold is a parameter and
    defaults to 3,000 miles.
    """
    iata = iata.upper()
    months = db.query(
        """
        SELECT year, month, SUM(flights) AS flights,
               SUM(CASE WHEN distance_mi >= ? THEN flights ELSE 0 END) AS over_threshold,
               ROUND(100.0 * SUM(CASE WHEN distance_mi >= ? THEN flights ELSE 0 END)
                     / NULLIF(SUM(flights), 0), 1) AS pct
        FROM route_month WHERE origin = ?
        GROUP BY year, month ORDER BY year, month
        """,
        (threshold_mi, threshold_mi, iata),
    )
    routes = db.query(
        """
        SELECT dest, distance_mi, SUM(flights) AS flights
        FROM route_month WHERE origin = ? AND distance_mi >= ?
        GROUP BY dest, distance_mi ORDER BY flights DESC
        """,
        (iata, threshold_mi),
    )
    return {"iata": iata, "threshold_mi": threshold_mi, "by_month": months,
            "routes_over_threshold": routes}


def compare_airports(iatas: list[str]) -> dict:
    """Side-by-side KPIs for two or more airports, for congestion comparisons.

    Delay rates are averaged across every month held, and also shown per runway,
    because a small airport on one runway can be as pressed as a large one.
    """
    codes = [c.upper() for c in iatas]
    placeholders = ",".join("?" * len(codes))
    rows = db.query(
        f"""
        SELECT a.iata, a.name, a.state, a.runway_count, a.longest_ft,
               e.enplanements, e.pct_change, e.hub,
               SUM(m.departures) AS departures,
               ROUND(100.0 * SUM(m.dep_del15) / NULLIF(SUM(m.departures), 0), 1) AS dep_delay_pct,
               ROUND(100.0 * SUM(m.arr_del15) / NULLIF(SUM(m.arrivals), 0), 1) AS arr_delay_pct,
               ROUND(100.0 * SUM(m.cancelled) / NULLIF(SUM(m.departures), 0), 1) AS cancel_pct,
               ROUND(1.0 * SUM(m.departures) / NULLIF(a.runway_count, 0)) AS dep_per_runway
        FROM airport a
        LEFT JOIN enplanement e ON e.iata = a.iata
        LEFT JOIN airport_month m ON m.iata = a.iata
        WHERE a.iata IN ({placeholders})
        GROUP BY a.iata
        """,
        tuple(codes),
    )
    missing = sorted(set(codes) - {r["iata"] for r in rows})
    return {"airports": rows, "not_in_database": missing or None}


def rank_expansion_candidates(
    states: list[str] | None = None,
    iatas: list[str] | None = None,
    min_enplanements: int = 250_000,
    limit: int = 10,
) -> dict:
    """Rank airports as terminal-expansion candidates using the fixed formula.

    Pass states (two-letter codes, e.g. the six New England states) or an
    explicit list of airports. Scores are min-max normalised inside the returned
    set, so they are relative to that peer group, not national.
    """
    where = ["e.enplanements >= ?"]
    params: list = [min_enplanements]
    if states:
        where.append(f"a.state IN ({','.join('?' * len(states))})")
        params += [s.upper() for s in states]
    if iatas:
        where.append(f"a.iata IN ({','.join('?' * len(iatas))})")
        params += [c.upper() for c in iatas]

    rows = db.query(
        f"""
        SELECT a.iata, a.name, a.state, a.runway_count,
               e.enplanements, e.pct_change,
               (SELECT MAX(peak_sched_dep) FROM airport_hour h WHERE h.iata = a.iata)
                   AS peak_sched_dep
        FROM airport a JOIN enplanement e ON e.iata = a.iata
        WHERE {' AND '.join(where)}
        """,
        tuple(params),
    )
    scored = [r for r in rows if r["runway_count"] and r["peak_sched_dep"]
              and r["pct_change"] is not None]
    if not scored:
        return {"ranked": [], "excluded": rows,
                "note": "No airport in this set has the growth, runway and "
                        "peak-hour data the score requires."}

    metrics = {
        "growth": [r["pct_change"] for r in scored],
        "enpl_per_runway": [r["enplanements"] / r["runway_count"] for r in scored],
        "peak_per_runway": [r["peak_sched_dep"] / r["runway_count"] for r in scored],
    }
    normalised = {k: _normalise(v) for k, v in metrics.items()}

    for i, row in enumerate(scored):
        row["components"] = {k: round(normalised[k][i], 1) for k in WEIGHTS}
        row["score"] = round(sum(WEIGHTS[k] * normalised[k][i] for k in WEIGHTS), 1)

    scored.sort(key=lambda r: r["score"], reverse=True)
    dropped = [{"iata": r["iata"], "name": r["name"]} for r in rows if r not in scored]
    return {
        "ranked": scored[:limit],
        "weights": WEIGHTS,
        "unscored_missing_data": dropped or None,
        "note": "Scores are relative to the airports in this list only.",
    }


REGISTRY = {
    f.__name__: f
    for f in (
        data_coverage,
        airport_profile,
        traffic_and_delays,
        peak_hour_demand,
        route_distance_mix,
        compare_airports,
        rank_expansion_candidates,
    )
}
