"""Reproduce yesterday before trusting today.

The strongest regression test a data pipeline can have is one it gets for
free: re-extract a period whose answers are already known, through *exactly*
the code path that will produce the new period, and compare. If the pipeline
reproduces the reference, the new numbers inherit that trust; if it does
not, the discrepancy pattern (see :mod:`sentinel.discrepancy`) usually says
why before anyone opens a source file.

Two subtleties that make this workable in practice:

- **Sources revise retroactively**, so a perfect match is not the bar. The
  benchmark validates the *pipeline*, not the values: revisions inject
  idiosyncratic, mixed-sign noise, which the pattern classifier tolerates,
  while pipeline bugs produce structure (uniform ratios, shared signs).
- **The reference embodies a methodology, not the truth.** A flag means
  "these two methodologies differ", not "you are wrong" — the reference may
  carry an inherited error. Which is right is a judgment call that belongs
  to a human, armed with the pattern.

Coverage is checked alongside values. An absence is invisible unless
something owns an expected list, so the benchmark diffs presence against
the reference and reports it as questions: "Poland reported last year and
is missing now — confirm?".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from sentinel.discrepancy import DiscrepancyReport, classify
from sentinel.landmarks import LabelMap

Value = float | int | None


@dataclass
class BenchmarkResult:
    period: str
    report: DiscrepancyReport
    dropped: list[str] = field(default_factory=list)  # reference has data, extraction doesn't
    appeared: list[str] = field(default_factory=list)  # extraction has data, reference doesn't
    unmatched_reference: list[str] = field(default_factory=list)  # label never seen in extraction
    unmatched_extracted: list[str] = field(default_factory=list)  # label unknown to reference

    @property
    def clean(self) -> bool:
        return (
            self.report.kind == "exact"
            and not self.dropped
            and not self.appeared
            and not self.unmatched_reference
            and not self.unmatched_extracted
        )

    def lines(self) -> list[str]:
        """Exceptions-only report.

        A clean run costs one line and one glance. Attention is the scarce
        resource: a wall of per-row confirmations gets rubber-stamped, and a
        rubber-stamped check protects nothing.
        """
        if self.clean:
            return [f"[{self.period}] benchmark clean — {self.report.summary()}"]
        out = [f"[{self.period}] benchmark: {self.report.summary()}"]
        for label, ref, cand, rel in self.report.top:
            out.append(f"    {label}: reference {ref:,.3f} vs pipeline {cand:,.3f} ({rel:+.2%})")
        for label in self.dropped:
            out.append(f"    {label}: reported in reference, missing from extraction — confirm?")
        for label in self.appeared:
            out.append(f"    {label}: missing in reference, extracted now — new reporter or bug?")
        for label in self.unmatched_reference:
            out.append(f"    {label}: reference label never matched by extraction — mapping gap?")
        for label in self.unmatched_extracted:
            out.append(f"    {label}: extracted label unknown to reference — alias needed or out of scope")
        return out


def run_benchmark(
    extract: Callable[[str], Mapping[str, Value]],
    reference: Mapping[str, Value],
    period: str,
    *,
    aliases: Mapping[str, str] | None = None,
) -> BenchmarkResult:
    """Re-extract ``period`` and compare against ``reference`` values.

    ``extract`` is the pipeline's own extraction function — the same
    callable that will be pointed at the new period. Giving the benchmark a
    special-cased extraction path would test the special case, not the
    pipeline.

    Alignment is by label via :class:`~sentinel.landmarks.LabelMap`, never
    by position, so a reordered source block or an extra header row shows up
    as an explicit mapping question instead of values landing one row off.
    """
    extracted = dict(extract(period))
    label_map = LabelMap(reference.keys(), aliases=aliases)
    alignment = label_map.align(extracted.keys())

    pairs: dict[str, tuple[Value, Value]] = {}
    dropped: list[str] = []
    appeared: list[str] = []
    for target, source in alignment.matched.items():
        ref_v, cand_v = reference[target], extracted[source]
        if ref_v is not None and cand_v is None:
            dropped.append(target)
        elif ref_v is None and cand_v is not None:
            appeared.append(target)
        else:
            pairs[target] = (ref_v, cand_v)

    return BenchmarkResult(
        period=period,
        report=classify(pairs),
        dropped=dropped,
        appeared=appeared,
        unmatched_reference=[t for t in alignment.unmatched_target if reference[t] is not None],
        unmatched_extracted=alignment.unmatched_source,
    )
