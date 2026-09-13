# 3. The ETL job

ETL means Extract, Transform, Load: grab the raw files, reshape them, save
them somewhere useful. It all lives in `etl/build_db.py`.

The headline problem: BTS gives us millions of individual flight rows, and we
cannot ship that. So **no flight row is ever stored**. As each month's ZIP is
streamed through, flights are collapsed into counters — per airport per month,
per airport per hour, per route per month. The finished database is about 8 MB.

Downloads are cached on disk, so a rerun does not refetch a 200 MB ZIP.

Two transformations are worth knowing:

**Parallel runway spacing.** Runways whose numbers match (28L and 28R) are
parallel. We measure the great-circle distance between their approach ends and
convert to feet. That number does not exist in any dataset; we derive it.

**Catchment.** Each big airport's coordinates are sent to the Census geocoder
to find its metro area, then we look up that metro's population now and five
years ago. Name matching would fail — Census calls BDL's metro
"Hartford-West Hartford-East Hartford", which appears in no airport field.
Only airports above 250,000 passengers are geocoded, since each one costs a
request.

The job writes the database file, and the app swaps to it automatically.
