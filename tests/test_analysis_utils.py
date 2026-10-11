"""Tests for src/analysis_utils.py: hand-checkable values and edge cases."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src import analysis_utils as au


def test_weighted_share_hand_calculation():
    flag = pd.Series([1, 0, 1, pd.NA], dtype="Int8")
    w = pd.Series([1.0, 1.0, 2.0, 5.0])
    pct, lo, hi, n = au.weighted_share(flag, w)
    assert n == 3                                   # missing answer excluded
    assert pct == pytest.approx(75.0)               # (1 + 2) / (1 + 1 + 2)
    assert 0 <= lo <= pct <= hi <= 100


def test_unweighted_share_is_plain_mean():
    flag = pd.Series([1, 0, 0, 1, 1])
    assert au.weighted_share(flag, pd.Series(1.0, index=flag.index))[0] == pytest.approx(60.0)


def test_empty_inputs_do_not_crash():
    empty = pd.DataFrame({"g": pd.Series(dtype=float), "f": pd.Series(dtype=float),
                          "weight": pd.Series(dtype=float)})
    assert au.weighted_share(empty["f"], empty["weight"])[3] == 0
    assert au.weighted_share_by(empty, "g", "f").empty
    assert au.weighted_distribution(empty, "g").empty
    assert au.weighted_crosstab(empty, "g", "f").empty
    assert np.isnan(au.weighted_mean(empty["f"], empty["weight"]))
    assert au.weighted_median_category(empty, "g") is None
    assert np.isnan(au.spearman(empty, "g", "f")["statistic"])
    assert np.isnan(au.chi_square(empty, "g", "f")["statistic"])


def test_distribution_and_crosstab_sum_to_100():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"a": rng.integers(1, 4, 200), "b": rng.integers(1, 5, 200),
                       "weight": rng.uniform(0.5, 2, 200)})
    assert au.weighted_distribution(df, "a")["percent"].sum() == pytest.approx(100)
    ct = au.weighted_crosstab(df, "a", "b")
    assert ct.groupby("a")["percent"].sum().to_numpy() == pytest.approx([100, 100, 100])


def test_weighted_mean_and_median_category():
    df = pd.DataFrame({"x": [1, 2, 3], "weight": [1.0, 1.0, 2.0]})
    assert au.weighted_mean(df["x"], df["weight"]) == pytest.approx(2.25)
    assert au.weighted_median_category(df, "x") == 2      # cumulative 25%, 50% -> 2


def test_spearman_matches_scipy_and_extremes():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10], "z": [5, 3, 4, 1, 2]})
    assert au.spearman(df, "x", "y")["statistic"] == pytest.approx(1.0)
    expected = stats.spearmanr(df["x"], df["z"])
    r = au.spearman(df, "x", "z")
    assert r["statistic"] == pytest.approx(expected.statistic)
    assert r["p_value"] == pytest.approx(expected.pvalue)
    assert r["n"] == 5


def test_chi_square_and_cramers_v():
    df = pd.DataFrame({"a": [0] * 50 + [1] * 50, "b": [0] * 50 + [1] * 50})
    r = au.chi_square(df, "a", "b")
    assert r["effect_size"] == pytest.approx(1.0)
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"a": rng.integers(0, 2, 500), "b": rng.integers(0, 3, 500)})
    chi2, p, dof, _ = stats.chi2_contingency(pd.crosstab(df["a"], df["b"]), correction=False)
    r = au.chi_square(df, "a", "b")
    assert (r["statistic"], r["p_value"], r["dof"]) == (pytest.approx(chi2), pytest.approx(p), dof)
    assert r["effect_size"] == pytest.approx(np.sqrt(chi2 / 500))


def test_mann_whitney_direction_and_effect():
    df = pd.DataFrame({"g": [1] * 5 + [0] * 5, "v": [6, 7, 8, 9, 10, 1, 2, 3, 4, 5]})
    r = au.mann_whitney(df, "v", "g", 1, 0)
    assert r["effect_size"] == pytest.approx(1.0)      # group 1 always higher
    assert au.mann_whitney(df, "v", "g", 0, 1)["effect_size"] == pytest.approx(-1.0)


def test_kruskal_effect_size():
    df = pd.DataFrame({"g": ["a"] * 20 + ["b"] * 20, "v": list(range(20)) + list(range(20, 40))})
    r = au.kruskal(df, "v", "g")
    h = stats.kruskal(range(20), range(20, 40)).statistic
    assert r["statistic"] == pytest.approx(h)
    assert r["effect_size"] == pytest.approx((h - 1) / (40 - 2))


def test_is_level_treats_missing_as_false():
    s = pd.Series([1, pd.NA, 0], dtype="Int8")
    assert au.is_level(s, 1).tolist() == [True, False, False]


def test_linear_trend_recovers_line():
    x = pd.Series([1, 2, 3, 4.0])
    slope, intercept = au.weighted_linear_trend(x, 2 * x + 1, pd.Series([1.0, 2, 3, 4]))
    assert (slope, intercept) == (pytest.approx(2.0), pytest.approx(1.0))


def test_association_phrase_never_overstates_negligible_effects():
    base = {"effect_name": "Spearman rho"}
    weak = au.association_phrase({**base, "effect_size": -0.07, "effect": "negligible"}, "X", "Y", "up", "down")
    assert weak == "X shows only a negligible association with Y (Spearman rho = -0.07)."
    strong = au.association_phrase({**base, "effect_size": -0.2, "effect": "small"}, "X", "Y", "up", "down")
    assert strong == "X goes with down (small association, Spearman rho = -0.20)."
    assert "could not be computed" in au.association_phrase({**base, "effect_size": np.nan, "effect": "n/a"},
                                                            "X", "Y", "up", "down")


def test_effect_labels():
    assert [au.effect_label(v) for v in (0.05, -0.2, 0.4, 0.7)] == ["negligible", "small", "moderate", "large"]
