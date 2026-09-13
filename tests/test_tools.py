"""Deterministic checks on the scoring and query layer.

These run against a fixture database with known values, so they assert exact
numbers rather than whatever the last ETL run happened to produce, and they
run anywhere without network access or an API key.

This is the part of the system that must never drift: the same data has to
produce the same score, and an airport we cannot score must be reported rather
than quietly dropped.
"""

import pytest

from app import tools

pytestmark = pytest.mark.usefixtures("fixture_data")

NEW_ENGLAND = ["MA", "RI", "CT", "NH", "VT", "ME"]


def test_weights_sum_to_one():
    assert round(sum(tools.WEIGHTS.values()), 6) == 1.0


def test_ranking_is_stable_and_correct():
    """BIG wins: the heaviest load per runway and parallels 800 ft apart."""
    ranked = tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]
    assert [row["iata"] for row in ranked] == ["BIG", "GRW", "FLT", "TNY", "CGO"]
    assert ranked[0]["components"]["load"] == 100.0
    assert ranked[0]["components"]["growth"] == 0.0
    assert ranked[0]["components"]["spacing"] == 100.0


def test_catchment_is_scored_independently_of_load():
    """GRW has the fastest-growing metro but far from the heaviest load.

    This is the disagreement the component exists to surface: an airline
    schedule and a population trend answer different questions.
    """
    rows = {r["iata"]: r["components"]
            for r in tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]}
    assert rows["GRW"]["catchment"] == 100.0
    assert rows["GRW"]["load"] < rows["BIG"]["load"]


def test_airport_without_catchment_is_reported():
    """NRW has no metro row, so it must surface as unscored with the reason."""
    result = tools.rank_expansion_candidates(states=NEW_ENGLAND, min_enplanements=0)
    unscored = {r["iata"]: r["missing"] for r in result["unscored_missing_data"]}
    assert "NRW" in unscored
    assert "metro population growth" in unscored["NRW"]


def test_spacing_follows_the_faa_thresholds():
    """Parallels under 1,200 ft are worked as one runway; under 2,500 ft lose
    independent approaches. Airports without parallels are not constrained."""
    assert tools._spacing_penalty(800) == 100.0
    assert tools._spacing_penalty(2000) == 60.0
    assert tools._spacing_penalty(4300) == 0.0
    assert tools._spacing_penalty(None) == 0.0


def test_scoring_is_reproducible():
    first = tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]
    second = tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]
    assert [(r["iata"], r["score"]) for r in first] == \
           [(r["iata"], r["score"]) for r in second]


def test_score_matches_its_components():
    for row in tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]:
        expected = sum(tools.WEIGHTS[k] * row["components"][k] for k in tools.WEIGHTS)
        assert round(expected, 1) == row["score"]


def test_scores_are_bounded_and_ordered():
    scores = [r["score"] for r in
              tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)


def test_airport_missing_inputs_is_reported_not_scored():
    """NRW has no runway count, so it must surface as unscored, not vanish."""
    result = tools.rank_expansion_candidates(states=NEW_ENGLAND, min_enplanements=0)
    assert "NRW" not in {r["iata"] for r in result["ranked"]}
    assert "NRW" in {r["iata"] for r in result["unscored_missing_data"]}


def test_ranking_is_relative_to_the_group_given():
    """Dropping the leader rescales the rest, so scores are peer-relative."""
    with_big = tools.rank_expansion_candidates(iatas=["BIG", "GRW", "TNY"])["ranked"]
    without = tools.rank_expansion_candidates(iatas=["GRW", "TNY"])["ranked"]
    grw_with = next(r["score"] for r in with_big if r["iata"] == "GRW")
    grw_without = next(r["score"] for r in without if r["iata"] == "GRW")
    assert grw_with != grw_without


def test_cargo_growth_filters_tiny_bases():
    """TNY tripled its cargo, but on 30,000 lbs, so it must not lead."""
    result = tools.cargo_growth()
    assert result["ranked"][0]["iata"] == "CGO"
    assert "TNY" not in {r["iata"] for r in result["ranked"]}
    assert "TNY" in {r["iata"] for r in result["excluded_small_base"]}
    assert all(r["landed_lbs"] >= result["min_lbs"] for r in result["ranked"])


def test_cargo_growth_reports_decline():
    assert "BIG" in {r["iata"] for r in tools.cargo_growth()["declining"]}


def test_longhaul_threshold_is_applied():
    result = tools.route_distance_mix("BIG", threshold_mi=3000)
    assert {r["dest"] for r in result["routes_over_threshold"]} == {"FAR"}
    by_month = {(m["year"], m["month"]): m for m in result["by_month"]}
    # June: 300 of 1,700 departures clear the threshold.
    assert by_month[(2026, 6)]["pct"] == 17.6
    # July: only the long route flew, so every departure clears it.
    assert by_month[(2026, 7)]["pct"] == 100.0


def test_threshold_is_a_parameter_not_a_constant():
    low = tools.route_distance_mix("BIG", threshold_mi=1000)["routes_over_threshold"]
    high = tools.route_distance_mix("BIG", threshold_mi=3000)["routes_over_threshold"]
    assert len(low) > len(high)


def test_delay_rates_are_computed_per_month():
    months = {m["month"]: m for m in tools.traffic_and_delays("BIG")["months"]}
    assert months[6]["dep_delay_pct"] == 20.0      # 2,000 of 10,000
    assert months[7]["dep_delay_pct"] == 30.0      # 3,600 of 12,000
    assert months[7]["avg_dep_delay_min"] == 50.0  # 180,000 min over 3,600 flights


def test_comparison_normalises_for_size():
    """The big airport carries more per runway despite having more runways."""
    rows = {r["iata"]: r for r in tools.compare_airports(["BIG", "GRW"])["airports"]}
    assert rows["BIG"]["dep_per_runway"] > rows["GRW"]["dep_per_runway"]
    assert rows["BIG"]["dep_delay_pct"] > rows["GRW"]["dep_delay_pct"]


def test_peak_hour_shortfall_and_constraint():
    result = tools.peak_hour_demand("BIG")
    busiest = result["busiest_hours"][0]
    assert busiest["hour"] == 8
    assert busiest["shortfall"] == 12          # 50 scheduled, 38 delivered
    assert "800 ft" in result["capacity_constraint"]
    assert "one runway" in result["capacity_constraint"]


def test_wide_spacing_is_not_reported_as_a_constraint():
    constraint = tools.peak_hour_demand("GRW")["capacity_constraint"]
    assert "independent approaches" in constraint


def test_unknown_airport_returns_error_not_exception():
    assert "error" in tools.airport_profile("ZZZ")


def test_compare_reports_airports_it_cannot_find():
    result = tools.compare_airports(["BIG", "ZZZ"])
    assert result["not_in_database"] == ["ZZZ"]


def test_coverage_describes_what_is_loaded():
    coverage = tools.data_coverage()
    assert coverage["flight_months"] == 2
    assert "bts_ontime" in coverage["sources"]
