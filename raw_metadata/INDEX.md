# Raw Metadata — Source Archive

Every external page we take information from is archived here **in full, as fetched**.

```
raw_metadata/
  originals/
    faa/            FAA — airport categories, capacity, operations, enplanements
    bts/            BTS TranStats — T-100, on-time performance
    ourairports/    OurAirports — runway and airport reference data
    voice/          MDN — Web Speech API
    gemini/         Google — model docs
  MANIFEST.csv        url, fetch timestamp, HTTP status, size per file
  fetch_sources.py    re-run to refresh the archive
  retry_failed.py     retry any source that failed, patch the manifest
```

## Rule

If a claim appears in `design/`, its source page is in `originals/`. If it is not
there, the claim must be labelled `[OUR CHOICE]` or `[UNVERIFIED]`.

**These files are not summaries.** The HTML is converted to Markdown and nothing else —
no condensing, no paraphrase, no omission. The only addition is a comment block at the
top recording the URL, fetch time and HTTP status. A summary is the thing under review,
so it cannot also be the evidence.

## Why archive the whole page

Public sources move. FAA retires reports, BTS shifts its lag, browser support changes,
Google deprecates models. A link alone proves nothing later. The archive shows what the
page said on the day we read it — including the parts we did not quote, which is where a
misread would hide.

Markdown rather than HTML so the text is readable and diffable in review.

## Refreshing

```powershell
python raw_metadata/fetch_sources.py    # refetch everything
python raw_metadata/retry_failed.py     # retry only what failed
```

Run before treating any claim as current, then check `git diff` — a changed page is a
signal that a design assumption needs rechecking. FAA hosts time out intermittently;
`retry_failed.py` exits non-zero while anything is still missing.

## What is archived

### FAA

| File | Page | Used for |
|---|---|---|
| [faa-airport-categories.md](originals/faa/faa-airport-categories.md) | Airport Categories | Hub-class thresholds (49 USC 47102), airport counts |
| [faa-capacity-profiles.md](originals/faa/faa-capacity-profiles.md) | Airport Capacity Profiles | Measured runway capacity; which airports have one |
| [faa-enplanements.md](originals/faa/faa-enplanements.md) | Passenger Boarding data | Per-airport enplanements, hub assignment, release dates |
| [faa-npias.md](originals/faa/faa-npias.md) | NPIAS | Airport system scope |
| [faa-opsnet-main.md](originals/faa/faa-opsnet-main.md) | OPSNET | Operations counts, publication lag |
| [faa-opsnet-airport.md](originals/faa/faa-opsnet-airport.md) | OPSNET Airport Operations | The query interface we pull from |
| [faa-aspm-portal.md](originals/faa/faa-aspm-portal.md) | ASPM | Evidence ASPM needs a login — why we rejected it |
| [faa-nasr-subscription.md](originals/faa/faa-nasr-subscription.md) | NASR / Form 5010 | Runway data; absence of gate and terminal fields |
| [faa-by-the-numbers.md](originals/faa/faa-by-the-numbers.md) | Air Traffic By The Numbers | US airport counts |

### BTS

| File | Page | Used for |
|---|---|---|
| [bts-transtats-latest-data.md](originals/bts/bts-transtats-latest-data.md) | TranStats latest-available table | Current data lag per dataset |
| [bts-transtats-download.md](originals/bts/bts-transtats-download.md) | TranStats download tool | Proof it is a form POST, not an API |
| [bts-ontime-dbinfo.md](originals/bts/bts-ontime-dbinfo.md) | On-Time Performance | Delay field schema, `DEP_DEL15` |

### OurAirports

| File | Page | Used for |
|---|---|---|
| [ourairports-data.md](originals/ourairports/ourairports-data.md) | Downloads | Public-domain licence, file list |
| [ourairports-data-dictionary.md](originals/ourairports/ourairports-data-dictionary.md) | Data dictionary | Column meanings for runways and airports |

### Voice

| File | Page | Used for |
|---|---|---|
| [mdn-speechrecognition.md](originals/voice/mdn-speechrecognition.md) | MDN SpeechRecognition | Browser support; server-side audio note |
| [mdn-speechrecognition-processlocally.md](originals/voice/mdn-speechrecognition-processlocally.md) | MDN `processLocally` | On-device recognition support matrix |

### Gemini

| File | Page | Used for |
|---|---|---|
| [gemini-function-calling.md](originals/gemini/gemini-function-calling.md) | Function calling | Tool loop, declaration schema, model ID |
| [gemini-models.md](originals/gemini/gemini-models.md) | Model list | Which Flash model is current |
| [gemini-rate-limits.md](originals/gemini/gemini-rate-limits.md) | Rate limits | Evidence free-tier quotas are not published |

See `MANIFEST.csv` for exact fetch timestamps and sizes.

## Not archivable

Two claims in `design/` cannot be backed by a page here, because both rest on absence:

- **Gate counts and terminal floor area.** No free public dataset publishes them. The
  evidence is the missing fields in `originals/faa/faa-nasr-subscription.md` and
  `originals/ourairports/ourairports-data-dictionary.md`. This is what removed the
  terminal component from our scoring model.
- **"Long-haul" as a standard distance.** No FAA, BTS, ICAO or IATA page defines one, so
  there is nothing to archive. Our 3,000-mile cutoff is labelled `[OUR CHOICE]`.
