"""Tests for the rule-based recommendation engine."""
import math

import pytest

from src import recommendations as recs

TEEN = {"age_group": "16", "sex": "Female"}


def ids(result):
    return [r.id for r in result.recommendations]


def test_short_sleep_gets_sleep_suggestion_with_priority():
    r = recs.generate_recommendations({**TEEN, "sleep_hours_approx": 5, "active_days": 7, "social_media_code": 3})
    assert ids(r) == ["sleep"]
    assert r.recommendations[0].priority == 1
    assert "8-10 hours" in r.recommendations[0].reason and r.recommendations[0].source == recs.SLEEP_SOURCE


def test_enough_sleep_is_a_strength_not_a_suggestion():
    r = recs.generate_recommendations({**TEEN, "sleep_hours_approx": 8, "active_days": 7, "social_media_code": 2})
    assert ids(r) == []
    assert any("sleep meets" in s for s in r.strengths)


def test_adult_sleep_guideline_is_used_for_18_plus():
    adult = {"age_group": "18 or older", "sleep_hours_approx": 7, "active_days": 7, "social_media_code": 1}
    assert "sleep" not in ids(recs.generate_recommendations(adult))
    assert "sleep" in ids(recs.generate_recommendations({**adult, "age_group": "17"}))


@pytest.mark.parametrize("days, title", [(0, "Add movement you enjoy"), (4, "Build towards daily activity")])
def test_activity_rules(days, title):
    r = recs.generate_recommendations({**TEEN, "active_days": days})
    assert r.recommendations[0].title == title


def test_social_media_rule_only_for_frequent_use():
    assert "social_media" not in ids(recs.generate_recommendations({**TEEN, "social_media_code": 5}))
    hourly = recs.generate_recommendations({**TEEN, "social_media_code": 8})
    assert hourly.recommendations[0].id == "social_media" and hourly.recommendations[0].priority == 1
    assert "association" in hourly.recommendations[0].reason


def test_combined_short_sleep_and_frequent_use_adds_screen_free_tip_once():
    r = recs.generate_recommendations({**TEEN, "sleep_hours_approx": 6, "social_media_code": 7, "active_days": 7})
    sleep = next(x for x in r.recommendations if x.id == "sleep")
    assert "screen-free" in sleep.action
    assert len(ids(r)) == len(set(ids(r)))                     # no duplicates


def test_number_of_suggestions_is_capped_and_prioritised():
    r = recs.generate_recommendations({**TEEN, "sleep_hours_approx": 4, "active_days": 0, "social_media_code": 8},
                                      max_items=2)
    assert len(r.recommendations) == 2 and r.more_available == 1
    assert all(x.priority == 1 for x in r.recommendations)


@pytest.mark.parametrize("bad", [None, "abc", 99, -1, 2.5, math.nan])
def test_missing_or_invalid_inputs_never_crash(bad):
    r = recs.generate_recommendations({"sleep_hours_approx": bad, "active_days": bad, "social_media_code": bad})
    assert r.recommendations == [] and len(r.not_used) == 3
    assert r.support_note


def test_empty_profile_and_language_rules():
    assert recs.generate_recommendations({}).recommendations == []
    r = recs.generate_recommendations({**TEEN, "sleep_hours_approx": 4, "active_days": 0, "social_media_code": 8})
    text = " ".join(f"{x.title} {x.action} {x.reason}" for x in r.recommendations).lower()
    for banned in ("mentally ill", "depressed", "high-risk", "diagnos", "will reduce", "causes"):
        assert banned not in text
    assert all(x.reason and x.indicators for x in r.recommendations)
