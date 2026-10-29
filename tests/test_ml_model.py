"""Tests for src/ml_model.py. Training tests use the synthetic fixture (temporary folder) only."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src import data_processing as dp
from src import ml_model as ml
from tests.conftest import PROJECT_ROOT

REAL_DATA = PROJECT_ROOT / "data" / "processed" / "cleaned_data.csv"


# ---- The project's real dataset (read only) --------------------------------------------
@pytest.mark.skipif(not REAL_DATA.exists(), reason="real cleaned dataset not present")
def test_existing_cleaned_dataset_loads_and_supports_the_target():
    df = ml.load_training_data(REAL_DATA)
    report = ml.validate_training_data(df)
    assert set(ml.FEATURES + [ml.TARGET]) <= set(df.columns)
    assert report["class_counts"].keys() == {"0", "1"}
    assert report["rows_used"] + report["rows_missing_target"] + report["rows_invalid_target"] == len(df)
    # the target is exactly the documented recode of Q84
    labelled = df[df[ml.TARGET].notna()]
    assert (labelled[ml.TARGET] == labelled["poor_mh_code"].isin([4, 5]).astype(int)).all()


# ---- Validation and preparation ------------------------------------------------------------
def test_missing_columns_are_reported(built_dataset):
    df = built_dataset[0].drop(columns=["sleep_hours_approx"])
    with pytest.raises(dp.MissingColumnsError, match="sleep_hours_approx"):
        ml.validate_training_data(df)


def test_missing_and_invalid_targets_are_excluded_not_treated_as_zero(built_dataset):
    df = built_dataset[0].copy()
    df[ml.TARGET] = df[ml.TARGET].astype("Float64")
    df.loc[df.index[:5], ml.TARGET] = 2          # invalid code
    report = ml.validate_training_data(df)
    X, y, _ = ml.prepare_xy(df)
    assert report["rows_invalid_target"] == 5
    assert len(X) == report["rows_used"] == int(df[ml.TARGET].isin([0, 1]).sum())
    assert set(y.unique()) <= {0, 1}
    assert not set(df.index[df[ml.TARGET].isna()]) & set(X.index)   # missing targets dropped


def test_one_class_target_is_rejected(built_dataset):
    df = built_dataset[0].copy()
    df[ml.TARGET] = 0
    with pytest.raises(ml.ModelError, match="only one class"):
        ml.validate_training_data(df)


def test_target_and_outcome_columns_are_not_inputs():
    assert ml.TARGET not in ml.FEATURES
    assert not ml.LEAKAGE_COLUMNS & set(ml.FEATURES)
    assert set(ml.EXCLUDED_COLUMNS) | set(ml.FEATURES) | {ml.TARGET} == set(dp.CLEANED_COLUMNS)


def test_split_is_disjoint_reproducible_and_stratified(built_dataset):
    X, y, _ = ml.prepare_xy(built_dataset[0])
    X_tr, X_te, y_tr, y_te = ml.split_data(X, y)
    X_tr2, X_te2, _, _ = ml.split_data(X, y)
    assert not set(X_tr.index) & set(X_te.index)
    assert len(X_tr) + len(X_te) == len(X)
    assert abs(len(X_te) / len(X) - ml.TEST_SIZE) < 0.01
    assert X_te.index.equals(X_te2.index)                       # fixed seed
    assert abs(y_tr.mean() - y_te.mean()) < 0.02                 # stratified


def test_imputation_is_learned_from_training_data_only(built_dataset):
    X, y, _ = ml.prepare_xy(built_dataset[0])
    X_tr, X_te, y_tr, _ = ml.split_data(X, y)
    X_tr = X_tr.copy()
    X_tr.loc[X_tr.index[:200], "sleep_hours_approx"] = 10.0     # make train and full-data medians differ
    pipe = ml.build_pipeline("logistic_regression").fit(X_tr, y_tr)
    imputer = pipe.named_steps["prep"].named_transformers_["numeric"].named_steps["impute"]
    assert list(imputer.statistics_) == list(X_tr[ml.NUMERIC_FEATURES].median())
    assert list(pipe.feature_names_in_) == ml.FEATURES


# ---- Training, evaluation, persistence ----------------------------------------------------
def test_training_completes_and_records_metadata(trained_model):
    meta = trained_model["metadata"]
    assert meta["model_kind"] in ml.MODEL_NAMES
    assert 0 < meta["threshold"]["value"] < 1
    assert meta["split"]["n_train"] + meta["split"]["n_test"] == meta["dataset"]["rows_used"]
    for m in meta["test_metrics"].values():
        assert 0 <= m["accuracy"] <= 1 and 0 <= m["roc_auc"] <= 1
        assert np.array(m["confusion_matrix"]).sum() == meta["split"]["n_test"]
    assert {r["feature"] for r in meta["permutation_importance"]["features"]} == set(ml.FEATURES)
    json.dumps(meta)                                            # serialisable
    assert ":\\" not in json.dumps(meta["dataset"]) and not meta["dataset"]["path"].startswith("/")


def test_single_class_test_set_is_handled(trained_model):
    X_te, y_te = trained_model["X_test"], trained_model["y_test"]
    only_zeros = y_te[y_te == 0]
    out = ml.evaluate_on_test(trained_model["model"], X_te.loc[only_zeros.index], only_zeros, 0.5)
    assert out["roc_auc"] is None and out["roc_curve"] is None and "only one class" in out["note"]


def test_predictions_have_expected_format(trained_model):
    model, meta = ml.load_model()
    res = ml.predict(model, meta, {"social_media_code": 6, "sleep_hours_approx": 7, "active_days": 3,
                                   "age_group": "16", "sex": "Female"})
    assert set(res) >= {"probability", "threshold", "predicted_class", "not_answered"}
    assert 0.0 <= res["probability"] <= 1.0 and res["predicted_class"] in (0, 1)
    assert res["predicted_class"] == int(res["probability"] >= res["threshold"])


def test_missing_inputs_are_imputed_not_rejected(trained_model):
    model, meta = ml.load_model()
    res = ml.predict(model, meta, {"social_media_code": None, "sleep_hours_approx": 6, "active_days": None,
                                   "age_group": "15", "sex": None})
    assert 0.0 <= res["probability"] <= 1.0
    assert len(res["not_answered"]) == 3


@pytest.mark.parametrize("profile, message", [
    ({"sleep_hours_approx": 3}, "not one of the survey's answers"),
    ({"active_days": 2.5}, "not one of the survey's answers"),
    ({"social_media_code": "lots"}, "not a number"),
    ({"sex": "Other"}, "not one of the survey's answers"),
    ({"screen_time_hours": 5}, "Unknown inputs"),
    ({}, "at least one"),
])
def test_invalid_inputs_raise_clear_errors(trained_model, profile, message):
    model, meta = ml.load_model()
    with pytest.raises(ml.InvalidInputError, match=message):
        ml.predict(model, meta, profile)


def test_explanation_matches_what_if_predictions(trained_model):
    model, meta = ml.load_model()
    profile = {"social_media_code": 8, "sleep_hours_approx": 4, "active_days": 0, "age_group": "18 or older",
               "sex": "Female"}
    base = ml.predict(model, meta, profile)["probability"]
    for row in ml.explain_prediction(model, meta, profile):
        alt = dict(profile, **{row["feature"]: meta["reference_profile"][row["feature"]]})
        assert row["difference"] == pytest.approx(base - ml.predict(model, meta, alt)["probability"])


def test_save_and_load_round_trip(trained_model, tmp_path):
    model_path, meta_path = tmp_path / "m.joblib", tmp_path / "m.json"
    ml.save_model(trained_model["model"], trained_model["metadata"], model_path, meta_path)
    loaded, meta = ml.load_model(model_path, meta_path)
    X = trained_model["X_test"].head(50)
    np.testing.assert_allclose(loaded.predict_proba(X), trained_model["model"].predict_proba(X))
    assert meta["model_version"] == ml.MODEL_VERSION


def test_missing_corrupt_or_mismatched_model_files(trained_model, tmp_path):
    with pytest.raises(ml.ModelNotTrainedError, match="--train"):
        ml.load_model(tmp_path / "none.joblib", tmp_path / "none.json")
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"not a model")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(trained_model["metadata"]))
    with pytest.raises(ml.ModelError, match="could not be read"):
        ml.load_model(bad, meta)
    wrong = tmp_path / "wrong.joblib"
    joblib.dump({"model": trained_model["model"], "features": ["something_else"]}, wrong)
    with pytest.raises(ml.ModelError, match="different input features"):
        ml.load_model(wrong, meta)


def test_threshold_and_calibration_helpers():
    y = np.array([0, 0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    assert 0.3 < ml.choose_threshold(y, p) <= 0.8
    assert ml.expected_calibration_error(np.array([0, 1] * 50), np.full(100, 0.5)) == pytest.approx(0.0)


def test_cli_train_and_show(built_dataset, capsys):
    assert ml.main(["--show"]) in (0, 1)          # 1 if not trained yet in this session
    assert ml.main(["--train"]) == 0
    assert "Held-out test metrics" in capsys.readouterr().out
