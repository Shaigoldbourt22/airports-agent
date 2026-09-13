"""Catchment demand from the Census Bureau API.

An airport's runways say what it can handle today. They say nothing about
whether the population it serves is growing, which is what a terminal built
now has to serve for the next thirty years.

Metro population is deliberately not used: it correlates with enplanements per
runway at r=0.99, so it would add weight without adding information. The growth
rate does not (r = -0.65 to +0.20), and it disagrees with airline schedules in
useful ways. Bangor's enplanements rose 16% in a metro growing 2.8%; Portland's
rose 5% in a metro growing 5.8%.

Airports are matched to metros by coordinates through the Census geocoder, not
by name. Census calls BDL's metro "Hartford-West Hartford-East Hartford", which
appears in no airport field.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# One-year ACS estimates. The five-year gap is long enough for a trend to show
# and short enough to still describe the metro an investor would buy into.
CURRENT_YEAR = 2023
BASELINE_YEAR = 2018

POPULATION = "B01003_001E"
ACS = "https://api.census.gov/data/{year}/acs/acs1"
CBSA_GEO = "metropolitan statistical area/micropolitan statistical area"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

# Census marks a suppressed or unavailable estimate with this sentinel rather
# than omitting the field.
MISSING = "-666666666"

# A CBSA code can be reused after its boundary changes, so the same code may
# cover different territory in two vintages. New Haven went from
# "New Haven-Milford" to "New Haven" when Connecticut moved to planning
# regions, which looks like a 34% population collapse. Comparing the names
# catches the redefinitions; this bound catches the rest, since no metro
# genuinely gains or loses a fifth of its people in five years.
MAX_PLAUSIBLE_GROWTH = 0.20


class CensusUnavailable(RuntimeError):
    """No API key, so catchment data cannot be fetched."""


def _get(url: str, timeout: int = 60):
    request = urllib.request.Request(url, headers={"User-Agent": "airports-agent/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _key() -> str:
    """The API key, from the environment or from .env when run locally.

    In Azure the ETL job gets it as a container environment variable. On a
    developer machine it sits in .env, which the ETL does not otherwise read,
    so it is parsed here rather than adding a dependency to the ETL image.
    """
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        return key

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "CENSUS_API_KEY" and value.strip():
                return value.strip().strip('"').strip("'")

    raise CensusUnavailable("CENSUS_API_KEY is not set")


def metro_population(year: int) -> dict[str, tuple[str, int]]:
    """Name and population by CBSA code for one ACS year.

    The name is returned alongside the count because a code alone cannot tell
    you whether two vintages describe the same territory.
    """
    query = urllib.parse.urlencode({
        "get": f"NAME,{POPULATION}",
        "for": f"{CBSA_GEO}:*",
        "key": _key(),
    })
    rows = _get(f"{ACS.format(year=year)}?{query}")
    return {
        row[2]: (row[0], int(row[1]))
        for row in rows[1:]
        if row[1] and row[1] != MISSING
    }


def growth(current: dict, baseline: dict, cbsa: str) -> float | None:
    """Five-year population growth, or None when the metro was redefined.

    Returning None is the honest answer: we cannot measure growth across a
    boundary change, and reporting the difference anyway would put a fictional
    collapse into the score.
    """
    if cbsa not in current or cbsa not in baseline:
        return None
    name_now, population_now = current[cbsa]
    name_then, population_then = baseline[cbsa]
    if population_then <= 0 or name_now != name_then:
        return None
    change = (population_now - population_then) / population_then
    return None if abs(change) > MAX_PLAUSIBLE_GROWTH else change


def metro_names(year: int = CURRENT_YEAR) -> dict[str, str]:
    return {code: name for code, (name, _) in metro_population(year).items()}


def locate(latitude: float, longitude: float) -> tuple[str | None, str | None]:
    """The metro area containing a point, as (cbsa code, name).

    Layer 93 is Metropolitan Statistical Areas. An airport outside every metro
    returns (None, None), which is a real answer: rural airports have no
    catchment in this sense.
    """
    query = urllib.parse.urlencode({
        "x": longitude,
        "y": latitude,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "93",
        "format": "json",
    })
    try:
        data = _get(f"{GEOCODER}?{query}", timeout=30)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None, None
    areas = data.get("result", {}).get("geographies", {}).get(
        "Metropolitan Statistical Areas", []
    )
    if not areas:
        return None, None
    return areas[0]["GEOID"], areas[0]["NAME"]
