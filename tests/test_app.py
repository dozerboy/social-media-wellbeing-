"""Dashboard tests with Streamlit's AppTest: metric values, filters, chart updates, empty data, errors."""
import json

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src import analysis_utils as au
from src import data_processing as dp
from tests.conftest import PROJECT_ROOT

APP = str(PROJECT_ROOT / "app.py")


@pytest.fixture
def app(built_dataset):
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    return at


def metrics(at):
    return {m.label: m.value for m in at.metric}


def expected_cards(df: pd.DataFrame, weighted: bool = True):
    w = df["weight"] if weighted else pd.Series(1.0, index=df.index)

    def share(col):
        ok = df[col].notna()
        return np.average(df.loc[ok, col].astype(float), weights=w[ok]) * 100

    def mean(col):
        ok = df[col].notna()
        return np.average(df.loc[ok, col].astype(float), weights=w[ok])

    return {"Respondents": f"{len(df):,}",
            "Frequent social media use": f"{share('social_media_frequent'):.1f}%",
            "Average sleep": f"{mean('sleep_hours_approx'):.1f} h",
            "Average active days": f"{mean('active_days'):.1f} / 7",
            "Poor mental health": f"{share('poor_mental_health'):.1f}%",
            "Persistent sadness": f"{share('sad_hopeless'):.1f}%"}


def chart_specs(at):
    return [el.proto.spec for el in at.get("plotly_chart")]


def test_metric_cards_match_independent_calculation(app):
    df = dp.load_cleaned_data()
    assert metrics(app) == expected_cards(df)


def test_unweighted_toggle(app):
    app.toggle(key="f_weighted").set_value(False).run()
    assert metrics(app) == expected_cards(dp.load_cleaned_data(), weighted=False)


def test_age_filter_updates_metrics_and_charts(app):
    before = chart_specs(app)
    app.multiselect(key="f_age").set_value(["15"]).run()
    assert not app.exception
    df = dp.load_cleaned_data()
    assert metrics(app) == expected_cards(df[df["age_group"] == "15"])
    after = chart_specs(app)
    assert len(after) == len(before) and after != before


def test_range_filters(app):
    app.slider(key="f_active").set_value((5, 7)).run()
    app.select_slider(key="f_sm").set_value((6, 8)).run()
    app.select_slider(key="f_sleep").set_value((5, 7)).run()
    assert not app.exception
    df = dp.load_cleaned_data()
    sub = df[df["active_days"].between(5, 7).fillna(False) & df["social_media_code"].between(6, 8).fillna(False)
             & df["sleep_code"].between(5, 7).fillna(False)]
    assert metrics(app)["Respondents"] == f"{len(sub):,}"


def test_more_filters_and_reset(app):
    app.multiselect(key="f_sex").set_value(["Female"]).run()
    df = dp.load_cleaned_data()
    assert metrics(app)["Respondents"] == f"{(df['sex'] == 'Female').sum():,}"
    app.button[0].click().run()          # Reset filters
    assert metrics(app)["Respondents"] == f"{len(df):,}"


def test_empty_selection_shows_message(app):
    app.multiselect(key="f_age").set_value([]).run()
    assert not app.exception
    assert any("No students match" in w.value for w in app.warning)
    assert len(app.metric) == 0


def test_tiny_selection_hides_unreliable_groups_without_crashing(app):
    app.multiselect(key="f_race").set_value(["Asian"]).run()
    app.slider(key="f_active").set_value((7, 7)).run()
    app.multiselect(key="f_age").set_value(["18 or older"]).run()
    assert not app.exception


def test_unsupported_variables_are_flagged_not_faked(app):
    infos = " ".join(i.value for i in app.info)
    for phrase in ("Screen-time distribution", "Nighttime social media use", "anxiety"):
        assert phrase in infos
    labels = metrics(app)
    assert not any("screen" in k.lower() or "anxiety" in k.lower() for k in labels)


def test_insights_are_computed_from_data(app):
    df = dp.load_cleaned_data()
    pct = au.weighted_share(df["social_media_frequent"], df["weight"])[0]
    text = " ".join(m.value for m in app.markdown)
    assert f"<b>{pct:.1f}%</b> of students in this selection" in text
    rho = au.spearman(df, "social_media_code", "sleep_hours_approx")
    assert f"rho = {rho['statistic']:.2f}" in text


def test_statistics_table_matches_analysis_utils(app):
    df = dp.load_cleaned_data()
    table = [d.value for d in app.dataframe if "Comparison" in d.value.columns][0]
    row = table[table["Comparison"].str.startswith("Social media freq. ↔ sleep")].iloc[0]
    r = au.spearman(df, "social_media_code", "sleep_hours_approx")
    assert row["n"] == r["n"] and row["Effect size"] == f"{r['statistic']:.3f}"


def test_missing_dataset_shows_clear_error(built_dataset, tmp_path, monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(dp, "CLEANED_CSV_FILE", tmp_path / "none.csv")
    monkeypatch.setattr(dp, "RAW_DAT_FILE", tmp_path / "none.dat")
    monkeypatch.setattr(dp, "INTERIM_CSV_FILE", tmp_path / "none_interim.csv")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("could not be loaded" in e.value for e in at.error)
    assert any("download" in c.value.lower() for c in at.code)
    st.cache_data.clear()
