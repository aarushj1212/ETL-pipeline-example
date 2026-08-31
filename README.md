# pipeline-sentinel

[![CI](https://github.com/aarushjawdekar/pipeline-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/aarushjawdekar/pipeline-sentinel/actions/workflows/ci.yml)

A validation layer for data pipelines whose scariest failure mode is not a
crash — it's a **plausible number that is wrong**.

I built the ideas in this repository while automating the annual update of a
financial-markets statistical publication: hundreds of tables rebuilt every
year from central-bank APIs and downloaded spreadsheets. In that setting the
dangerous errors never throw exceptions. They look like this:

- a parser pinned to "data starts at row 8" meets a file with one fewer
  header row, scans past the first two countries, and emits them as missing;
- a value converted at the annual-average exchange rate instead of
  end-of-period shifts *every* row by a uniform 0.7% — under any sane alert
  threshold, and a genuine methodology error;
- a column pasted by position lands one row off after a spacer row, and
  every value is real, current, and attached to the wrong country.

This library is the distillation of what actually catches these. Not a
universal error detector (there isn't one), but four checks whose blind
spots don't overlap, wired so that a clean run costs the reviewer one
glance — because attention, not compute, is the scarce resource.

## The one-command pitch

The demo pipeline pulls gross debt-securities issuance for eight euro-area
countries from the [ECB's public API](https://data.ecb.europa.eu/data/datasets/csec),
validates it, and writes a formatted workbook:

```console
$ python demo/ecb_issuance.py --offline
identity EUR + X1 = _T: holds for every country-year
[2024] benchmark clean — all 8 overlapping values match — pipeline reproduces reference
tolerance flags for 2025: none — every change within its row's band
```

Now inject a classic silent error — an exchange-rate convention slip that
moves every value by ~1.3%. No threshold-based alert fires (the tolerance
bands rightly accept ±1.3% as noise), and nothing crashes. It is caught
anyway, and the report names the likely culprit:

```console
$ python demo/ecb_issuance.py --offline --sabotage fx
identity EUR + X1 = _T: holds for every country-year
[2024] benchmark: uniform ratio across rows: reference ≈ candidate × 0.987167 — suspect FX rate, units, or scaling
tolerance flags for 2025: none — every change within its row's band
```

That is the design thesis in one run: **magnitude thresholds cannot
distinguish error from event, but the *pattern* of a discrepancy across rows
identifies its cause.** A uniform ratio is an FX/units/scaling slip. A shared
sign is an omitted component. Mixed signs on a mostly-exact table are
retroactive source revisions, and staying calm about those is as important
as being loud about the rest.

Try `--sabotage units` (a thousand-fold scaling slip) and `--sabotage drop`
(a country quietly lost) to see the other failure classes get caught by the
checks designed for them.

## What's inside

| Module | Principle | Silent failure it prevents |
|---|---|---|
| `sentinel.landmarks` | Locate data by what stays constant, never by coordinates; align rows by label, never by position | Header-row drift; spacer rows; reordered country blocks |
| `sentinel.tolerance` | Judge each series against its own history — a per-row 2σ band on year-on-year changes, with an honest fallback when history is short | One flat threshold that's too noisy for volatile rows and too permissive for stable ones; values that silently vanish or reappear |
| `sentinel.discrepancy` | Classify disagreements by pattern, not magnitude | Small uniform methodology errors passing under thresholds; revision noise wasting reviewer attention |
| `sentinel.benchmark` | Reproduce a known period through the *same code path* before trusting the new one | Any extraction bug — caught on known answers before the new year inherits it |

The full reasoning — including the real incidents each check is distilled
from and the two structural blind spots this approach *cannot* cover (and
what covers them instead) — is in
[**docs/design-principles.md**](docs/design-principles.md). That document is
the point of the repository; the code is its executable appendix.

## Quickstart

```console
pip install -e ".[dev]"
pytest -q                              # 34 tests, each reenacting a real failure mode
python demo/ecb_issuance.py            # live ECB API
python demo/ecb_issuance.py --offline  # cached fixture, no network
```

Library usage is three calls:

```python
from sentinel import LabelMap, flag_table, run_benchmark

# 1. Align source rows to target rows by label — never by position
alignment = LabelMap(target_labels, aliases={"Korea": "Korea, Rep."}).align(source_labels)

# 2. Re-extract a known period through your real extraction path
result = run_benchmark(extract, last_years_values, "2024")
print("\n".join(result.lines()))   # one line when clean; the pattern when not

# 3. Judge the new column against each row's own history
for flag in flag_table(history_by_row, new_column):
    print(flag)
```

## Design notes

- **Checks are free, questions are expensive.** Every check runs on every
  run; only exceptions surface. A wall of per-table confirmations gets
  rubber-stamped, and a rubber-stamped check protects nothing.
- **No fuzzy matching, ever.** Label differences are bridged by declared
  aliases. Guessing a mapping is exactly the judgment call a pipeline must
  not make on a human's behalf.
- **Fabrication is worse than absence.** Nothing in this library ever fills
  a gap with a placeholder. A visible hole invites a question; a fabricated
  cell answers it wrongly.
- **Stdlib-only core.** The library has zero dependencies; `requests` and
  `openpyxl` appear only in the demo.

## Built with an AI pair, deliberately

This repository was implemented with Claude Code, under a spec-first
workflow where check designs are reviewed in plain language before any code
exists, and every output is verified structurally (changelogs, read-back
verification, this test suite) rather than by trust.
[docs/ai-workflow.md](docs/ai-workflow.md) describes the working method;
[CLAUDE.md](CLAUDE.md) is the live context file agents work under.

## License

MIT — see [LICENSE](LICENSE).
