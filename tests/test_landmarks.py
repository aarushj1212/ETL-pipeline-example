"""Every test here reenacts a real way positional parsing fails silently."""

import pytest

from sentinel.landmarks import LabelMap, LandmarkError, find_header_row, normalize_label

COUNTRIES = ["Austria", "Belgium", "France", "Germany"]


def make_file(extra_header_rows: int) -> list[list[object]]:
    """A source file whose preamble length varies by vintage."""
    preamble: list[list[object]] = [["Big Statistics Report"], [None]]
    preamble += [[f"hand-typed note {i}"] for i in range(extra_header_rows)]
    header = [["Country", "2024", "2025"]]
    data = [[c, 100.0 + i, 110.0 + i] for i, c in enumerate(COUNTRIES)]
    return preamble + header + data


def test_header_found_regardless_of_preamble_length():
    # The same parser must work on the clean download AND the hand-edited
    # working copy with extra rows typed above the table.
    for extra in (0, 2, 5):
        rows = make_file(extra)
        start = find_header_row(rows, "Country") + 1
        assert [r[0] for r in rows[start : start + len(COUNTRIES)]] == COUNTRIES


def test_hardcoded_row_would_have_failed_silently():
    # The counterfactual: pin the row number learned from the edited copy,
    # run it on the clean file, and the first countries silently vanish.
    edited = make_file(2)
    pinned = find_header_row(edited, "Country") + 1
    clean = make_file(0)
    scanned = [r[0] for r in clean[pinned:]]
    assert "Austria" not in scanned  # the exact silent failure this prevents


def test_missing_landmark_raises():
    with pytest.raises(LandmarkError):
        find_header_row(make_file(0), "This header does not exist")


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("EU 27", "EU (27)"),
        ("  France ", "france"),
        ("Türkiye", "türkiye"),
        ("Italy¹", "Italy"),
        ("Spain*", "Spain"),
        ("Euro area – 19", "Euro area - 19"),
    ],
)
def test_normalize_label_equivalences(a, b):
    assert normalize_label(a) == normalize_label(b)


def test_normalize_label_keeps_meaningful_digits():
    assert normalize_label("EU 27") != normalize_label("EU 28")


def test_align_survives_reordered_source_block():
    # One table ordering a country block differently must not misplace values.
    target = ["Switzerland", "Iceland", "Liechtenstein", "Norway"]
    source = ["Iceland", "Liechtenstein", "Norway", "Switzerland"]  # different order
    alignment = LabelMap(target).align(source)
    assert alignment.clean
    assert alignment.matched["Switzerland"] == "Switzerland"


def test_align_reports_scope_differences_instead_of_forcing_them():
    # Source emits extra countries the target deliberately omits; the target
    # keeps a row the source stopped reporting. Both must surface as lists,
    # not as values landing one row off.
    target = ["Austria", "Belgium", "Total"]
    source = ["Austria", "Belgium", "Australia", "Japan"]
    alignment = LabelMap(target).align(source)
    assert alignment.unmatched_source == ["Australia", "Japan"]
    assert alignment.unmatched_target == ["Total"]


def test_aliases_are_declared_not_guessed():
    label_map = LabelMap(["Korea, Rep.", "Türkiye"], aliases={"Korea": "Korea, Rep."})
    assert label_map.match("Korea") == "Korea, Rep."
    assert label_map.match("South Korea") is None  # no fuzzy guessing, ever


def test_ambiguous_targets_refuse_to_build():
    with pytest.raises(LandmarkError):
        LabelMap(["EU 27", "EU (27)"])  # would normalise to the same key
