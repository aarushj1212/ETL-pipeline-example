"""pipeline-sentinel: a validation layer for pipelines whose scariest failure
mode is a plausible number that is wrong.

Four small tools, each born from a real silent failure:

- ``landmarks``: locate data by what stays constant, never by coordinates
- ``tolerance``: judge each series against its own history, not a flat threshold
- ``discrepancy``: classify disagreements by *pattern*, not magnitude
- ``benchmark``: reproduce yesterday before trusting today

See ``docs/design-principles.md`` for the reasoning behind each.
"""

from sentinel.landmarks import LabelMap, find_header_row, normalize_label
from sentinel.tolerance import Flag, flag_series, flag_table
from sentinel.discrepancy import DiscrepancyReport, classify
from sentinel.benchmark import BenchmarkResult, run_benchmark

__all__ = [
    "LabelMap",
    "find_header_row",
    "normalize_label",
    "Flag",
    "flag_series",
    "flag_table",
    "DiscrepancyReport",
    "classify",
    "BenchmarkResult",
    "run_benchmark",
]
