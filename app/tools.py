"""Deterministic tools the model may call.

Every number an answer contains must come from one of these functions. They run
plain SQL against the database built by etl/build_db.py, and the ranking is a
fixed formula with published weights, so the same question always produces the
same score. The model chooses which tool to call and writes the prose; it never
computes.
"""

from app import db

LONGHAUL_MI = 3000

# FAA separation rules for parallel runways. Under 2,500 ft apart an airport
# cannot run independent approaches in poor visibility; under 1,200 ft the
# parallels are worked as a single runway. Both cost arrival capacity exactly
# when demand peaks, so spacing is a structural constraint, not a detail.
INDEPENDENT_APPROACH_FT = 2500
SINGLE_RUNWAY_FT = 1200

# Terminal-expansion score. Weights are fixed and sum to 1.
#   growth     rising airline demand is the reason to build
#   catchment  whether the metro the terminal would serve is growing
#
# The question is which airports would repay a terminal, so the score is built
# only from what a terminal can serve: passenger demand now and over the life of
# the asset. Runway pressure is reported alongside it as a constraint, not added
# into it. Scoring the two together ranked the most airfield-constrained airport
# first on a terminal question, which is the one place extra gates add no
# throughput at all.
#
# Catchment growth is the only measure here that does not move with traffic
# (r = -0.65 to +0.20 against the airfield measures). It is what separates an
# airline adding a seasonal route from a metro that will still need the terminal
# in 2050.
#
# Gate counts and terminal floor area would be the honest capacity denominator,
# but no federal dataset publishes either, so terminal need is a demand proxy.
WEIGHTS = {"growth": 0.5, "catchment": 0.5}

# Airfield pressure, scored the same way but kept out of the ranking.
#   load     how hard the existing runways are already worked
#   spacing  whether runway geometry caps arrivals in bad weather
#
# Load is one factor, not two. Enplanements per runway and peak departures per
# runway correlate at r=0.92 nationally, so scoring them separately put half the
# weight on a single underlying measurement while presenting it as two
# independent signals. They are averaged into one component instead.
AIRFIELD_WEIGHTS = {"load": 0.7, "spacing": 0.3}

# Above this, the airfield is the binding constraint and a terminal on its own
# cannot raise throughput, however strong the demand case looks.
AIRFIELD_CONSTRAINED_AT = 60.0


def _spacing_penalty(parallel_ft: int | None) -> float:
    """0-100 by how much parallel spacing limits arrivals in poor visibility.

    No parallels means spacing is not the binding constraint, so it scores 0
    rather than being treated as missing data.
    """
    if not parallel_ft:
        return 0.0
    if parallel_ft < SINGLE_RUNWAY_FT:
        return 100.0
    if parallel_ft < INDEPENDENT_APPROACH_FT:
        return 60.0
    return 0.0


def _missing_inputs(row: dict) -> list[str]:
    """Which score inputs an airport lacks, named so an answer can say so."""
    missing = []
    if not row["runway_count"]:
        missing.append("runway count")
    if not row["peak_sched_dep"]:
        missing.append("peak-hour flight data")
    if row["pct_change"] is None:
        missing.append("enplanement growth")
    if row["pop_growth"] is None:
        missing.append("metro population growth")
    return missing


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
               a.parallel_ft,
               e.year, e.enplanements, e.pct_change, e.hub, e.rank,
               c.landed_lbs, c.rank AS cargo_rank,
               d.estimate_usd AS development_need_usd, d.period AS development_period,
               f.year AS financial_year, f.operating_revenue, f.operating_expenses,
               f.operating_income, f.non_aeronautical_revenue, f.aeronautical_revenue,
               f.capex_terminal, f.total_debt
        FROM airport a
        LEFT JOIN enplanement e ON e.iata = a.iata
        LEFT JOIN cargo c ON c.iata = a.iata AND c.year = e.year
        LEFT JOIN development_need d ON d.iata = a.iata
        LEFT JOIN financials f ON f.iata = a.iata
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

    Returns the runway geometry alongside it, because that is usually the
    cause. FAA rules bar independent approaches to parallel runways spaced
    under 2,500 ft in poor visibility, and parallels under 1,200 ft apart work
    as a single runway, so arrival capacity drops sharply when cloud moves in.
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

    geometry = db.query(
        "SELECT runway_count, longest_ft, parallel_ft FROM airport WHERE iata = ?",
        (iata.upper(),),
    )
    constraint = None
    if geometry and geometry[0]["parallel_ft"]:
        spacing = geometry[0]["parallel_ft"]
        if spacing < 1200:
            constraint = (
                f"Closest parallel runways are {spacing:,} ft apart, under the "
                "1,200 ft minimum for simultaneous operations, so they are "
                "worked as one runway in poor visibility."
            )
        elif spacing < 2500:
            constraint = (
                f"Closest parallel runways are {spacing:,} ft apart, below the "
                "2,500 ft FAA minimum for independent approaches, so arrival "
                "rates fall when visibility drops."
            )
        else:
            constraint = (
                f"Closest parallel runways are {spacing:,} ft apart, enough for "
                "independent approaches in poor visibility."
            )

    return {
        "iata": iata.upper(),
        "busiest_hours": rows,
        "runways": geometry[0] if geometry else None,
        "capacity_constraint": constraint,
        "method": "Shortfall is peak scheduled arrivals minus peak actual "
                  "arrivals in the same hour. It is a proxy for unmet demand, "
                  "not a measure of it: it counts flights the schedule asked "
                  "for and the airport did not deliver, and misses demand that "
                  "was never scheduled because airlines knew slots were "
                  "unavailable. Report it as a proxy.",
        "caveat": "Parallel-spacing limits bite in low visibility, so the "
                  "shortfall concentrates in fog, low cloud and the weather "
                  "that triggers FAA ground delay programs, not in clear "
                  "conditions. The data holds no weather field, so this is "
                  "context for the reader, not something measured here.",
    }


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
    return {
        "iata": iata,
        "threshold_mi": threshold_mi,
        "by_month": months,
        "routes_over_threshold": routes,
        "total_flights": sum(m["flights"] or 0 for m in months),
        "scope": "BTS On-Time Performance covers scheduled passenger flights "
                 "on reporting US carriers only. All-cargo operations are not "
                 "counted, which matters at freight hubs such as ANC, where "
                 "most long-haul departures are cargo and sit outside these "
                 "figures. Say so when answering for such an airport, and give "
                 "the flight counts alongside the percentages so the base is "
                 "visible.",
    }


def cargo_growth(min_lbs: int = 100_000_000, limit: int = 10) -> dict:
    """Airports ranked by cargo growth, with the tiny-base noise filtered out.

    An airport handling a few tonnes can post +100% and mean nothing, so a
    minimum annual landed weight is applied. The excluded high-percentage
    airports are returned too, so the filter can be reported rather than hidden.
    """
    rows = db.query(
        """
        SELECT c.iata, a.name, a.state, c.landed_lbs, c.pct_change, c.rank
        FROM cargo c JOIN airport a ON a.iata = c.iata
        ORDER BY c.pct_change DESC
        """
    )
    big = [r for r in rows if r["landed_lbs"] >= min_lbs]
    noise = [r for r in rows if r["landed_lbs"] < min_lbs and (r["pct_change"] or 0) > 0.2]
    return {
        "ranked": big[:limit],
        "declining": sorted(big, key=lambda r: r["pct_change"] or 0)[:5],
        "excluded_small_base": noise[:5],
        "min_lbs": min_lbs,
    }


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
               a.parallel_ft,
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
    return {
        "airports": rows,
        "not_in_database": missing or None,
        "note": "longest_ft is the longest runway in feet, and caps which "
                "aircraft an airport can take regardless of how busy it is. "
                "Low traffic per runway can also be a legal limit rather than "
                "a physical one: several US airports operate under slot caps "
                "or noise curfews, which this data does not record.",
    }


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
        SELECT a.iata, a.name, a.state, a.runway_count, a.parallel_ft,
               e.enplanements, e.pct_change,
               c.metro, c.pop_growth, c.population,
               d.estimate_usd AS development_need_usd, d.period AS development_period,
               f.year AS financial_year, f.non_aeronautical_revenue,
               f.operating_revenue, f.operating_income, f.capex_terminal,
               (SELECT MAX(peak_sched_dep) FROM airport_hour h WHERE h.iata = a.iata)
                   AS peak_sched_dep
        FROM airport a JOIN enplanement e ON e.iata = a.iata
        LEFT JOIN catchment c ON c.iata = a.iata
        LEFT JOIN development_need d ON d.iata = a.iata
        LEFT JOIN financials f ON f.iata = a.iata
        WHERE {' AND '.join(where)}
        """,
        tuple(params),
    )
    scored = [r for r in rows if r["runway_count"] and r["peak_sched_dep"]
              and r["pct_change"] is not None and r["pop_growth"] is not None]
    if not scored:
        return {
            "ranked": [],
            "unscored_missing_data": [
                {"iata": r["iata"], "name": r["name"],
                 "missing": _missing_inputs(r)} for r in rows
            ],
            "note": "No airport in this set has all four inputs the score needs.",
        }

    # Both per-runway measures describe the same thing, so they are averaged
    # before normalising rather than scored as separate components.
    load = [((r["enplanements"] / r["runway_count"]) / 100_000
             + r["peak_sched_dep"] / r["runway_count"]) / 2 for r in scored]

    normalised = {
        "load": _normalise(load),
        "growth": _normalise([r["pct_change"] for r in scored]),
        "catchment": _normalise([r["pop_growth"] for r in scored]),
    }
    # Spacing is already 0-100 on a published rule, so normalising it would make
    # the worst airport in a set of mildly constrained ones look critical.
    normalised["spacing"] = [_spacing_penalty(r["parallel_ft"]) for r in scored]

    for i, row in enumerate(scored):
        # Score from the published components, not the raw ones, so an analyst
        # can reproduce the total from the figures shown.
        components = {k: round(normalised[k][i], 1)
                      for k in (*WEIGHTS, *AIRFIELD_WEIGHTS)}
        row["components"] = components
        row["score"] = round(sum(WEIGHTS[k] * components[k] for k in WEIGHTS), 1)
        row["airfield_pressure"] = round(
            sum(AIRFIELD_WEIGHTS[k] * components[k] for k in AIRFIELD_WEIGHTS), 1)
        row["airfield_constrained"] = row["airfield_pressure"] >= AIRFIELD_CONSTRAINED_AT
        # Capital the FAA says the airport needs, per passenger it already
        # serves. High means a lot of building to serve the same traffic.
        row["development_need_per_enplanement"] = (
            round(row["development_need_usd"] / row["enplanements"], 2)
            if row["development_need_usd"] else None
        )
        # What the terminal earns from each passenger who walks through it.
        # Low against heavy traffic is the renovation case: the passengers are
        # already there and the airport is not selling to them.
        row["non_aero_revenue_per_enplanement"] = (
            round(row["non_aeronautical_revenue"] / row["enplanements"], 2)
            if row["non_aeronautical_revenue"] else None
        )
        row["operating_margin"] = (
            round(row["operating_income"] / row["operating_revenue"], 3)
            if row["operating_revenue"] else None
        )

    scored.sort(key=lambda r: r["score"], reverse=True)
    dropped = [
        {"iata": r["iata"], "name": r["name"], "state": r["state"],
         "enplanements": r["enplanements"], "missing": _missing_inputs(r)}
        for r in rows if r not in scored
    ]
    return {
        "ranked": scored[:limit],
        "weights": WEIGHTS,
        "airfield_weights": AIRFIELD_WEIGHTS,
        "unscored_missing_data": dropped or None,
        "note": "Scores are relative to the airports in this list only. Any "
                "airport under unscored_missing_data must be named in the "
                "answer, with what it is missing.",
        "method_note": "The score ranks the demand case for a terminal: "
                       "enplanement growth and metro population growth, the "
                       "two things extra gates can serve. Gate counts and "
                       "terminal floor area are not published federally, so "
                       "this is a demand proxy, not a measure of how full the "
                       "existing terminal is. "
                       "airfield_pressure is reported separately and is not in "
                       "the score. Where airfield_constrained is true the "
                       "runways, not the terminal, cap throughput, and a "
                       "terminal project alone adds no flights however strong "
                       "the demand case. Report that flag for every airport "
                       "that carries it.",
        "cost_note": "development_need_usd is the FAA's five-year estimate of "
                     "eligible development cost for the airport, and "
                     "development_need_per_enplanement divides it by annual "
                     "passengers. It is the only cost figure held, and it is "
                     "not in the score. It is needed development, not funded "
                     "or committed spend, and it covers airside work as well "
                     "as terminal work, so it is not a terminal price. Quote "
                     "it as scale of capital need per passenger and say what "
                     "it excludes.",
        "revenue_note": "non_aero_revenue_per_enplanement is what the airport "
                        "earns per passenger from food, retail, parking and "
                        "car hire, taken from its own FAA Form 127 filing. It "
                        "is the closest thing here to a return on a terminal: "
                        "heavy traffic with a low figure means passengers are "
                        "already there and the airport is not selling to them. "
                        "It is not in the score, it is a whole-airport figure "
                        "rather than a per-terminal one, and it is a year or "
                        "two behind the flight data, so quote the year with "
                        "it.",
    }


REGISTRY = {
    f.__name__: f
    for f in (
        data_coverage,
        airport_profile,
        traffic_and_delays,
        peak_hour_demand,
        route_distance_mix,
        cargo_growth,
        compare_airports,
        rank_expansion_candidates,
    )
}
