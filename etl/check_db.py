"""Sanity checks against the built database."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "airports.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def show(title, sql, params=()):
    print(f"\n--- {title} ---")
    rows = con.execute(sql, params).fetchall()
    if not rows:
        print("  (no rows)")
        return
    print("  " + " | ".join(rows[0].keys()))
    for r in rows:
        print("  " + " | ".join("" if v is None else str(v) for v in r))


show("row counts", """
    SELECT 'airport' t, COUNT(*) n FROM airport
    UNION ALL SELECT 'enplanement', COUNT(*) FROM enplanement
    UNION ALL SELECT 'cargo', COUNT(*) FROM cargo
    UNION ALL SELECT 'airport_month', COUNT(*) FROM airport_month
    UNION ALL SELECT 'airport_hour', COUNT(*) FROM airport_hour
    UNION ALL SELECT 'route_month', COUNT(*) FROM route_month
""")

show("sources", "SELECT * FROM source_meta")

show("New England airports with enplanements", """
    SELECT a.iata, a.state, e.enplanements, ROUND(e.pct_change*100,1) pct,
           a.runway_count rw
    FROM airport a JOIN enplanement e ON e.iata = a.iata
    WHERE a.state IN ('MA','CT','RI','NH','ME','VT') AND e.enplanements > 100000
    ORDER BY e.enplanements DESC
""")

show("congestion, LAX vs SNA", """
    SELECT iata, SUM(departures) dep, SUM(arrivals) arr,
           ROUND(100.0*SUM(dep_del15)/SUM(departures),1) dep_del_pct,
           ROUND(100.0*SUM(arr_del15)/SUM(arrivals),1) arr_del_pct,
           ROUND(100.0*SUM(cancelled)/(SUM(departures)+SUM(arrivals)),2) canc_pct
    FROM airport_month WHERE iata IN ('LAX','SNA','SFO') GROUP BY iata
""")

show("ANC long-haul share by month", """
    SELECT year, month, departures, longhaul_dep,
           ROUND(100.0*longhaul_dep/departures,1) pct
    FROM airport_month WHERE iata='ANC' ORDER BY year, month
""")

show("SFO peak hour: scheduled vs achieved", """
    SELECT hour, MAX(peak_sched_arr) sched, MAX(peak_actual_arr) actual,
           MAX(peak_sched_arr)-MAX(peak_actual_arr) gap
    FROM airport_hour WHERE iata='SFO'
    GROUP BY hour ORDER BY sched DESC LIMIT 5
""")

show("top ANC long-haul routes", """
    SELECT dest, SUM(flights) flights, distance_mi
    FROM route_month WHERE origin='ANC' AND distance_mi >= 3000
    GROUP BY dest, distance_mi ORDER BY flights DESC
""")

show("terminal pressure, New England (peak concurrent departures)", """
    SELECT h.iata, MAX(h.peak_sched_dep) peak_dep,
           e.enplanements, ROUND(e.pct_change*100,1) growth
    FROM airport_hour h
    JOIN airport a ON a.iata = h.iata
    JOIN enplanement e ON e.iata = h.iata
    WHERE a.state IN ('MA','CT','RI','NH','ME','VT')
    GROUP BY h.iata ORDER BY peak_dep DESC LIMIT 10
""")

con.close()
