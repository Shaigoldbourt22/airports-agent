"""Retry sources that failed in the last run and patch MANIFEST.csv."""

import csv
import datetime
import pathlib
import sys

from fetch_sources import SOURCES, converter, fetch, header_block

ROOT = pathlib.Path(__file__).parent
DEST = ROOT / "originals"
MANIFEST = ROOT / "MANIFEST.csv"
ATTEMPTS = 3


def main() -> None:
    rows = list(csv.reader(MANIFEST.open(encoding="utf-8")))
    header, data = rows[0], rows[1:]
    failed = {r[0] for r in data if r[3] == "FAIL"}
    if not failed:
        print("Nothing to retry.")
        return

    urls = dict(SOURCES)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fixed = {}

    for name in failed:
        url = urls[name]
        for attempt in range(1, ATTEMPTS + 1):
            try:
                status, html = fetch(url, timeout=90)
                body = converter().handle(html)
                path = DEST / f"{name}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(header_block(url, now, status) + body, encoding="utf-8")
                fixed[name] = (status, len(body))
                print(f"OK   {name}  {len(body)} chars")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  {name} attempt {attempt}/{ATTEMPTS}: {exc}")
        else:
            print(f"FAIL {name}  still unreachable")

    for row in data:
        if row[0] in fixed:
            status, size = fixed[row[0]]
            row[2], row[3], row[4] = now, str(status), str(size)
            row[5] = f"originals/{row[0]}.md"

    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(data)

    still_failing = [r[0] for r in data if r[3] == "FAIL"]
    print(f"\nManifest updated. Still failing: {still_failing or 'none'}")
    sys.exit(1 if still_failing else 0)


if __name__ == "__main__":
    main()
