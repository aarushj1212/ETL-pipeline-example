"""Locate data by what stays constant — never by coordinates.

The failure this module exists to prevent: a parser that reads "data starts
at row 8" works perfectly against the file it was written for, then a later
vintage of the same file gains or loses a header row and the parser silently
scans past the first entries, emitting missing values with no error. A run of
unexpected NAs at the *top* of a table is the signature of a parsing bug, not
a data change — real coverage losses rarely hit exactly the first rows.

Two landmark tools:

- :func:`find_header_row` finds a block by its own header text and fails
  loudly when the landmark is absent, so a layout change becomes a crash at
  the right line instead of a wrong number three sheets downstream.
- :class:`LabelMap` aligns source rows to target rows by *label*, never by
  position. Positional pasting breaks in quiet ways: spacer rows in one file
  but not the other, one table ordering a country block differently, a source
  emitting extra rows the target deliberately omits. Label matching turns all
  of those into explicit "unmatched" lists a human can glance at.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence


class LandmarkError(LookupError):
    """A structural landmark this parser depends on was not found."""


def find_header_row(
    rows: Sequence[Sequence[object]],
    marker: str,
    *,
    column: int | None = None,
) -> int:
    """Return the index of the first row whose text contains ``marker``.

    ``rows`` is any sequence of row sequences (e.g. an openpyxl
    ``ws.iter_rows(values_only=True)`` materialised into a list, or a parsed
    CSV). Matching is case-insensitive and whitespace-tolerant. If ``column``
    is given, only that cell of each row is examined.

    The data block is then ``rows[find_header_row(...) + 1:]`` — derived from
    the file's own content, so extra title rows, a hand-edited working copy,
    or a source adding a disclaimer line all shift the result correctly.

    Raises :class:`LandmarkError` when the marker is absent, because a wrong
    guess here does not fail — it fabricates NAs.
    """
    want = _squash(marker)
    for i, row in enumerate(rows):
        cells = [row[column]] if column is not None else list(row)
        for cell in cells:
            if cell is not None and want in _squash(str(cell)):
                return i
    raise LandmarkError(
        f"Header landmark {marker!r} not found in {len(rows)} rows. "
        "The source layout has probably changed — inspect the file before "
        "trusting any output derived from it."
    )


_PARENS = re.compile(r"\((.*?)\)")
_WS = re.compile(r"\s+")
# Footnote markers: daggers, asterisks, and SUPERSCRIPT digits — removed
# before NFKC normalisation, which would otherwise turn ¹ into a plain 1.
# Plain trailing digits are deliberately kept: "EU 27" ends in a number that
# means something, and no regex can tell it apart from a footnote. That
# residual ambiguity is resolved by declared aliases, not by guessing.
_FOOTNOTES = str.maketrans("", "", "*†‡¹²³⁴⁵⁶⁷⁸⁹⁰")


def _squash(s: str) -> str:
    return _WS.sub(" ", s).strip().casefold()


def normalize_label(label: str) -> str:
    """Reduce a row label to a canonical comparison key.

    Handles the differences that legitimately occur between a source's label
    and a target's label for the same entity: case, stray whitespace,
    unicode variants, superscript footnote markers ("France¹"), and
    parenthesised qualifiers written inconsistently ("EU 27" vs "EU (27)").
    """
    s = label.translate(_FOOTNOTES)
    s = unicodedata.normalize("NFKC", s)
    s = _PARENS.sub(r" \1 ", s)  # "EU (27)" -> "EU 27"
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    return _squash(s)


@dataclass
class Alignment:
    """Result of matching source labels onto target labels."""

    matched: dict[str, str] = field(default_factory=dict)  # target label -> source label
    unmatched_target: list[str] = field(default_factory=list)  # in target, no source row
    unmatched_source: list[str] = field(default_factory=list)  # in source, no target row

    @property
    def clean(self) -> bool:
        return not self.unmatched_target and not self.unmatched_source


class LabelMap:
    """Alignment of source rows to target rows by normalised label.

    ``aliases`` maps a source spelling to the target spelling for entities
    whose names differ beyond mechanical normalisation (ISO codes vs names,
    "Korea" vs "Korea, Rep."). Aliases are *declared*, not guessed: fuzzy
    matching is exactly the kind of silent judgment call this library
    refuses to make on the human's behalf.
    """

    def __init__(self, target_labels: Iterable[str], *, aliases: Mapping[str, str] | None = None):
        self._targets = list(target_labels)
        self._index = {normalize_label(t): t for t in self._targets}
        if len(self._index) != len(self._targets):
            seen: dict[str, str] = {}
            for t in self._targets:
                key = normalize_label(t)
                if key in seen:
                    raise LandmarkError(
                        f"Target labels {seen[key]!r} and {t!r} normalise to the same "
                        f"key {key!r}; label matching would be ambiguous."
                    )
                seen[key] = t
        self._aliases = {normalize_label(k): normalize_label(v) for k, v in (aliases or {}).items()}

    def match(self, source_label: str) -> str | None:
        """Return the target label for a source label, or None."""
        key = normalize_label(source_label)
        key = self._aliases.get(key, key)
        return self._index.get(key)

    def align(self, source_labels: Iterable[str]) -> Alignment:
        """Match every source label; report leftovers on both sides.

        The unmatched lists are the human's short review list. An unmatched
        *target* label means that row will stay empty — if it had data last
        year, that is a question, not a default. An unmatched *source* label
        may be deliberate scope (rows the target intentionally omits) or a
        renamed entity that needs an alias.
        """
        out = Alignment()
        hit: set[str] = set()
        for s in source_labels:
            t = self.match(s)
            if t is None:
                out.unmatched_source.append(s)
            else:
                out.matched[t] = s
                hit.add(t)
        out.unmatched_target = [t for t in self._targets if t not in hit]
        return out
