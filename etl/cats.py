"""Airport financial reports from the FAA CATS system.

Every commercial service airport files Form 127 each year: operating revenue
split between aeronautical and non-aeronautical sources, operating expenses,
capital spending by category, and debt. It is the only per-airport money in the
whole pipeline. Everything else measures demand or physical constraint, none of
which says whether a site earns anything from the passengers it already has.

The figure that matters most for terminal investment is non-aeronautical
revenue per enplanement: concessions, food, retail, parking and rental cars,
divided by passengers. An airport with heavy traffic and thin spend per head is
the textbook renovation case, because the passengers are already there and the
airport is not selling to them. Aeronautical revenue does not show that, since
landing fees follow aircraft weight rather than how good the terminal is.

Two things about this source are easy to get wrong.

The CSV export returns HTTP 500 and has done so on every attempt, so the HTML
report is parsed instead. Line items are numbered and those numbers are stable
across years, so rows are matched on the leading number rather than on wording,
which does drift.

The site keys airports by an internal numeric id, not by location code, and the
location and airport dropdowns are sorted differently, so their options cannot
be paired positionally: doing that maps BOS to Chevak. Each report page states
its own location ID, so the mapping is read from the reports themselves.
"""

import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://cats.airports.faa.gov/reports/form_127/"
HEADERS = {"User-Agent": "airports-agent/1.0"}

# Line items to keep, by the number the form gives them. Wording changes
# between editions; the numbering has not.
LINE_ITEMS = {
    "3.0": "aeronautical_revenue",
    "4.2": "terminal_food_beverage",
    "4.3": "terminal_retail",
    "4.6": "parking_ground_transport",
    "4.9": "non_aeronautical_revenue",
    "5.0": "operating_revenue",
    "6.9": "operating_expenses",
    "7.0": "operating_income",
    "10.2": "capex_terminal",
    "10.6": "capex_total",
    "11.4": "total_debt",
}

FIELDS = list(dict.fromkeys(LINE_ITEMS.values()))


def _get(**params) -> str:
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode("utf-8", "replace")


def _money(text: str) -> int | None:
    """Parse a form amount. Losses are shown in brackets, not with a minus."""
    cleaned = text.strip().replace("$", "").replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    value = int(float(cleaned))
    return -value if negative else value


def airport_ids() -> list[str]:
    """The site's internal ids for every airport that files the form."""
    html = _get()
    block = re.search(
        r"<select[^>]*name=[\"']airportID[\"'][^>]*>(.*?)</select>", html, re.S | re.I)
    if not block:
        return []
    values = re.findall(r"<option[^>]*value=[\"']([^\"']*)[\"']", block.group(1))
    return [v for v in values if v.strip()]


def report(airport_id: str, year: int) -> dict | None:
    """One airport's filing, or None where it did not file that year."""
    try:
        html = _get(year=year, airportID=airport_id)
    except (urllib.error.URLError, OSError):
        return None

    loc = re.search(
        r"Airport location ID\s*</dt>\s*<dd>\s*([A-Z0-9]{3,4})\b", html, re.I)
    name = re.search(
        r"Airport name\s*</dt>\s*<dd>\s*([^<]+)", html, re.I)
    if not loc:
        return None

    values: dict[str, int] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = [re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
        if len(cells) < 2:
            continue
        number = re.match(r"(\d+\.\d+)\s", cells[0])
        if not number or number.group(1) not in LINE_ITEMS:
            continue
        amount = _money(cells[1])
        if amount is not None:
            values[LINE_ITEMS[number.group(1)]] = amount

    # A page renders for an airport that filed nothing, so an empty report has
    # to be rejected rather than stored as a row of zeroes.
    if not values.get("operating_revenue"):
        return None

    return {
        "iata": loc.group(1).upper(),
        "name": name.group(1).strip() if name else "",
        "year": year,
        **{field: values.get(field) for field in FIELDS},
    }


def fetch_all(year: int, wanted: set[str] | None = None,
              log=print) -> list[dict]:
    """Every filing for a year, optionally limited to airports we hold.

    One request per airport, so the filter matters: most of the 668 filers are
    small fields that never appear in a ranking. Airports are only known by
    code after their page is fetched, so the filter is applied on the way out.
    """
    ids = airport_ids()
    log(f"  {len(ids)} airports file this form")
    rows = []
    for i, airport_id in enumerate(ids, 1):
        row = report(airport_id, year)
        if row and (wanted is None or row["iata"] in wanted):
            rows.append(row)
        if i % 100 == 0:
            log(f"  {i}/{len(ids)} checked, {len(rows)} kept")
    return rows
