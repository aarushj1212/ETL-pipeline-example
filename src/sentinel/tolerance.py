"""Judge each series against its own history, not a flat threshold.

A single percentage band applied to every row of a table is simultaneously
too noisy and too permissive: derivatives turnover routinely doubles in a
year, while a large economy's outstanding debt moving 25% would be
extraordinary. One threshold cannot serve both.

Instead, each row is its own null hypothesis. Take the row's historical
year-on-year changes, estimate their mean and standard deviation, and flag
the newest change when it sits outside ``n_sigma`` standard deviations of
that history. Volatile series earn wide bands; stable series earn tight
ones — from their own record, with zero per-row configuration.

Two honest caveats, encoded rather than ignored:

- A σ estimated from few observations is noise. Below ``min_history``
  changes, fall back to a flat band instead of trusting it.
- Financial series are fat-tailed: a few historical shocks inflate σ and
  desensitise the test, so expect *fewer* flags than a normal distribution
  would predict. The band is a triage tool, not a hypothesis test.

Transitions between "has data" and "missing" are flagged unconditionally.
A value that disappears (or a gap that suddenly fills) is invisible to any
magnitude test — and a run of fresh NAs is more often a parsing bug than a
fact about the world.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Mapping, Sequence

Number = float | int
Value = Number | None


@dataclass(frozen=True)
class Flag:
    """One suspicious cell, with enough context to review it at a glance."""

    label: str
    reason: str  # "outlier" | "went_missing" | "reappeared"
    new_value: Value
    previous_value: Value
    change_pct: float | None = None  # observed year-on-year change
    band: tuple[float, float] | None = None  # (low, high) accepted range, in pct
    basis: str | None = None  # "2.0σ over 12 changes" or "flat ±25% (short history)"

    def __str__(self) -> str:
        if self.reason == "went_missing":
            return f"{self.label}: had {self.previous_value} last period, now missing"
        if self.reason == "reappeared":
            return f"{self.label}: was missing last period, now {self.new_value}"
        lo, hi = self.band  # type: ignore[misc]
        return (
            f"{self.label}: {self.change_pct:+.1%} vs accepted "
            f"[{lo:+.1%}, {hi:+.1%}] ({self.basis}); "
            f"{self.previous_value:,.3f} -> {self.new_value:,.3f}"
        )


def _pct_changes(history: Sequence[Value]) -> list[float]:
    """Consecutive year-on-year % changes over the row's own history.

    Only adjacent (prev, curr) pairs where both exist and prev != 0 count.
    A gap breaks the pair — bridging it would manufacture a change that
    never happened as a single-year move.
    """
    changes: list[float] = []
    for prev, curr in zip(history, history[1:]):
        if prev is None or curr is None or prev == 0:
            continue
        changes.append((curr - prev) / abs(prev))
    return changes


def flag_series(
    label: str,
    history: Sequence[Value],
    new_value: Value,
    *,
    n_sigma: float = 2.0,
    min_history: int = 8,
    fallback_pct: float = 0.25,
) -> Flag | None:
    """Assess one new observation against the series' own record.

    ``history`` is the row's existing values in chronological order (use
    ``None`` for missing years); ``new_value`` is the freshly produced
    figure. Returns a :class:`Flag` when the value deserves human eyes,
    else ``None`` — silence is the designed output for clean data.
    """
    if not history:
        return None  # brand-new row: nothing to compare against
    previous = history[-1]

    # Presence transitions first: no magnitude test can see these.
    if new_value is None:
        return (
            Flag(label, "went_missing", None, previous)
            if previous is not None
            else None  # missing -> still missing: not news
        )
    if previous is None:
        return Flag(label, "reappeared", new_value, None)
    if previous == 0:
        return None  # zero base: a % change is undefined, not suspicious

    change = (new_value - previous) / abs(previous)
    changes = _pct_changes(history)

    if len(changes) >= min_history:
        mu = statistics.fmean(changes)
        sigma = statistics.stdev(changes)
        band = (mu - n_sigma * sigma, mu + n_sigma * sigma)
        basis = f"{n_sigma:g}σ over {len(changes)} changes"
    else:
        band = (-fallback_pct, fallback_pct)
        basis = f"flat ±{fallback_pct:.0%} (short history: {len(changes)} changes)"

    if band[0] <= change <= band[1]:
        return None
    return Flag(label, "outlier", new_value, previous, change, band, basis)


def flag_table(
    table: Mapping[str, Sequence[Value]],
    new_column: Mapping[str, Value],
    **kwargs: float,
) -> list[Flag]:
    """Run :func:`flag_series` across a whole table.

    ``table`` maps row label -> historical values; ``new_column`` maps row
    label -> the newly produced value (labels absent from ``new_column``
    are treated as missing, which is itself flaggable). Returns only the
    exceptions: an empty list is a clean bill of health.
    """
    flags: list[Flag] = []
    for row_label, history in table.items():
        f = flag_series(row_label, history, new_column.get(row_label), **kwargs)
        if f is not None:
            flags.append(f)
    return flags
