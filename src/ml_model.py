"""Machine-learning prediction of the survey's poor-mental-health indicator.

The model learns from the project's existing cleaned dataset (data/processed/cleaned_data.csv, built
from the CDC YRBS 2023 file by src/data_processing.py). Nothing here creates or downloads other data.

Workflow (train_and_evaluate):
    1. load cleaned_data.csv and keep students who answered the target question
    2. stratified 80/20 train/test split with a fixed seed, BEFORE any preprocessing is fitted
    3. 5-fold cross-validation on the TRAINING set only -> model selection, decision threshold, calibration check
    4. fit the chosen pipelines on the training set and evaluate once on the untouched test set
    5. save the selected pipeline (models/wellbeing_model.joblib) and its metadata (models/model_metadata.json)

Usage (from the project root):
    python -m src.ml_model --train     # train, evaluate, save
    python -m src.ml_model --show      # print the saved model's summary

The output is a statistical estimate learned from a survey population. It is not a diagnosis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, classification_report,
                             confusion_matrix, f1_score, precision_recall_curve, precision_score, recall_score,
                             roc_auc_score, roc_curve)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from src import data_processing as dp
except ModuleNotFoundError:  # run as "python src/ml_model.py"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src import data_processing as dp

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------------------
MODEL_VERSION = "1.0.0"
RANDOM_SEED = 42
TEST_SIZE = 0.20
CV_FOLDS = 5
SELECTION_TOLERANCE = 0.01      # prefer the interpretable model if its CV ROC-AUC is within this of the best
CALIBRATION_ECE_LIMIT = 0.05    # recalibrate probabilities only if CV calibration error exceeds this

# SMW_MODEL_DIR lets the automated tests use a temporary folder. Normal use never sets it.
MODEL_DIR = Path(os.environ.get("SMW_MODEL_DIR", dp.PROJECT_ROOT / "models"))
MODEL_FILE = MODEL_DIR / "wellbeing_model.joblib"
METADATA_FILE = MODEL_DIR / "model_metadata.json"
TRAIN_COMMAND = "python -m src.ml_model --train"

# --------------------------------------------------------------------------------------
# Target and features (verified against src/data_processing.py and docs/data_dictionary.md)
# --------------------------------------------------------------------------------------
TARGET = "poor_mental_health"
TARGET_DEFINITION = (
    "1 = mental health was 'not good' most of the time or always during the past 30 days "
    "(CDC question Q84, answers 4-5); 0 = never, rarely or sometimes (answers 1-3). Students who did not "
    "answer Q84 have no target value and are left out of training and evaluation, not counted as 0.")

NUMERIC_FEATURES = ["social_media_code", "sleep_hours_approx", "active_days"]
CATEGORICAL_FEATURES = ["age_group", "sex"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

FEATURE_INFO: Dict[str, Dict[str, Any]] = {
    "social_media_code": {
        "label": "Social media use frequency", "source": "Q80", "type": "ordinal (1 = never ... 8 = more than hourly)",
        "options": [[code, label] for code, label in dp.SOCIAL_MEDIA_LABELS.items()]},
    "sleep_hours_approx": {
        "label": "Sleep on an average school night", "source": "Q85",
        "type": "ordinal hours (4 = 4 or less ... 10 = 10 or more)",
        "options": [[dp.SLEEP_HOURS_APPROX[code], label] for code, label in dp.SLEEP_LABELS.items()]},
    "active_days": {
        "label": "Days physically active for 60+ minutes (past 7 days)", "source": "Q76", "type": "count 0-7",
        "options": [[d, f"{d} day" if d == 1 else f"{d} days"] for d in range(8)]},
    "age_group": {"label": "Age group", "source": "Q1", "type": "category",
                  "options": [[g, g] for g in dp.AGE_GROUP_ORDER]},
    "sex": {"label": "Sex", "source": "Q2", "type": "category",
            "options": [[s, s] for s in dp.SEX_LABELS.values()]},
}

# Columns that must never be model inputs: the target itself or another measure of the same outcome.
LEAKAGE_COLUMNS = {TARGET, "poor_mh_code", "poor_mh_frequency", "sad_hopeless", "difficulty_concentrating"}

EXCLUDED_COLUMNS: Dict[str, str] = {
    "poor_mh_code": "the target question itself in another form (target leakage)",
    "poor_mh_frequency": "the target question itself in another form (target leakage)",
    "sad_hopeless": "another mental-health outcome, not a lifestyle input (outcome leakage)",
    "difficulty_concentrating": "another mental-health outcome (outcome leakage); also 31% missing",
    "social_media_freq": "same answer as social_media_code (label form)",
    "social_media_frequent": "coarser yes/no version of social_media_code",
    "sleep_code": "same answer as sleep_hours_approx (code form)",
    "sleep_hours_cat": "same answer as sleep_hours_approx (label form)",
    "sleep_8plus": "coarser yes/no version of sleep_hours_approx",
    "active_5plus": "coarser yes/no version of active_days",
    "age_code": "same answer as age_group (finer codes)",
    "age_label": "same answer as age_group (label form)",
    "grade_code": "almost identical to age (redundant)",
    "grade_label": "almost identical to age (redundant)",
    "race_ethnicity": ("left out by design: a public well-being demo should not ask for race/ethnicity, and "
                       "group-level differences could be misread as personal traits"),
    "weight": "survey-design variable, not a student characteristic",
    "stratum": "survey-design variable, not a student characteristic",
    "psu": "survey-design variable, not a student characteristic",
    "row_id": "record identifier",
}

assert not LEAKAGE_COLUMNS & set(FEATURES), "target leakage: an outcome column is listed as a feature"

MODEL_NAMES = {"logistic_regression": "Logistic Regression", "random_forest": "Random Forest"}

LIMITATIONS = [
    "Trained on US high-school students (about 14-18) surveyed in 2023; it may not apply to college students, "
    "adults or other countries.",
    "The outcome is a single self-reported survey question, not a clinical assessment. The model cannot diagnose "
    "anything.",
    "Associations only: the survey is cross-sectional, so the model shows which answers go together, not causes.",
    "Unweighted: the model describes the survey sample. Survey weights and the clustered design are not used, so "
    "metrics are not national estimates.",
    "Missing answers are imputed inside the pipeline (median or a 'Not answered' category, learned from training "
    "data only); 26% of labelled students skipped the social media question.",
    "Uses only five inputs; most influences on mental health (family, school, health, relationships) are not "
    "measured, so individual estimates are uncertain.",
    "Includes sex and age group, which carry group-level differences; these are not personal faults and the "
    "model must not be used to make decisions about real people.",
]


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------
class ModelError(Exception):
    """Base class for model problems (bad data, unreadable model file, ...)."""


class ModelNotTrainedError(ModelError):
    """No saved model exists yet."""


class InvalidInputError(ModelError, ValueError):
    """A prediction input is outside the dataset's valid answers."""


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
def load_training_data(path: Optional[Path] = None) -> pd.DataFrame:
    """Load the existing cleaned dataset with the project's own loader (raises a clear error if missing)."""
    return dp.load_cleaned_data(Path(path) if path else dp.CLEANED_CSV_FILE)


def validate_training_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Check the required columns and the target coding; return counts of usable and excluded rows."""
    dp.validate_columns(df, FEATURES + [TARGET])
    target = pd.to_numeric(df[TARGET], errors="coerce")
    missing = int(target.isna().sum())
    invalid = int((target.notna() & ~target.isin([0, 1])).sum())
    usable = target.isin([0, 1])
    counts = target[usable].astype(int).value_counts().to_dict()
    report = {"rows_in_dataset": len(df), "rows_missing_target": missing, "rows_invalid_target": invalid,
              "rows_used": int(usable.sum()), "class_counts": {str(k): int(v) for k, v in sorted(counts.items())}}
    if len(counts) < 2:
        raise ModelError(f"The target '{TARGET}' has only one class among usable rows ({counts}); "
                         "a classifier cannot be trained.")
    if min(counts.values()) < 2 * CV_FOLDS or report["rows_used"] < 100:
        raise ModelError(f"Too few usable rows to train and evaluate reliably: {report}.")
    return report


def to_feature_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Put inputs in the exact layout the pipeline expects, for training AND prediction.

    Numbers become floats (NaN = not answered); categories become plain text (NaN = not answered).
    """
    out = pd.DataFrame(index=data.index)
    for col in NUMERIC_FEATURES:
        out[col] = pd.to_numeric(data[col], errors="coerce").astype(float)
    for col in CATEGORICAL_FEATURES:
        values = data[col].astype(object)
        out[col] = values.where(pd.notna(values), np.nan)
    return out[FEATURES]


def prepare_xy(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, Dict[str, Any]]:
    """Features X and labels y for students with a valid target (missing/invalid targets are dropped)."""
    report = validate_training_data(df)
    target = pd.to_numeric(df[TARGET], errors="coerce")
    usable = target.isin([0, 1])
    return to_feature_frame(df.loc[usable]), target[usable].astype(int), report


def split_data(X: pd.DataFrame, y: pd.Series):
    """Reproducible train/test split, stratified so both sets keep the same class balance."""
    stratify = y if y.value_counts().min() >= 2 else None
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=stratify)


# --------------------------------------------------------------------------------------
# Pipelines
# --------------------------------------------------------------------------------------
def build_preprocessor(scale_numeric: bool) -> ColumnTransformer:
    """Imputation and encoding. Every statistic (medians, categories) is learned when the pipeline is fitted,
    i.e. from training data only."""
    numeric_steps = [("impute", SimpleImputer(strategy="median", add_indicator=True))]  # + 'was missing' flags
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="Not answered")),
        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([("numeric", Pipeline(numeric_steps), NUMERIC_FEATURES),
                              ("categorical", categorical, CATEGORICAL_FEATURES)],
                             verbose_feature_names_out=False)


def build_pipeline(kind: str) -> Pipeline:
    """'logistic_regression' (scaled, interpretable baseline) or 'random_forest' (nonlinear comparison).

    No class weights: the positive class is about 31%, a moderate imbalance. Unweighted models keep their
    probabilities interpretable, and the imbalance is handled by choosing the decision threshold instead.
    """
    if kind == "logistic_regression":
        return Pipeline([("prep", build_preprocessor(scale_numeric=True)),
                         ("model", LogisticRegression(max_iter=2000))])
    if kind == "random_forest":
        return Pipeline([("prep", build_preprocessor(scale_numeric=False)),
                         ("model", RandomForestClassifier(n_estimators=300, min_samples_leaf=25,
                                                          max_features="sqrt", random_state=RANDOM_SEED,
                                                          n_jobs=-1))])
    raise ValueError(f"Unknown model kind '{kind}'. Choose one of {list(MODEL_NAMES)}.")


# --------------------------------------------------------------------------------------
# Evaluation helpers
# --------------------------------------------------------------------------------------
def _cv() -> StratifiedKFold:
    return StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Average gap between predicted probability and observed rate, over equal-width probability bins."""
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        mask = bins == b
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(total)


def choose_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Threshold that maximises F1 on out-of-fold TRAINING predictions (ties -> closest to 0.5).

    F1 balances missed cases (false negatives) and false alarms (false positives); a plain 0.5 cut-off
    would flag very few students because the positive class is the minority.
    """
    grid = np.round(np.arange(0.05, 0.951, 0.01), 2)
    scores = np.array([f1_score(y, (p >= t).astype(int), zero_division=0) for t in grid])
    best = np.flatnonzero(scores == scores.max())
    return float(grid[best[np.argmin(np.abs(grid[best] - 0.5))]])


def _downsample(*arrays: np.ndarray, max_points: int = 200) -> List[List[float]]:
    n = len(arrays[0])
    idx = np.unique(np.linspace(0, n - 1, min(n, max_points)).round().astype(int))
    return [np.asarray(a)[idx].round(4).tolist() for a in arrays]


def cross_validate_models(X_train: pd.DataFrame, y_train: pd.Series) -> Dict[str, Dict[str, Any]]:
    """Out-of-fold probabilities for each candidate model (training data only)."""
    results = {}
    for kind in MODEL_NAMES:
        oof = cross_val_predict(build_pipeline(kind), X_train, y_train, cv=_cv(), method="predict_proba")[:, 1]
        results[kind] = {"oof": oof,
                         "roc_auc": float(roc_auc_score(y_train, oof)),
                         "average_precision": float(average_precision_score(y_train, oof)),
                         "brier": float(brier_score_loss(y_train, oof)),
                         "ece": expected_calibration_error(y_train, oof)}
    return results


def select_model(cv_results: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    """Highest cross-validated ROC-AUC; Logistic Regression wins ties within SELECTION_TOLERANCE."""
    best = max(cv_results, key=lambda k: cv_results[k]["roc_auc"])
    lr = "logistic_regression"
    if best != lr and cv_results[lr]["roc_auc"] >= cv_results[best]["roc_auc"] - SELECTION_TOLERANCE:
        return lr, (f"Random Forest's cross-validated ROC-AUC ({cv_results[best]['roc_auc']:.3f}) is within "
                    f"{SELECTION_TOLERANCE} of Logistic Regression's ({cv_results[lr]['roc_auc']:.3f}), so the "
                    "simpler, interpretable Logistic Regression is preferred.")
    other = "random_forest" if best == lr else lr
    return best, (f"{MODEL_NAMES[best]} has the highest cross-validated ROC-AUC on the training set "
                  f"({cv_results[best]['roc_auc']:.3f} vs {cv_results[other]['roc_auc']:.3f} for "
                  f"{MODEL_NAMES[other]}).")


def evaluate_on_test(model, X_test: pd.DataFrame, y_test: pd.Series, threshold: float) -> Dict[str, Any]:
    """All held-out metrics. ROC/PR quantities are skipped (None) if the test set has only one class."""
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    out: Dict[str, Any] = {
        "n_test": int(len(y_test)), "threshold": threshold,
        "accuracy": float(accuracy_score(y_test, pred)),
        "precision": float(precision_score(y_test, pred, zero_division=0)),
        "recall": float(recall_score(y_test, pred, zero_division=0)),
        "f1": float(f1_score(y_test, pred, zero_division=0)),
        "brier": float(brier_score_loss(y_test, proba)),
        "predicted_positive_rate": float(pred.mean()),
        "observed_positive_rate": float(np.mean(y_test)),
        "confusion_matrix": confusion_matrix(y_test, pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y_test, pred, labels=[0, 1], target_names=["0 (not poor)", "1 (poor)"], output_dict=True,
            zero_division=0),
        "roc_auc": None, "average_precision": None, "roc_curve": None, "pr_curve": None,
        "calibration_curve": None, "note": "",
    }
    if len(np.unique(y_test)) < 2:
        out["note"] = ("The test set contains only one class, so ROC-AUC, precision-recall and calibration "
                       "curves cannot be computed.")
        return out
    fpr, tpr, _ = roc_curve(y_test, proba)
    prec, rec, _ = precision_recall_curve(y_test, proba)
    frac_pos, mean_pred = calibration_curve(y_test, proba, n_bins=10, strategy="quantile")
    out.update({
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "average_precision": float(average_precision_score(y_test, proba)),
        "roc_curve": dict(zip(["fpr", "tpr"], _downsample(fpr, tpr))),
        "pr_curve": dict(zip(["recall", "precision"], _downsample(rec, prec))),
        "calibration_curve": {"mean_predicted": mean_pred.round(4).tolist(), "observed": frac_pos.round(4).tolist()},
    })
    return out


def subgroup_metrics(model, X_test: pd.DataFrame, y_test: pd.Series, threshold: float) -> List[Dict[str, Any]]:
    """Per-group check (sex, age group) on the test set: are errors spread evenly? A fairness diagnostic only."""
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    rows = []
    for col in CATEGORICAL_FEATURES:
        for level in sorted(X_test[col].dropna().unique(), key=str):
            mask = (X_test[col] == level).to_numpy()
            yt, yp = y_test.to_numpy()[mask], pred[mask]
            rows.append({"variable": col, "group": str(level), "n": int(mask.sum()),
                         "observed_rate": float(yt.mean()), "predicted_positive_rate": float(yp.mean()),
                         "recall": float(recall_score(yt, yp, zero_division=0)) if yt.sum() else None,
                         "precision": float(precision_score(yt, yp, zero_division=0)) if yp.sum() else None})
    return rows


def importance_on_test(model, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, Any]:
    """Permutation importance on held-out data: the drop in score when one input is shuffled."""
    scoring = "roc_auc" if len(np.unique(y_test)) == 2 else "accuracy"
    result = permutation_importance(model, X_test, y_test, scoring=scoring, n_repeats=10,
                                    random_state=RANDOM_SEED, n_jobs=1)
    rows = [{"feature": f, "label": FEATURE_INFO[f]["label"], "mean": float(m), "std": float(s)}
            for f, m, s in zip(X_test.columns, result.importances_mean, result.importances_std)]
    return {"scoring": scoring, "features": sorted(rows, key=lambda r: -r["mean"])}


def reference_profile(X_train: pd.DataFrame) -> Dict[str, Any]:
    """The most typical answers in the training data (median / most common), used for 'what-if' explanations."""
    ref: Dict[str, Any] = {}
    for col in NUMERIC_FEATURES:
        ref[col] = int(round(float(X_train[col].median())))
    for col in CATEGORICAL_FEATURES:
        ref[col] = str(X_train[col].mode(dropna=True).iloc[0])
    return ref


# --------------------------------------------------------------------------------------
# Train, save, load
# --------------------------------------------------------------------------------------
def _sha256(path: Path) -> Optional[str]:
    if not Path(path).exists():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(dp.PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def train_and_evaluate(df: Optional[pd.DataFrame] = None, data_path: Optional[Path] = None, save: bool = True,
                       model_path: Path = MODEL_FILE, metadata_path: Path = METADATA_FILE) -> Dict[str, Any]:
    """Run the whole workflow. Returns {'model', 'metadata', 'models', 'X_test', 'y_test'}."""
    data_path = Path(data_path) if data_path else dp.CLEANED_CSV_FILE
    if df is None:
        df = load_training_data(data_path)
    X, y, data_report = prepare_xy(df)
    X_train, X_test, y_train, y_test = split_data(X, y)
    if set(X_train.index) & set(X_test.index):
        raise ModelError("Internal error: training and test sets overlap.")

    cv = cross_validate_models(X_train, y_train)
    selected, reason = select_model(cv)
    thresholds = {k: choose_threshold(y_train.to_numpy(), r["oof"]) for k, r in cv.items()}

    calibrated = False
    if cv[selected]["ece"] > CALIBRATION_ECE_LIMIT:
        # Probabilities are shown to users, so poorly calibrated ones are corrected (decided on training CV only).
        def make_calibrated():
            return CalibratedClassifierCV(build_pipeline(selected), method="sigmoid", cv=_cv())
        oof_cal = cross_val_predict(make_calibrated(), X_train, y_train, cv=_cv(), method="predict_proba")[:, 1]
        cv[selected]["ece_after_calibration"] = expected_calibration_error(y_train, oof_cal)
        thresholds[selected] = choose_threshold(y_train.to_numpy(), oof_cal)
        calibrated = True

    fitted, test_metrics = {}, {}
    for kind in MODEL_NAMES:
        model = (CalibratedClassifierCV(build_pipeline(kind), method="sigmoid", cv=_cv())
                 if (kind == selected and calibrated) else build_pipeline(kind))
        fitted[kind] = model.fit(X_train, y_train)
        test_metrics[kind] = evaluate_on_test(fitted[kind], X_test, y_test, thresholds[kind])
    final = fitted[selected]

    metadata = {
        "model_name": MODEL_NAMES[selected], "model_kind": selected, "model_version": MODEL_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__, "pandas_version": pd.__version__,
        "target": TARGET, "target_definition": TARGET_DEFINITION,
        "features": FEATURES, "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES,
        "feature_info": FEATURE_INFO, "excluded_columns": EXCLUDED_COLUMNS,
        "dataset": {"path": _relative(data_path), "sha256": _sha256(data_path), **data_report},
        "split": {"test_size": TEST_SIZE, "random_seed": RANDOM_SEED, "stratified": True,
                  "n_train": int(len(y_train)), "n_test": int(len(y_test)),
                  "train_class_counts": {str(k): int(v) for k, v in y_train.value_counts().sort_index().items()},
                  "test_class_counts": {str(k): int(v) for k, v in y_test.value_counts().sort_index().items()}},
        "missing_in_training": {c: float(X_train[c].isna().mean()) for c in FEATURES},
        "cross_validation": {k: {m: v for m, v in r.items() if m != "oof"} for k, r in cv.items()},
        "cv_folds": CV_FOLDS,
        "selection": {"criterion": (f"highest {CV_FOLDS}-fold cross-validated ROC-AUC on the training set; "
                                    f"Logistic Regression preferred if within {SELECTION_TOLERANCE}"),
                      "selected": selected, "reason": reason},
        "threshold": {"value": thresholds[selected], "per_model": thresholds,
                      "method": "maximises F1 on out-of-fold training predictions"},
        "imbalance_handling": ("No class weights or resampling. The decision threshold is chosen on training "
                               "cross-validation to balance precision and recall; the test set is never resampled."),
        "calibration": {"applied": calibrated, "ece_limit": CALIBRATION_ECE_LIMIT,
                        "cv_ece": cv[selected]["ece"], "method": "sigmoid (Platt), fitted within training data"
                        if calibrated else "not needed"},
        "test_metrics": test_metrics,
        "permutation_importance": importance_on_test(final, X_test, y_test),
        "subgroup_metrics": subgroup_metrics(final, X_test, y_test, thresholds[selected]),
        "reference_profile": reference_profile(X_train),
        "training_positive_rate": float(y_train.mean()),
        "survey_weights": ("Not used. The model is fitted and evaluated on the unweighted sample with an "
                           "ordinary random split, which ignores the survey's strata and clusters."),
        "limitations": LIMITATIONS,
    }
    if save:
        save_model(final, metadata, model_path, metadata_path)
    return {"model": final, "metadata": metadata, "models": fitted, "X_test": X_test, "y_test": y_test}


def save_model(model, metadata: Dict[str, Any], model_path: Path = MODEL_FILE,
               metadata_path: Path = METADATA_FILE) -> None:
    model_path, metadata_path = Path(model_path), Path(metadata_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"model": model, "features": FEATURES, "model_version": MODEL_VERSION,
              "sklearn_version": sklearn.__version__, "threshold": metadata["threshold"]["value"]}
    joblib.dump(bundle, model_path, compress=3)
    metadata_path.write_text(json.dumps(metadata, indent=2, default=dp._json_default), encoding="utf-8")
    logger.info("Saved model to %s and metadata to %s", model_path, metadata_path)


def load_model(model_path: Path = MODEL_FILE, metadata_path: Path = METADATA_FILE):
    """Return (fitted pipeline, metadata). Raises ModelNotTrainedError / ModelError with the fix."""
    model_path, metadata_path = Path(model_path), Path(metadata_path)
    if not model_path.exists():
        raise ModelNotTrainedError(f"No trained model found at {_relative(model_path)}. "
                                   f"Train it from the project folder with:  {TRAIN_COMMAND}")
    if not metadata_path.exists():
        raise ModelError(f"The model's metadata file {_relative(metadata_path)} is missing. "
                         f"Retrain with:  {TRAIN_COMMAND}")
    try:
        bundle = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:  # corrupted, truncated or incompatible file
        raise ModelError(f"The saved model could not be read ({type(exc).__name__}: {exc}). "
                         f"Retrain with:  {TRAIN_COMMAND}") from exc
    if not isinstance(bundle, dict) or "model" not in bundle or not hasattr(bundle["model"], "predict_proba"):
        raise ModelError(f"{_relative(model_path)} is not a model saved by this project. Retrain with:  {TRAIN_COMMAND}")
    if bundle.get("features") != FEATURES or metadata.get("features") != FEATURES:
        raise ModelError("The saved model was trained with different input features than this code expects. "
                         f"Retrain with:  {TRAIN_COMMAND}")
    if bundle.get("sklearn_version") != sklearn.__version__:
        warnings.warn(f"Model saved with scikit-learn {bundle.get('sklearn_version')} but {sklearn.__version__} "
                      "is installed; predictions may differ. Retrain or install the pinned version.")
    return bundle["model"], metadata


# --------------------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------------------
def _allowed(feature: str) -> List[Any]:
    return [opt[0] for opt in FEATURE_INFO[feature]["options"]]


def option_label(feature: str, value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "Not answered"
    for opt_value, label in FEATURE_INFO[feature]["options"]:
        if opt_value == value:
            return str(label)
    return str(value)


def validate_profile(profile: Dict[str, Any]) -> pd.DataFrame:
    """Turn a {feature: answer} dict into a one-row model input. None = 'not answered' (imputed like in training)."""
    if not isinstance(profile, dict):
        raise InvalidInputError("The profile must be a dictionary of answers.")
    unknown = sorted(set(profile) - set(FEATURES))
    if unknown:
        raise InvalidInputError(f"Unknown inputs {unknown}. The model uses only: {FEATURES}.")
    row: Dict[str, Any] = {}
    for feature in FEATURES:
        value = profile.get(feature)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            row[feature] = np.nan
            continue
        if feature in NUMERIC_FEATURES:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise InvalidInputError(f"{FEATURE_INFO[feature]['label']}: {value!r} is not a number.") from None
            if not number.is_integer() or int(number) not in _allowed(feature):
                raise InvalidInputError(f"{FEATURE_INFO[feature]['label']}: {value!r} is not one of the survey's "
                                        f"answers {_allowed(feature)}.")
            row[feature] = int(number)
        else:
            if str(value) not in _allowed(feature):
                raise InvalidInputError(f"{FEATURE_INFO[feature]['label']}: {value!r} is not one of the survey's "
                                        f"answers {_allowed(feature)}.")
            row[feature] = str(value)
    if all(pd.isna(v) for v in row.values()):
        raise InvalidInputError("Answer at least one question to get an estimate.")
    return to_feature_frame(pd.DataFrame([row]))


def predict(model, metadata: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """Estimated probability of the target outcome for one illustrative profile."""
    X = validate_profile(profile)
    probability = float(model.predict_proba(X)[0, 1])
    threshold = float(metadata["threshold"]["value"])
    return {"probability": probability, "threshold": threshold,
            "predicted_class": int(probability >= threshold),
            "training_positive_rate": float(metadata["training_positive_rate"]),
            "not_answered": [FEATURE_INFO[f]["label"] for f in FEATURES if pd.isna(X.iloc[0][f])]}


def explain_prediction(model, metadata: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Local 'what-if' explanation: how the estimate changes if ONE answer is replaced by the most typical
    training answer, keeping the others. Describes the model's behaviour, not causes."""
    base_X = validate_profile(profile)
    base_p = float(model.predict_proba(base_X)[0, 1])
    reference = metadata["reference_profile"]
    rows = []
    for feature in FEATURES:
        current = base_X.iloc[0][feature]
        ref = reference[feature]
        if pd.isna(current) or current == ref:
            continue
        what_if = base_X.copy()
        what_if[feature] = float(ref) if feature in NUMERIC_FEATURES else ref
        p_ref = float(model.predict_proba(what_if)[0, 1])
        rows.append({"feature": feature, "label": FEATURE_INFO[feature]["label"],
                     "your_answer": option_label(feature, current if feature in CATEGORICAL_FEATURES else int(current)),
                     "typical_answer": option_label(feature, ref),
                     "probability_with_typical": p_ref, "difference": base_p - p_ref})
    return sorted(rows, key=lambda r: -abs(r["difference"]))


# --------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------
def print_summary(metadata: Dict[str, Any]) -> None:
    split = metadata["split"]
    print(f"\n=== {metadata['model_name']} (v{metadata['model_version']}), trained {metadata['created_at_utc']} ===")
    print(f"Target: {metadata['target']} - {metadata['target_definition']}")
    print(f"Features: {', '.join(metadata['features'])}")
    print(f"Rows used: {metadata['dataset']['rows_used']:,} (train {split['n_train']:,} / test {split['n_test']:,}); "
          f"excluded for missing target: {metadata['dataset']['rows_missing_target']:,}")
    print(f"Selection: {metadata['selection']['reason']}")
    print(f"Decision threshold: {metadata['threshold']['value']:.2f} ({metadata['threshold']['method']})")
    print(f"Calibration: {metadata['calibration']['method']} (CV ECE {metadata['calibration']['cv_ece']:.3f})")
    print("\nHeld-out test metrics:")
    header = f"{'model':<22}{'accuracy':>9}{'precision':>10}{'recall':>8}{'F1':>7}{'ROC-AUC':>9}{'PR-AUC':>8}{'Brier':>7}"
    print(header)
    for kind, m in metadata["test_metrics"].items():
        auc = "n/a" if m["roc_auc"] is None else f"{m['roc_auc']:.3f}"
        ap = "n/a" if m["average_precision"] is None else f"{m['average_precision']:.3f}"
        print(f"{MODEL_NAMES[kind]:<22}{m['accuracy']:>9.3f}{m['precision']:>10.3f}{m['recall']:>8.3f}"
              f"{m['f1']:>7.3f}{auc:>9}{ap:>8}{m['brier']:>7.3f}")
    print("\nPermutation importance (test set):")
    for r in metadata["permutation_importance"]["features"]:
        print(f"  {r['label']:<55}{r['mean']:+.4f} (sd {r['std']:.4f})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Train or inspect the well-being prediction model.")
    parser.add_argument("--train", action="store_true", help="train, evaluate and save the model")
    parser.add_argument("--show", action="store_true", help="print the saved model's summary")
    parser.add_argument("--data", type=Path, default=None, help="cleaned CSV (default: data/processed/cleaned_data.csv)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not (args.train or args.show):
        parser.print_help()
        return 0
    try:
        if args.train:
            metadata = train_and_evaluate(data_path=args.data)["metadata"]
            print_summary(metadata)
            print(f"\nSaved: {_relative(MODEL_FILE)} and {_relative(METADATA_FILE)}")
        else:
            print_summary(load_model()[1])
    except (ModelError, dp.DataProcessingError) as exc:
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
