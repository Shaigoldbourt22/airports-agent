"""Deterministic checks on the scoring and query layer.

These need only the database, so they run on every push. They protect the
part of the system that must never drift: if the same data produces a
different score, that is a bug, not a model quirk.
"""

import pytest

from app import tools

pytestmark = pytest.mark.usefixtures("require_db")

NEW_ENGLAND = ["MA", "RI", "CT", "NH", "VT", "ME"]


def test_scoring_is_reproducible():
    first = tools.rank_expansion_candidates(states=NEW_ENGLAND)
    second = tools.rank_expansion_candidates(states=NEW_ENGLAND)
    assert [(r["iata"], r["score"]) for r in first["ranked"]] == \
           [(r["iata"], r["score"]) for r in second["ranked"]]


def test_weights_sum_to_one():
    assert round(sum(tools.WEIGHTS.values()), 6) == 1.0


def test_score_matches_its_components():
    for row in tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]:
        expected = sum(tools.WEIGHTS[k] * row["components"][k] for k in tools.WEIGHTS)
        assert round(expected, 1) == row["score"]


def test_ranking_is_ordered_and_bounded():
    ranked = tools.rank_expansion_candidates(states=NEW_ENGLAND)["ranked"]
    assert ranked, "no New England airport could be scored"
    scores = [r["score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 100 for s in scores)


def test_airports_missing_inputs_are_reported_not_scored():
    """An airport we cannot score must be named, never silently dropped."""
    result = tools.rank_expansion_candidates(states=NEW_ENGLAND, min_enplanements=0)
    scored = {r["iata"] for r in result["ranked"]}
    dropped = {r["iata"] for r in (result["unscored_missing_data"] or [])}
    assert not scored & dropped


def test_cargo_growth_filters_tiny_bases():
    result = tools.cargo_growth()
    assert all(r["landed_lbs"] >= result["min_lbs"] for r in result["ranked"])
    # The filtered-out airports are still surfaced, so the filter is visible.
    assert all(r["landed_lbs"] < result["min_lbs"]
               for r in result["excluded_small_base"])


def test_longhaul_threshold_is_applied():
    result = tools.route_distance_mix("ANC", threshold_mi=3000)
    assert all(r["distance_mi"] >= 3000 for r in result["routes_over_threshold"])
    for month in result["by_month"]:
        assert month["over_threshold"] <= month["flights"]
        assert 0 <= month["pct"] <= 100


def test_unknown_airport_returns_error_not_exception():
    assert "error" in tools.airport_profile("ZZZ")


def test_compare_reports_airports_it_cannot_find():
    result = tools.compare_airports(["LAX", "ZZZ"])
    assert result["not_in_database"] == ["ZZZ"]


def test_peak_hour_shortfall_is_consistent():
    for hour in tools.peak_hour_demand("SFO")["busiest_hours"]:
        assert hour["shortfall"] == hour["peak_sched_arr"] - hour["peak_actual_arr"]
