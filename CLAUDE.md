# CLAUDE.md: project conventions

Working agreements for AI sessions (and humans) in this repository.

## Commands

- Test: `pytest -q`
- Lint: `ruff check .`
- Demo (offline, deterministic): `python demo/ecb_issuance.py --offline`
- Demo failure drills: `--sabotage units|fx|drop` (expected to exit 1)

## Non-negotiable design rules

These are settled decisions; do not relitigate them in code:

1. **Align by label, never by position.** Any transfer of values between
   tables goes through `sentinel.landmarks.LabelMap`.
2. **No fuzzy matching.** Name differences are bridged by declared aliases.
   If a label doesn't match, the correct behaviour is to report it, not to
   guess.
3. **Locate data by landmark, never by coordinate.** No hard-coded row or
   column numbers when reading a source; find the header text and derive
   positions from it. Missing landmark = raise, loudly.
4. **Exceptions-only reporting.** A clean check emits at most one summary
   line. Never add per-row confirmation output.
5. **Never fabricate a value.** No placeholders, no carry-forward, no
   silent zeros. Missing is missing.
6. **The benchmark path is the production path.** `run_benchmark` must be
   fed the same extraction callable used for the new period.

## Style

- Python ≥ 3.10, stdlib-first; `requests`/`openpyxl` only in `demo/`.
- Docstrings explain *why the check exists* (the failure it prevents), not
  just what the function does; that is the point of this repository.
- Keep the library dependency-free and the demo self-contained.

## Fixtures

`demo/fixtures/csec_gross_s1.csv` is a cached ECB CSEC API response
(gross issuance, 8 euro-area countries, 2014-01 onward); regenerate it by
running the demo live and re-trimming columns. `reference_2024.json` plays
the role of "last year's published edition" for the benchmark.
