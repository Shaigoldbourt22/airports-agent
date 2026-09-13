"""Fetch every source cited in design/ and archive it as Markdown.

The page text is converted, not rewritten: no summarizing, no editing, no omissions.
Only a small provenance header is prepended, above a marker line.

Usage:
    python raw_metadata/fetch_sources.py
"""

import csv
import datetime
import http.cookiejar
import pathlib
import urllib.request

import html2text

SOURCES = [
    ("faa/faa-airport-categories", "https://www.faa.gov/airports/planning_capacity/categories"),
    ("faa/faa-capacity-profiles", "https://www.faa.gov/airports/planning_capacity/profiles"),
    ("faa/faa-enplanements", "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger"),
    ("faa/faa-npias", "https://www.faa.gov/airports/planning_capacity/npias"),
    ("faa/faa-opsnet-main", "https://aspm.faa.gov/opsnet/sys/main.asp"),
    ("faa/faa-opsnet-airport", "https://aspm.faa.gov/opsnet/sys/Airport.asp"),
    ("faa/faa-aspm-portal", "https://aspm.faa.gov/"),
    ("faa/faa-nasr-subscription", "https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/"),
    ("faa/faa-by-the-numbers", "https://www.faa.gov/air_traffic/by_the_numbers"),
    ("bts/bts-transtats-latest-data", "https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FIL"),
    ("bts/bts-transtats-download", "https://www.transtats.bts.gov/DL_SelectFields.aspx"),
    ("bts/bts-ontime-dbinfo", "https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFD&Yv0x=D"),
    ("ourairports/ourairports-data", "https://ourairports.com/data/"),
    ("ourairports/ourairports-data-dictionary", "https://ourairports.com/help/data-dictionary.html"),
    ("voice/mdn-speechrecognition", "https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition"),
    ("voice/mdn-speechrecognition-processlocally", "https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/processLocally"),
    ("gemini/gemini-function-calling", "https://ai.google.dev/gemini-api/docs/function-calling"),
    ("gemini/gemini-models", "https://ai.google.dev/gemini-api/docs/models"),
    ("gemini/gemini-rate-limits", "https://ai.google.dev/gemini-api/docs/rate-limits"),
]

ROOT = pathlib.Path(__file__).parent
DEST = ROOT / "originals"
USER_AGENT = "Mozilla/5.0 (compatible; airport-agent-archiver/1.0)"


def converter() -> html2text.HTML2Text:
    h = html2text.HTML2Text()
    h.body_width = 0          # no rewrapping, keep the text as-is
    h.ignore_links = False
    h.ignore_images = True
    h.ignore_emphasis = False
    h.unicode_snob = True
    h.single_line_break = True
    return h


def opener() -> urllib.request.OpenerDirector:
    """Cookie-aware opener. aspm.faa.gov issues a session cookie and redirect-loops
    without it."""
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def fetch(url: str, timeout: int = 60) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener().open(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.status, resp.read().decode(charset, errors="replace")


def header_block(url: str, fetched_at: str, status: int) -> str:
    return (
        f"<!--\n"
        f"Source:  {url}\n"
        f"Fetched: {fetched_at}\n"
        f"Status:  {status}\n"
        f"Converted from HTML to Markdown verbatim. Text is unmodified.\n"
        f"-->\n\n"
    )


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for name, url in SOURCES:
        path = DEST / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            status, html = fetch(url)
            body = converter().handle(html)
            path.write_text(header_block(url, fetched_at, status) + body, encoding="utf-8")

            rows.append([name, url, fetched_at, status, len(body), f"originals/{name}.md"])
            print(f"OK   {name}  {len(body)} chars")

        except Exception as exc:  # noqa: BLE001 - archiving is best-effort per source
            rows.append([name, url, fetched_at, "FAIL", 0, ""])
            print(f"FAIL {name}  {exc}")

    with (ROOT / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "url", "fetched_at", "status", "chars", "file"])
        writer.writerows(rows)

    print("\nManifest written to raw_metadata/MANIFEST.csv")


if __name__ == "__main__":
    main()
