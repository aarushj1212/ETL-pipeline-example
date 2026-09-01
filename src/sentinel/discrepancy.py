"""Classify disagreements by pattern, not magnitude.

When a rebuilt table disagrees with a reference version, the size of the
discrepancy says almost nothing about its cause. A 0.7% uniform gap across
every country can be a wrong exchange-rate convention (annual-average vs
end-of-period), a systematic methodology error a "flag if >2%" rule waves
straight through. Meanwhile a genuine data revision can move one country
by 30% and mean nothing at all.

What identifies the cause is the *shape* of the disagreement across rows:

- Same ratio everywhere       -> multiplicative error: FX rate, unit,
  scaling. Report the implied ratio; it often names the culprit on sight
  (a ratio of ~1000 is a units slip; ~1.01 smells like an FX convention).
- Same sign, varying size     -> additive error: a component omitted or
  double-counted in one of the two methodologies.
- Mixed signs, mostly exact   -> consistent with retroactive source
  revisions. Rank the largest few for a human glance; do not block.
- Exact match everywhere      -> print the positive signal. Silence should
  be earned, and saying "11 tables clean" once is cheap.

These buckets narrow *where to look*; final attribution still means opening
the source. The point is that whole classes of error get detected every run
by default, instead of depending on someone noticing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

Value = float | int | None

# Tolerances are for float noise and last-digit rounding in published data,
# not for judgment calls.
_EXACT_RTOL = 1e-9
_RATIO_SPREAD = 0.002  # ratios within ±0.2% of their median count as "uniform"
_SIGN_SHARE = 0.85  # share of one sign that suggests an additive error


@dataclass
class DiscrepancyReport:
    kind: str  # "exact" | "multiplicative" | "additive" | "idiosyncratic" | "empty"
    n_compared: int = 0
    n_exact: int = 0
    implied_ratio: float | None = None  # reference ≈ candidate × ratio
    top: list[tuple[str, float, float, float]] = field(default_factory=list)
    # (label, reference, candidate, relative difference), largest first

    def summary(self) -> str:
        if self.kind == "empty":
            return "no overlapping values to compare"
        if self.kind == "exact":
            return f"all {self.n_compared} overlapping values match; pipeline reproduces reference"
        if self.kind == "multiplicative":
            return (
                f"uniform ratio across rows: reference ≈ candidate × {self.implied_ratio:.6g}"
                "; suspect FX rate, units, or scaling"
            )
        if self.kind == "additive":
            return (
                "discrepancies share a sign across most rows"
                "; suspect a component omitted or double-counted"
            )
        return (
            f"{self.n_exact}/{self.n_compared} exact; remaining differences are mixed-sign "
            "and scattered, consistent with retroactive revisions (largest listed)"
        )


def classify(
    pairs: Mapping[str, tuple[Value, Value]],
    *,
    top_n: int = 5,
) -> DiscrepancyReport:
    """Classify how ``candidate`` values disagree with ``reference`` values.

    ``pairs`` maps row label -> (reference, candidate). Labels where either
    side is missing are ignored here; presence differences are a coverage
    question and are reported separately by the benchmark layer, because an
    absence is invisible unless something owns an expected list.
    """
    compared: dict[str, tuple[float, float]] = {
        k: (float(r), float(c))
        for k, (r, c) in pairs.items()
        if r is not None and c is not None
    }
    if not compared:
        return DiscrepancyReport("empty")

    n = len(compared)
    diffs = {k: r - c for k, (r, c) in compared.items()}
    exact = [k for k, (r, c) in compared.items() if abs(r - c) <= _EXACT_RTOL * max(abs(r), abs(c), 1.0)]
    n_exact = len(exact)

    if n_exact == n:
        return DiscrepancyReport("exact", n_compared=n, n_exact=n)

    inexact = {k: v for k, v in compared.items() if k not in set(exact)}

    # Multiplicative: ratios of the non-matching rows cluster tightly around
    # a common value. Requires more than one row of evidence; a single
    # discrepant row is just a discrepant row.
    ratios = sorted(r / c for r, c in inexact.values() if c != 0)
    if len(ratios) == len(inexact) >= 2:
        median = ratios[len(ratios) // 2]
        if median != 0 and all(abs(x / median - 1) <= _RATIO_SPREAD for x in ratios):
            return DiscrepancyReport(
                "multiplicative", n_compared=n, n_exact=n_exact, implied_ratio=median
            )

    def rel(k: str) -> float:
        r, c = compared[k]
        return abs(diffs[k]) / max(abs(r), abs(c))

    top = sorted(
        ((k, compared[k][0], compared[k][1], rel(k)) for k in inexact),
        key=lambda t: t[3],
        reverse=True,
    )[:top_n]

    # Additive: the differences overwhelmingly share a sign.
    signs = [1 if d > 0 else -1 for d in (diffs[k] for k in inexact)]
    dominant = max(signs.count(1), signs.count(-1)) / len(signs)
    if len(signs) >= 3 and dominant >= _SIGN_SHARE:
        return DiscrepancyReport("additive", n_compared=n, n_exact=n_exact, top=top)

    return DiscrepancyReport("idiosyncratic", n_compared=n, n_exact=n_exact, top=top)
