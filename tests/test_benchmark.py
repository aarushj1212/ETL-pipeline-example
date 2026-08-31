from sentinel.benchmark import run_benchmark

REFERENCE = {
    "Austria": 120.0,
    "Belgium": 250.0,
    "France": 900.0,
    "Poland": 80.0,
    "Korea, Rep.": 300.0,
}


def test_clean_run_costs_one_line():
    result = run_benchmark(lambda period: dict(REFERENCE), REFERENCE, "2024")
    assert result.clean
    lines = result.lines()
    assert len(lines) == 1 and "clean" in lines[0]


def test_pipeline_bug_produces_structure():
    # A wrong unit in the extraction path: the benchmark year catches it
    # before the new year inherits it.
    result = run_benchmark(
        lambda period: {k: v * 1000 for k, v in REFERENCE.items()}, REFERENCE, "2024"
    )
    assert not result.clean
    assert result.report.kind == "multiplicative"


def test_dropped_reporter_becomes_a_question():
    extracted = {k: (None if k == "Poland" else v) for k, v in REFERENCE.items()}
    result = run_benchmark(lambda period: extracted, REFERENCE, "2024")
    assert result.dropped == ["Poland"]
    assert any("Poland" in line and "confirm" in line for line in result.lines())


def test_alias_bridges_source_naming():
    extracted = dict(REFERENCE)
    extracted["Korea"] = extracted.pop("Korea, Rep.")
    aliased = run_benchmark(
        lambda period: extracted, REFERENCE, "2024", aliases={"Korea": "Korea, Rep."}
    )
    assert aliased.clean

    unaliased = run_benchmark(lambda period: extracted, REFERENCE, "2024")
    assert unaliased.unmatched_extracted == ["Korea"]
    assert "Korea, Rep." in unaliased.unmatched_reference


def test_same_extractor_serves_benchmark_and_new_year():
    # The value of the benchmark is that it exercises the identical code
    # path. This test just documents the contract: extract takes a period.
    calls = []

    def extract(period):
        calls.append(period)
        return dict(REFERENCE)

    run_benchmark(extract, REFERENCE, "2024")
    assert calls == ["2024"]
