from sentinel.discrepancy import classify

COUNTRIES = ["AT", "BE", "DE", "ES", "FR", "IT", "NL", "PL"]
BASE = {c: 100.0 * (i + 1) for i, c in enumerate(COUNTRIES)}


def pairs(reference, candidate):
    return {c: (reference[c], candidate[c]) for c in reference}


def test_exact_reproduction_is_named_as_such():
    report = classify(pairs(BASE, dict(BASE)))
    assert report.kind == "exact"
    assert "reproduces" in report.summary()


def test_small_uniform_ratio_beats_any_magnitude_threshold():
    # The motivating case: a wrong FX-rate convention shifts every row by
    # the same ~1.3%, far under a naive "flag if >2%" rule, but the uniform
    # ratio identifies it instantly, and the implied ratio names the culprit.
    candidate = {c: v / 1.013 for c, v in BASE.items()}
    report = classify(pairs(BASE, candidate))
    assert report.kind == "multiplicative"
    assert abs(report.implied_ratio - 1.013) < 1e-6


def test_units_slip_shows_ratio_of_thousand():
    candidate = {c: v / 1000 for c, v in BASE.items()}
    report = classify(pairs(BASE, candidate))
    assert report.kind == "multiplicative"
    assert abs(report.implied_ratio - 1000) < 1e-6


def test_omitted_component_shows_up_as_shared_sign():
    # Reference includes a component the candidate omitted: every reference
    # value sits above the candidate by a different amount, but the same way.
    candidate = {c: v - (10 + 3 * i) for i, (c, v) in enumerate(BASE.items())}
    report = classify(pairs(BASE, candidate))
    assert report.kind == "additive"


def test_scattered_revisions_stay_calm():
    candidate = dict(BASE)
    candidate["AT"] *= 1.08  # a couple of retroactive revisions,
    candidate["FR"] *= 0.94  # mixed signs, everything else exact
    report = classify(pairs(BASE, candidate))
    assert report.kind == "idiosyncratic"
    assert report.n_exact == len(BASE) - 2
    top_labels = [t[0] for t in report.top]
    assert set(top_labels) == {"AT", "FR"}  # largest movers surface first


def test_single_discrepant_row_is_not_called_multiplicative():
    candidate = dict(BASE)
    candidate["DE"] *= 1.5
    report = classify(pairs(BASE, candidate))
    assert report.kind != "multiplicative"


def test_missing_values_are_not_compared_here():
    # Presence is a coverage question owned by the benchmark layer.
    report = classify({"AT": (100.0, None), "BE": (None, 50.0)})
    assert report.kind == "empty"
