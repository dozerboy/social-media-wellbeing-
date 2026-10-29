"""The dashboard's 'AI Predictions & Recommendations' tab (called from app.py).

Loads the saved model once (cached), never retrains while the user changes inputs, and reads every
metric, curve and importance value from models/model_metadata.json written at training time.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import data_processing as dp
from src import ml_model as ml
from src import plotting as pl
from src import recommendations as recs

NOT_ANSWERED = "Prefer not to answer"
METRIC_ROWS = [("accuracy", "Accuracy"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1-score"),
               ("roc_auc", "ROC-AUC"), ("average_precision", "PR-AUC (average precision)"),
               ("brier", "Brier score (lower is better)"), ("threshold", "Decision threshold")]


# --------------------------------------------------------------------------------------
# Model loading (cached; the file's modification time is part of the key, so a retrain is picked up)
# --------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading the trained model…")
def _load_cached(model_path: str, metadata_path: str, modified: float):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model, metadata = ml.load_model(Path(model_path), Path(metadata_path))
    return model, metadata, [str(w.message) for w in caught]


def load_model() -> Tuple[Any, Dict[str, Any], List[str]]:
    path = ml.MODEL_FILE
    if not path.exists():
        ml.load_model()  # raises ModelNotTrainedError with instructions
    return _load_cached(str(path), str(ml.METADATA_FILE), path.stat().st_mtime)


def _train_button(label: str) -> None:
    st.markdown(f"To train it from the project folder, run:  `{ml.TRAIN_COMMAND}`")
    if st.button(label, key="ai_train"):
        with st.spinner("Training on data/processed/cleaned_data.csv… (about 30 seconds)"):
            try:
                ml.train_and_evaluate(save=True)
            except (ml.ModelError, dp.DataProcessingError) as exc:
                st.error(f"Training failed: {exc}")
                return
        st.cache_resource.clear()
        st.rerun()


# --------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------
def _about(metadata: Dict[str, Any]) -> None:
    info, split = metadata["feature_info"], metadata["split"]
    inputs = ", ".join(info[f]["label"].lower() for f in metadata["features"])
    st.markdown("#### About the AI model")
    st.markdown(
        f"- **What it predicts:** the estimated likelihood that a student reported their mental health was "
        f"*not good most of the time or always* in the past 30 days (survey question Q84).\n"
        f"- **Data:** this project's cleaned CDC YRBS 2023 dataset: {metadata['dataset']['rows_used']:,} students "
        f"who answered that question ({split['n_train']:,} for training, {split['n_test']:,} held out for testing).\n"
        f"- **Inputs:** {inputs}.\n"
        f"- **Algorithms compared:** Logistic Regression and Random Forest. Selected: **{metadata['model_name']}**.\n"
        f"- **What the result means:** a pattern learned from survey answers, an *estimate* for a profile like "
        f"the one entered. It is **not a diagnosis** and not a measurement of anyone's mental health.")


def _profile_form(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    info, reference = metadata["feature_info"], metadata["reference_profile"]
    st.markdown("#### Illustrative profile")
    st.caption("Describe a hypothetical high-school student using the survey's own answer choices. "
               "Choose 'Prefer not to answer' to leave a question out; the model then fills it in "
               "the same way it did for students who skipped it.")
    with st.form("ai_profile_form"):
        cols = st.columns(2)
        profile: Dict[str, Any] = {}
        for i, feature in enumerate(metadata["features"]):
            opts = [value for value, _ in info[feature]["options"]] + [NOT_ANSWERED]
            labels = {value: label for value, label in info[feature]["options"]}
            default = opts.index(reference[feature]) if reference[feature] in opts else 0
            choice = cols[i % 2].selectbox(
                info[feature]["label"], opts, index=default, key=f"ai_{feature}",
                format_func=lambda v, labels=labels: NOT_ANSWERED if v == NOT_ANSWERED else str(labels[v]),
                help=f"Survey question {info[feature]['source']}")
            profile[feature] = None if choice == NOT_ANSWERED else choice   # None = not answered
        submitted = st.form_submit_button("Predict", type="primary", key="ai_predict")
    if submitted:
        st.session_state["ai_profile"] = profile
    return st.session_state.get("ai_profile")


def _probability_chart(p: float, threshold: float, base: float, style_fig: Callable) -> go.Figure:
    fig = go.Figure(go.Bar(x=[p * 100], y=["Estimate"], orientation="h", marker_color=pl.BLUE, width=0.45,
                           hovertemplate="Estimated likelihood: %{x:.1f}%<extra></extra>"))
    # The two reference lines are often close together, so their labels go on opposite sides of the lines.
    left, right = sorted([(threshold, "Model cut-off", "dash"), (base, "Rate in training data", "dot")])
    for (value, name, dash), side in ((left, "top left"), (right, "top right")):
        fig.add_vline(x=value * 100, line=dict(color=pl.INK_2, width=1.5, dash=dash),
                      annotation_text=f"{name}: {value:.0%}", annotation_position=side)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title="Estimated likelihood (under the model's definition)")
    fig.update_yaxes(visible=False)
    return style_fig(fig, "Estimated likelihood of reporting poor mental well-being", height=230, legend=False)


def _results(model, metadata: Dict[str, Any], profile: Dict[str, Any], style_fig, show_chart) -> bool:
    st.markdown("#### Prediction result")
    try:
        res = ml.predict(model, metadata, profile)
    except ml.InvalidInputError as exc:
        st.error(f"This profile can't be scored: {exc}")
        return False
    p, thr, base = res["probability"], res["threshold"], res["training_positive_rate"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated likelihood", f"{p:.0%}",
              help="Estimated likelihood of reporting poor mental well-being under the model's definition.")
    c2.metric("Compared with the model's cut-off", "Above" if res["predicted_class"] else "Below",
              help=f"The model labels an estimate of {thr:.0%} or more as its positive class. The cut-off was "
                   "chosen on training data to balance missed cases and false alarms.")
    c3.metric("Rate among training students", f"{base:.0%}",
              help="Share of students in the training data who reported poor mental health.")
    show_chart(_probability_chart(p, thr, base, style_fig))
    side = "at or above" if res["predicted_class"] else "below"
    compared = "higher than" if p > base else "lower than" if p < base else "the same as"
    st.markdown(
        f"Among surveyed students whose answers resemble this profile, the model estimates about **{p:.0%}** "
        f"reported poor mental health most of the time or always. That is {compared} the {base:.0%} rate in "
        f"the training data, and {side} the model's {thr:.0%} cut-off.")
    if res["not_answered"]:
        st.caption("Not answered (filled in by the model as during training): " + ", ".join(res["not_answered"]) + ".")
    st.info("This is an uncertain statistical estimate learned from US high-school students surveyed in 2023. "
            "It is **not a diagnosis**, it may not apply to any individual, and it must not be used to make "
            "decisions about real people.")
    return True


def _recommendations(profile: Dict[str, Any]) -> None:
    st.markdown("#### Personalised well-being suggestions")
    st.caption("Rule-based suggestions from the answers above, separate from the model's estimate. They appear "
               "whatever the estimate is, and they do not promise to change it.")
    result = recs.generate_recommendations(profile)
    for r in result.recommendations:
        with st.container(border=True):
            st.markdown(f"**{r.title}**")
            st.markdown(r.action)
            st.markdown(f"*Why this appears:* {r.reason}")
            st.caption("Based on: " + "; ".join(r.indicators)
                       + (f" · [Guideline source]({r.source})" if r.source else ""))
    if result.more_available:
        st.caption(f"{result.more_available} more suggestion(s) apply; only the most relevant three are shown.")
    for s in result.strengths:
        st.success(s)
    for note in result.not_used:
        st.caption(note)
    st.info(result.support_note)


def _metrics_table(metadata: Dict[str, Any]) -> pd.DataFrame:
    rows = {}
    for kind, m in metadata["test_metrics"].items():
        name = ml.MODEL_NAMES[kind] + (" (selected)" if kind == metadata["model_kind"] else "")
        rows[name] = {label: (None if m.get(key) is None else round(float(m[key]), 3)) for key, label in METRIC_ROWS}
    return pd.DataFrame(rows)


def _curve_chart(metadata: Dict[str, Any], kind: str, style_fig) -> Optional[go.Figure]:
    fig = go.Figure()
    for model_kind, color in [("logistic_regression", pl.BLUE), ("random_forest", pl.TEAL)]:
        m = metadata["test_metrics"][model_kind]
        curve = m["roc_curve"] if kind == "roc" else m["pr_curve"]
        if curve is None:
            return None
        x, y = (curve["fpr"], curve["tpr"]) if kind == "roc" else (curve["recall"], curve["precision"])
        score = m["roc_auc"] if kind == "roc" else m["average_precision"]
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2.5),
                                 name=f"{ml.MODEL_NAMES[model_kind]} ({score:.3f})"))
    if kind == "roc":
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Chance (0.5)",
                                 line=dict(color=pl.MUTED, dash="dash", width=1)))
        fig.update_xaxes(title="False positive rate", range=[0, 1])
        fig.update_yaxes(title="True positive rate (recall)", range=[0, 1])
        return style_fig(fig, "ROC curves on the held-out test set", height=380)
    rate = metadata["test_metrics"][metadata["model_kind"]]["observed_positive_rate"]
    fig.add_trace(go.Scatter(x=[0, 1], y=[rate, rate], mode="lines", name=f"No-skill baseline ({rate:.2f})",
                             line=dict(color=pl.MUTED, dash="dash", width=1)))
    fig.update_xaxes(title="Recall", range=[0, 1])
    fig.update_yaxes(title="Precision", range=[0, 1])
    return style_fig(fig, "Precision-recall curves on the held-out test set", height=380)


def _performance(metadata: Dict[str, Any], style_fig, show_chart) -> None:
    st.markdown("#### Model performance (held-out test set)")
    sel = metadata["selection"]
    st.markdown(f"**Selected model:** {metadata['model_name']}. **Criterion:** {sel['criterion']}. {sel['reason']}")
    st.dataframe(_metrics_table(metadata), width="stretch")
    negative_share = 1 - metadata["test_metrics"][metadata["model_kind"]]["observed_positive_rate"]
    with st.expander("What these metrics mean, and why accuracy alone is not enough"):
        st.markdown(
            f"- **Accuracy:** the share of all test students classified correctly. {negative_share:.0%} of test "
            f"students did *not* report poor mental health, so a model that always says 'no' would score "
            f"{negative_share:.0%} accuracy while finding nobody. That is why the other metrics matter.\n"
            "- **Precision:** of the students the model flags, the share who really reported poor mental health "
            "(a low value means many false alarms).\n"
            "- **Recall:** of the students who reported poor mental health, the share the model flags (a low "
            "value means many missed cases).\n"
            "- **F1-score:** a balance of precision and recall.\n"
            "- **ROC-AUC:** how well the model ranks a random positive student above a random negative one "
            "(0.5 = chance, 1.0 = perfect).\n"
            "- **PR-AUC:** like ROC-AUC, but focused on the minority class.\n"
            "- **Brier score:** the average squared error of the probabilities (lower is better).\n\n"
            "**False positives vs false negatives.** Lowering the cut-off finds more students who reported poor "
            "mental health (fewer false negatives) but flags more who did not (more false positives). The cut-off "
            "here maximises F1 on training data, a middle ground. In a real support setting a missed student is "
            "usually the more serious error, but this demo model is not meant for such decisions.")
    m = metadata["test_metrics"][metadata["model_kind"]]
    c1, c2 = st.columns(2)
    with c1:
        cm = m["confusion_matrix"]
        fig = go.Figure(go.Heatmap(
            z=cm, x=["Predicted 0", "Predicted 1"], y=["Actual 0", "Actual 1"],
            colorscale=[[0, "#eaf1f8"], [1, pl.BLUE]], showscale=False,
            text=[[f"{v:,}" for v in row] for row in cm], texttemplate="%{text}",
            hovertemplate="%{y}, %{x}: %{z:,} students<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        show_chart(style_fig(fig, f"Confusion matrix: {metadata['model_name']}", height=340, legend=False))
        st.caption("Top-right = false positives (flagged, did not report poor mental health); "
                   "bottom-left = false negatives (reported it, not flagged).")
    with c2:
        split = metadata["split"]
        dist = pd.DataFrame({"Training set": split["train_class_counts"], "Test set": split["test_class_counts"]})
        dist.index = dist.index.map({"0": "0: not poor", "1": "1: poor mental health"})
        st.markdown("**Class distribution**")
        st.dataframe(dist, width="stretch")
        st.caption(f"Stratified {1 - ml.TEST_SIZE:.0%} / {ml.TEST_SIZE:.0%} split (seed {split['random_seed']}), "
                   "so both sets keep the same balance. No resampling was applied.")
        cv = pd.DataFrame(metadata["cross_validation"]).T.rename(index=ml.MODEL_NAMES)
        st.markdown("**Cross-validation on the training set (used for selection)**")
        st.dataframe(cv.round(3), width="stretch")
    if m["roc_curve"] is None:
        st.info(m["note"])
        return
    c3, c4 = st.columns(2)
    with c3:
        show_chart(_curve_chart(metadata, "roc", style_fig))
    with c4:
        show_chart(_curve_chart(metadata, "pr", style_fig))
    cal = m["calibration_curve"]
    fig = go.Figure([go.Scatter(x=cal["mean_predicted"], y=cal["observed"], mode="lines+markers",
                                line=dict(color=pl.BLUE, width=2.5), name="Model"),
                     go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration",
                                line=dict(color=pl.MUTED, dash="dash", width=1))])
    fig.update_xaxes(title="Average estimated likelihood", range=[0, 1], tickformat=".0%")
    fig.update_yaxes(title="Observed share reporting poor mental health", range=[0, 1], tickformat=".0%")
    show_chart(style_fig(fig, "Calibration: do the estimates match observed rates?", height=360))
    st.caption(f"Points near the dashed line mean the displayed likelihoods are trustworthy on average. "
               f"Calibration step: {metadata['calibration']['method']}.")


def _explainability(model, metadata: Dict[str, Any], profile: Optional[Dict[str, Any]], style_fig, show_chart) -> None:
    st.markdown("#### What influences the model?")
    imp = metadata["permutation_importance"]
    rows = sorted(imp["features"], key=lambda r: r["mean"])
    fig = go.Figure(go.Bar(x=[r["mean"] for r in rows], y=[r["label"] for r in rows], orientation="h",
                           marker_color=pl.BLUE,
                           error_x=dict(type="data", array=[r["std"] for r in rows], thickness=1.2),
                           hovertemplate="%{y}: %{x:.4f}<extra></extra>"))
    fig.update_xaxes(title=f"Drop in test {imp['scoring'].upper().replace('_', '-')} when the input is shuffled")
    show_chart(style_fig(fig, "Permutation importance (held-out test set)", height=330, legend=False))
    st.caption("Bigger bars mean the model relies more on that answer for prediction. This shows what the model "
               "uses, **not** what causes poor mental health.")

    if profile:
        try:
            local = ml.explain_prediction(model, metadata, profile)
        except ml.InvalidInputError:
            local = []
        st.markdown("**For the profile above (what-if explanation)**")
        if not local:
            st.caption("Every answered input already equals the most typical training answer, so there is nothing "
                       "to compare.")
        else:
            local = list(reversed(local))
            fig = go.Figure(go.Bar(
                x=[r["difference"] * 100 for r in local], y=[r["label"] for r in local], orientation="h",
                marker_color=[pl.BLUE if r["difference"] > 0 else pl.TEAL for r in local],
                customdata=[[r["your_answer"], r["typical_answer"]] for r in local],
                hovertemplate="Your answer: %{customdata[0]}<br>Typical answer: %{customdata[1]}"
                              "<br>Difference: %{x:+.1f} percentage points<extra></extra>"))
            fig.update_xaxes(title="Change in estimate vs the typical answer (percentage points)", zeroline=True,
                             zerolinecolor=pl.AXIS)
            show_chart(style_fig(fig, "How each answer moves this estimate", height=300, legend=False))
            st.caption("Each bar compares the estimate for this profile with the estimate if that one answer were "
                       "replaced by the most common training answer. Blue raises the estimate, teal lowers it. "
                       "It describes how the model behaves, not a cause or a personal fault.")

    with st.expander("Fairness check and limitations"):
        sub = pd.DataFrame(metadata["subgroup_metrics"]).rename(columns={
            "variable": "Variable", "group": "Group", "n": "Test students", "observed_rate": "Observed rate",
            "predicted_positive_rate": "Flagged rate", "recall": "Recall", "precision": "Precision"})
        st.dataframe(sub.round(3), hide_index=True, width="stretch")
        top = metadata["permutation_importance"]["features"][0]["label"]
        st.caption(f"Compare the flagged rate and recall between groups: a model can make more errors for some "
                   f"groups than others. The model's most important input on the test set is '{top}'. Differences "
                   f"linked to sex or age are group-level survey patterns, not personal traits. Race/ethnicity is "
                   f"deliberately not used.")
        st.markdown("\n".join(f"- {item}" for item in metadata["limitations"]))
        st.caption(metadata["survey_weights"])


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------
def render_ai_tab(style_fig: Callable, show_chart: Callable) -> None:
    st.subheader("AI Predictions & Recommendations")
    try:
        model, metadata, load_warnings = load_model()
    except ml.ModelNotTrainedError as exc:
        st.warning(f"**The prediction model has not been trained yet.** {exc}")
        _train_button("Train the model now (uses the existing dataset)")
        return
    except ml.ModelError as exc:
        st.error(f"**The saved model could not be used.** {exc}")
        _train_button("Retrain the model now (uses the existing dataset)")
        return
    for message in load_warnings:
        st.warning(message)

    _about(metadata)
    profile = _profile_form(metadata)
    if profile is None:
        st.caption("Choose answers and press **Predict** to see an estimate and suggestions.")
    else:
        if _results(model, metadata, profile, style_fig, show_chart):
            _recommendations(profile)
    st.divider()
    _performance(metadata, style_fig, show_chart)
    st.divider()
    _explainability(model, metadata, profile, style_fig, show_chart)
