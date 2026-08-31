from sentinel.tolerance import flag_series, flag_table

# A stable series: drifts a few percent a year.
STABLE = [100, 103, 101, 105, 108, 106, 110, 113, 111, 115, 118, 117]
# A volatile series: routinely swings by half.
VOLATILE = [100, 160, 90, 150, 70, 130, 60, 120, 55, 110, 50, 100]


def test_same_move_is_judged_by_each_series_own_history():
    # +20% is an event for the stable row and a Tuesday for the volatile one.
    # This is the whole argument against a single flat threshold.
    stable_flag = flag_series("stable", STABLE, STABLE[-1] * 1.20)
    volatile_flag = flag_series("volatile", VOLATILE, VOLATILE[-1] * 1.20)
    assert stable_flag is not None and stable_flag.reason == "outlier"
    assert volatile_flag is None


def test_short_history_falls_back_to_flat_band():
    # Two observations cannot support a σ estimate; trusting one would just
    # be noise wearing a lab coat.
    flag = flag_series("young", [100, 104], 140, min_history=8, fallback_pct=0.25)
    assert flag is not None
    assert "flat" in flag.basis


def test_presence_transitions_always_flag():
    went = flag_series("row", STABLE, None)
    came = flag_series("row", [None, None, None], 42)
    assert went is not None and went.reason == "went_missing"
    assert came is not None and came.reason == "reappeared"


def test_still_missing_is_not_news():
    assert flag_series("row", [None, None], None) is None


def test_gaps_are_not_bridged_into_fake_changes():
    # 100 -> (gap) -> 200 is not a one-year +100% move; treating it as one
    # would poison the σ estimate for every later year.
    with_gap = [100, None, 200, 210, 220, 230, 240, 250, 260, 270]
    flag = flag_series("gappy", with_gap, 285)
    assert flag is None or "+100" not in str(flag)


def test_zero_base_is_skipped_not_divided():
    assert flag_series("zeroed", [0, 0, 0], 50) is None


def test_flag_table_returns_exceptions_only():
    table = {"stable": STABLE, "volatile": VOLATILE}
    clean_new = {"stable": STABLE[-1] * 1.02, "volatile": VOLATILE[-1] * 1.4}
    assert flag_table(table, clean_new) == []

    dirty_new = {"stable": STABLE[-1] * 3, "volatile": VOLATILE[-1] * 1.4}
    flags = flag_table(table, dirty_new)
    assert [f.label for f in flags] == ["stable"]


def test_absent_label_in_new_column_counts_as_missing():
    flags = flag_table({"stable": STABLE}, {})
    assert len(flags) == 1 and flags[0].reason == "went_missing"
