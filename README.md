# pipeline-sentinel

[![CI](https://github.com/aarushjawdekar/pipeline-sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/aarushjawdekar/pipeline-sentinel/actions/workflows/ci.yml)

The most expensive failure in a data pipeline is a plausible number that is
wrong. A crash announces itself and gets fixed the same afternoon; a
wrong-but-plausible number gets published. I built the ideas in this
repository while automating the annual update of a financial-markets
statistical publication, where hundreds of tables are rebuilt every year
from central-bank APIs and downloaded spreadsheets, and where the errors
that matter never throw exceptions. Three examples from that work:

- a parser pinned to "data starts at row 8" meets a file with one fewer
  header row, scans past the first two countries, and emits them as missing;
- a value converted at the annual-average exchange rate instead of
  end-of-period shifts every row by a uniform 0.7%, which is under any sane
  alert threshold and is a genuine methodology error;
- a column pasted by position lands one row off after a spacer row, and
  every value is real, current, and attached to the wrong country.

Predicting every possible error in the abstract is impossible, so this
library does not try. It implements four checks whose blind spots do not
overlap, and it reports by exception, so that a clean run costs the
reviewer one glance. The reviewer's attention is the scarce resource in
this kind of work, and the design spends it carefully.

## The demo

The demo pipeline pulls gross debt-securities issuance for eight euro-area
countries from the [ECB's public API](https://data.ecb.europa.eu/data/datasets/csec),
validates it, and writes a formatted workbook:

```console
$ python demo/ecb_issuance.py --offline
identity EUR + X1 = _T: holds for every country-year
[2024] benchmark clean: all 8 overlapping values match; pipeline reproduces reference
tolerance flags for 2025: none; every change within its row's band
```

Now inject a classic silent error: an exchange-rate convention slip that
moves every value by about 1.3%. No threshold-based alert fires, since the
tolerance bands rightly accept a 1.3% move as noise, and nothing crashes.
It is caught anyway, and the report names the likely culprit:

```console
$ python demo/ecb_issuance.py --offline --sabotage fx
identity EUR + X1 = _T: holds for every country-year
[2024] benchmark: uniform ratio across rows: reference ≈ candidate × 0.987167; suspect FX rate, units, or scaling
tolerance flags for 2025: none; every change within its row's band
```

This run makes the argument for the whole design. The size of a discrepancy
says little about its cause, but its pattern across rows says a lot: a
uniform ratio points to an FX, units or scaling slip, a shared sign points
to a component omitted or double-counted, and mixed signs on a mostly-exact
table usually mean retroactive source revisions, which deserve a calm
ranking rather than an alarm. There are two further drills, `--sabotage
units` (a thousand-fold scaling slip) and `--sabotage drop` (a country
quietly lost), each caught by the check designed for its failure class.

## What's inside

| Module | Principle | Silent failure it prevents |
|---|---|---|
| `sentinel.landmarks` | Locate data by what stays constant, never by coordinates; align rows by label, never by position | Header-row drift; spacer rows; reordered country blocks |
| `sentinel.tolerance` | Judge each series against its own history: a per-row 2σ band on year-on-year changes, with a flat fallback when history is short | One flat threshold that is too noisy for volatile rows and too permissive for stable ones; values that silently vanish or reappear |
| `sentinel.discrepancy` | Classify disagreements by pattern, not magnitude | Small uniform methodology errors passing under thresholds; revision noise wasting reviewer attention |
| `sentinel.benchmark` | Reproduce a known period through the same code path before trusting the new one | Any extraction bug, caught on known answers before the new year inherits it |

The reasoning behind each check, including the real incidents they are
distilled from and the two blind spots this approach cannot cover, is in
[docs/design-principles.md](docs/design-principles.md). I consider that
document the core of the repository; the code is the working
implementation of it.

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

# 1. Align source rows to target rows by label, never by position
alignment = LabelMap(target_labels, aliases={"Korea": "Korea, Rep."}).align(source_labels)

# 2. Re-extract a known period through your real extraction path
result = run_benchmark(extract, last_years_values, "2024")
print("\n".join(result.lines()))   # one line when clean; the pattern when not

# 3. Judge the new column against each row's own history
for flag in flag_table(history_by_row, new_column):
    print(flag)
```

## Design notes

Two rules hold everywhere in the library. First, checks run silently and
only exceptions surface, because a wall of per-table confirmations gets
rubber-stamped, and a rubber-stamped check protects nothing. Second, the
code never guesses on the human's behalf: label differences are bridged by
declared aliases rather than fuzzy matching, and a gap is never filled with
a placeholder value, since a visible hole invites a question while a
fabricated cell answers it wrongly. The core library has no dependencies;
`requests` and `openpyxl` appear only in the demo.

## How this was built

This repository was implemented with Claude Code. I reviewed every check
design in plain language before any code was written, and outputs are
verified through the test suite and by reading files back rather than
trusting that a write happened as intended.
[docs/ai-workflow.md](docs/ai-workflow.md) describes the working method,
and [CLAUDE.md](CLAUDE.md) is the context file agent sessions work under.

## License

MIT; see [LICENSE](LICENSE).
