"""Social Media Usage & Mental Well-Being: interactive Streamlit dashboard.

Data: CDC Youth Risk Behavior Survey (YRBS) 2023, national high-school file, cleaned by
src/data_processing.py (the same pipeline the notebook uses).

Run from the project folder:
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")  # draw Matplotlib figures off-screen for Streamlit
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import analysis_utils as au  # noqa: E402
from src import data_processing as dp  # noqa: E402
from src import plotting as pl  # noqa: E402
from src.dashboard_ai import render_ai_tab  # noqa: E402

st.set_page_config(page_title="Social Media & Well-Being", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------
FONT = "Inter, Segoe UI, system-ui, -apple-system, sans-serif"
MIN_GROUP_N = 30  # groups with fewer students are hidden from group charts (estimates too unstable)

SM_SHORT = {1: "Never", 2: "Few/month", 3: "Weekly", 4: "Few/week", 5: "Daily",
            6: "Several/day", 7: "Hourly", 8: "More than hourly"}
SLEEP_SHORT = {1: "4 h or less", 2: "5 h", 3: "6 h", 4: "7 h", 5: "8 h", 6: "9 h", 7: "10 h or more"}
SLEEP_TICKS = {4: "≤4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10+"}

AGE_OPTIONS = list(dp.AGE_GROUP_ORDER)
SEX_OPTIONS = list(dp.SEX_LABELS.values())
GRADE_OPTIONS = list(dp.GRADE_LABELS.values())
RACE_OPTIONS = list(dp.RACE_LABELS.values())
FULL_RANGES = {"sm_range": (1, 8), "sleep_range": (1, 7), "active_range": (0, 7)}

INDICATORS = {
    "poor_mental_health": "Poor mental health %",
    "sad_hopeless": "Persistent sadness %",
    "sleep_8plus": "Sleeps 8+ h %",
    "active_5plus": "Active 5+ days %",
}

FILTER_KEYS = ["f_age", "f_sm", "f_sleep", "f_active", "f_sex", "f_grade", "f_race", "f_weighted"]

CSS = f"""
<style>
.block-container {{padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px;}}
h1 {{font-weight: 700; letter-spacing: -0.02em; color: {pl.INK}; margin-bottom: 0.2rem;}}
h2, h3 {{letter-spacing: -0.01em; color: {pl.INK};}}
.subtitle {{font-size: 1.15rem; color: {pl.INK_2}; margin: 0 0 0.8rem 0;}}
.intro {{color: {pl.INK_2}; max-width: 70rem; line-height: 1.55;}}
div[data-testid="stMetric"] {{background: {pl.SURFACE}; border: 1px solid {pl.GRID}; border-radius: 12px;
    padding: 14px 18px; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);}}
div[data-testid="stMetricLabel"] p {{color: {pl.INK_2}; font-size: 0.86rem; font-weight: 500;}}
div[data-testid="stMetricValue"] {{color: {pl.INK}; font-weight: 650;}}
.na-note {{color: {pl.MUTED}; font-size: 0.85rem; margin-top: 0.3rem;}}
.insight {{background: {pl.SURFACE}; border: 1px solid {pl.GRID}; border-left: 4px solid {pl.BLUE};
    border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; color: {pl.INK};}}
</style>
"""


# --------------------------------------------------------------------------------------
# Data loading, filtering and cached calculations
# --------------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the cleaned YRBS 2023 data…")
def load_data() -> pd.DataFrame:
    """Load cleaned_data.csv, building it with the shared pipeline first if it does not exist."""
    if not dp.CLEANED_CSV_FILE.exists():
        if dp.RAW_DAT_FILE.exists() or dp.INTERIM_CSV_FILE.exists():
            dp.run_pipeline()
        else:
            dp.check_raw_file(dp.RAW_DAT_FILE)  # raises an error with download instructions
    return au.add_usage_group(dp.load_cleaned_data())


def _category_mask(series: pd.Series, selected: Tuple[str, ...], options: List[str]) -> pd.Series:
    """Keep everyone (including missing) when all options are selected; else only the selection."""
    if set(selected) >= set(options):
        return pd.Series(True, index=series.index)
    return series.astype(object).isin(list(selected))


def _range_mask(series: pd.Series, chosen: Tuple[int, int], full: Tuple[int, int]) -> pd.Series:
    """Keep everyone (including missing) when the full range is chosen; else values inside it."""
    if tuple(chosen) == tuple(full):
        return pd.Series(True, index=series.index)
    return series.astype(float).between(chosen[0], chosen[1]).fillna(False).astype(bool)


def apply_filters(df: pd.DataFrame, age: Tuple[str, ...], sex: Tuple[str, ...], grade: Tuple[str, ...],
                  race: Tuple[str, ...], sm_range: Tuple[int, int], sleep_range: Tuple[int, int],
                  active_range: Tuple[int, int], weighted: bool) -> pd.DataFrame:
    """Rows matching the filters, with column 'w' = survey weight (or 1 when unweighted)."""
    mask = (_category_mask(df["age_group"], age, AGE_OPTIONS)
            & _category_mask(df["sex"], sex, SEX_OPTIONS)
            & _category_mask(df["grade_label"], grade, GRADE_OPTIONS)
            & _category_mask(df["race_ethnicity"], race, RACE_OPTIONS)
            & _range_mask(df["social_media_code"], sm_range, FULL_RANGES["sm_range"])
            & _range_mask(df["sleep_code"], sleep_range, FULL_RANGES["sleep_range"])
            & _range_mask(df["active_days"], active_range, FULL_RANGES["active_range"]))
    out = df.loc[mask].copy()
    out["w"] = out["weight"].astype(float) if weighted else 1.0
    return out


@st.cache_data(show_spinner=False)
def filter_data(**filters) -> pd.DataFrame:
    return apply_filters(load_data(), **filters)


@st.cache_data(show_spinner=False)
def summary_metrics(data: pd.DataFrame) -> Dict[str, float]:
    return {
        "n": len(data),
        "frequent": au.weighted_share(data["social_media_frequent"], data["w"])[0],
        "sleep": au.weighted_mean(data["sleep_hours_approx"], data["w"]),
        "active": au.weighted_mean(data["active_days"], data["w"]),
        "poor_mh": au.weighted_share(data["poor_mental_health"], data["w"])[0],
        "sad": au.weighted_share(data["sad_hopeless"], data["w"])[0],
    }


TESTS = {  # key: (label, function, arguments)
    "sm_sleep": ("Social media freq. ↔ sleep hours", au.spearman, ("social_media_code", "sleep_hours_approx")),
    "sm_poor_mh": ("Social media freq. ↔ poor mental health", au.spearman, ("social_media_code", "poor_mh_code")),
    "active_poor_mh": ("Active days ↔ poor mental health", au.spearman, ("active_days", "poor_mh_code")),
    "age_sm": ("Age ↔ social media freq.", au.spearman, ("age_code", "social_media_code")),
    "freq_x_poor_mh": ("Frequent use × poor mental health", au.chi_square,
                       ("social_media_frequent", "poor_mental_health")),
    "freq_x_sad": ("Frequent use × persistent sadness", au.chi_square, ("social_media_frequent", "sad_hopeless")),
    "active5_x_poor_mh": ("Active 5+ days × poor mental health", au.chi_square,
                          ("active_5plus", "poor_mental_health")),
}


@st.cache_data(show_spinner=False)
def run_tests(data: pd.DataFrame) -> Dict[str, Dict[str, object]]:
    return {key: func(data, *args) for key, (_, func, args) in TESTS.items()}


@st.cache_data(show_spinner=False)
def correlation_matrix(data: pd.DataFrame) -> pd.DataFrame:
    return au.spearman_matrix(data, au.CORRELATION_VARIABLES)


# --------------------------------------------------------------------------------------
# Small UI helpers
# --------------------------------------------------------------------------------------
def style_fig(fig: go.Figure, title: str, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16, color=pl.INK)),
        template="plotly_white", height=height, font=dict(family=FONT, size=13, color=pl.INK_2),
        margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor=pl.SURFACE, plot_bgcolor=pl.SURFACE,
        hoverlabel=dict(bgcolor="white", font_size=13, font_family=FONT),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text=""),
    )
    fig.update_xaxes(gridcolor=pl.GRID, zeroline=False, linecolor=pl.GRID)
    fig.update_yaxes(gridcolor=pl.GRID, zeroline=False, linecolor=pl.GRID)
    return fig


def show_chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def not_available(what: str, reason: str, substitute: Optional[str] = None) -> None:
    text = f"**{what}: not available in this dataset.** {reason}"
    if substitute:
        text += f" Shown instead: {substitute}."
    st.info(text)


def drop_small_groups(table: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    small = table["n"] < MIN_GROUP_N
    return table.loc[~small].copy(), int(small.sum())


def small_group_note(hidden: int) -> None:
    if hidden:
        st.caption(f"{hidden} group(s) with fewer than {MIN_GROUP_N} students hidden "
                   f"because their estimates would be unreliable.")


def error_bars(t: pd.DataFrame) -> Dict[str, object]:
    return dict(type="data", symmetric=False, array=(t["ci_high"] - t["percent"]).to_numpy(),
                arrayminus=(t["percent"] - t["ci_low"]).to_numpy(), thickness=1.3, width=4)


def with_n(sentence: str, n: int) -> str:
    """Add the sample size inside a sentence's closing parenthesis: '(rho = 0.1).' -> '(rho = 0.1, n = 1,234).'"""
    if sentence.endswith(")."):
        return f"{sentence[:-2]}, n = {n:,})."
    return f"{sentence.rstrip('.')} (n = {n:,})."


def md_bold_to_html(text: str) -> str:
    """Convert **bold** markdown to <b> for use inside an HTML block."""
    parts = text.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


# --------------------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------------------
def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def sidebar() -> Dict[str, object]:
    sb = st.sidebar
    sb.markdown("## Filters")
    sb.caption("All charts and metrics update with these filters.")

    age = sb.multiselect("Age group (years)", AGE_OPTIONS, default=AGE_OPTIONS, key="f_age")
    sm_range = sb.select_slider(
        "Social media use frequency", options=list(SM_SHORT), value=FULL_RANGES["sm_range"],
        format_func=lambda c: SM_SHORT[c], key="f_sm",
        help="How OFTEN students use social media (CDC question Q80). Screen-time hours are "
             "not measured in the 2023 YRBS.")
    sleep_range = sb.select_slider(
        "Sleep on school nights", options=list(SLEEP_SHORT), value=FULL_RANGES["sleep_range"],
        format_func=lambda c: SLEEP_SHORT[c], key="f_sleep",
        help="Hours of sleep on an average school night (CDC question Q85).")
    active_range = sb.slider("Days physically active (60+ min, past week)", 0, 7,
                             FULL_RANGES["active_range"], key="f_active", help="CDC question Q76.")

    with sb.expander("More filters"):
        sex = st.multiselect("Sex", SEX_OPTIONS, default=SEX_OPTIONS, key="f_sex")
        grade = st.multiselect("Grade", GRADE_OPTIONS, default=GRADE_OPTIONS, key="f_grade")
        race = st.multiselect("Race / ethnicity", RACE_OPTIONS, default=RACE_OPTIONS, key="f_race")

    sb.divider()
    weighted = sb.toggle("Use survey weights", value=True, key="f_weighted",
                         help="On: percentages and averages estimate all US high-school students. "
                              "Off: they describe only the students in the sample.")
    sb.button("Reset filters", on_click=reset_filters, width="stretch", key="reset_filters")
    sb.divider()
    sb.caption("Narrowing a range or a list also removes students who did not answer that "
               "question. A full range keeps them.")
    sb.caption("Data: CDC Youth Risk Behavior Survey 2023 (national, grades 9–12).")
    return dict(age=tuple(age), sex=tuple(sex), grade=tuple(grade), race=tuple(race),
                sm_range=tuple(sm_range), sleep_range=tuple(sleep_range),
                active_range=tuple(active_range), weighted=bool(weighted))


# --------------------------------------------------------------------------------------
# Section 1 + 3: header and metric cards
# --------------------------------------------------------------------------------------
def header() -> None:
    st.markdown("# Social Media Usage & Mental Well-Being")
    st.markdown('<p class="subtitle">Exploring the relationship between digital habits, sleep, '
                'lifestyle, and self-reported well-being.</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="intro">This dashboard explores how often US high-school students use social media, '
        'and how that relates to sleep, physical activity, age and self-reported mental health. '
        'It uses the CDC\'s 2023 Youth Risk Behavior Survey. Every number is calculated live from the '
        'filtered data. Results describe <b>associations</b>, not causes.</p>', unsafe_allow_html=True)


def metric_cards(data: pd.DataFrame, full: pd.DataFrame, filtered: bool) -> None:
    m, base = summary_metrics(data), summary_metrics(full)

    def delta(key: str, unit: str) -> Optional[str]:
        if not filtered or pd.isna(m[key]) or pd.isna(base[key]):
            return None
        return f"{m[key] - base[key]:+.1f}{unit} vs all"

    def fmt(value: float, pattern: str) -> str:
        return "–" if pd.isna(value) else pattern.format(value)

    cols = st.columns(6)
    cols[0].metric("Respondents", f"{m['n']:,}",
                   delta=f"{m['n'] / len(full):.0%} of sample" if filtered else None, delta_color="off",
                   help="Number of students in the current selection (unweighted count).")
    cols[1].metric("Frequent social media use", fmt(m["frequent"], "{:.1f}%"), delta("frequent", " pp"),
                   delta_color="off", help="Uses social media several times a day or more often.")
    cols[2].metric("Average sleep", fmt(m["sleep"], "{:.1f} h"), delta("sleep", " h"), delta_color="off",
                   help="School nights. Approximate: '4 or less' counted as 4 h, '10 or more' as 10 h.")
    cols[3].metric("Average active days", fmt(m["active"], "{:.1f} / 7"), delta("active", ""),
                   delta_color="off", help="Days physically active for 60+ minutes in the past week.")
    cols[4].metric("Poor mental health", fmt(m["poor_mh"], "{:.1f}%"), delta("poor_mh", " pp"),
                   delta_color="off",
                   help="Mental health 'not good' most of the time or always in the past 30 days.")
    cols[5].metric("Persistent sadness", fmt(m["sad"], "{:.1f}%"), delta("sad", " pp"), delta_color="off",
                   help="Sad or hopeless almost every day for 2+ weeks in the past 12 months.")
    st.markdown('<p class="na-note">Daily screen time and anxiety scores are not in this dataset, so no '
                'cards are shown for them. Social media frequency and self-reported mental health are '
                'used instead.</p>', unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Section 4: digital habits
# --------------------------------------------------------------------------------------
def section_digital(data: pd.DataFrame) -> None:
    st.subheader("Digital habits")
    not_available("Screen-time distribution", "The 2023 YRBS asks how often students use social media, "
                  "not for how many hours.", "the distribution of social media use frequency")

    c1, c2 = st.columns([1.1, 1])
    with c1:
        dist = au.weighted_distribution(data, "social_media_code", "w")
        if dist.empty:
            st.warning("No answers to the social media question in this selection.")
        else:
            dist["label"] = dist["social_media_code"].astype(int).map(dp.SOCIAL_MEDIA_LABELS)
            fig = go.Figure(go.Bar(
                x=dist["percent"], y=dist["label"], orientation="h", marker_color=pl.BLUE,
                customdata=dist["n"], text=dist["percent"].map(lambda v: f"{v:.1f}%"),
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}<br><b>%{x:.1f}%</b> of students<br>n = %{customdata:,}<extra></extra>"))
            fig.update_yaxes(autorange="reversed", title=None)
            fig.update_xaxes(title="Students (%)", ticksuffix="%")
            show_chart(style_fig(fig, "How often students use social media", legend=False))

    with c2:
        by_age, hidden = drop_small_groups(au.weighted_share_by(data, "age_group", "social_media_frequent", "w"))
        if by_age.empty:
            st.warning("Not enough students per age group in this selection.")
        else:
            fig = go.Figure(go.Bar(
                x=by_age["age_group"].astype(str), y=by_age["percent"], marker_color=pl.BLUE,
                error_y=error_bars(by_age),
                customdata=np.stack([by_age["n"], by_age["ci_low"], by_age["ci_high"]], axis=1),
                hovertemplate="Age %{x}<br><b>%{y:.1f}%</b> frequent users<br>95% CI %{customdata[1]:.1f}–"
                              "%{customdata[2]:.1f}%<br>n = %{customdata[0]:,}<extra></extra>"))
            fig.update_xaxes(title="Age group (years)")
            fig.update_yaxes(title="Frequent users (%)", ticksuffix="%", rangemode="tozero")
            show_chart(style_fig(fig, "Frequent use (several times a day+) by age", legend=False))
            small_group_note(hidden)

    mix = au.weighted_crosstab(data, "age_group", "usage_group", "w")
    if not mix.empty:
        mix["age_group"] = mix["age_group"].astype(str)
        mix["usage_group"] = mix["usage_group"].astype(str)
        fig = px.bar(mix, x="percent", y="age_group", color="usage_group", orientation="h",
                     category_orders={"usage_group": au.USAGE_GROUP_ORDER, "age_group": AGE_OPTIONS},
                     color_discrete_sequence=pl.ordinal_colors(len(au.USAGE_GROUP_ORDER)),
                     custom_data=["usage_group", "n"])
        fig.update_traces(marker_line_color=pl.SURFACE, marker_line_width=1.5,
                          hovertemplate="Age %{y}<br>%{customdata[0]}: <b>%{x:.1f}%</b>"
                                        "<br>n = %{customdata[1]:,}<extra></extra>")
        fig.update_layout(barmode="stack")
        fig.update_xaxes(title="Students in the age group (%)", ticksuffix="%", range=[0, 100])
        fig.update_yaxes(title="Age group (years)")
        show_chart(style_fig(fig, "Social media use frequency within each age group", height=360))

    st.markdown("##### Comparison of usage categories")
    table = pd.DataFrame({label: au.weighted_share_by(data, "usage_group", flag, "w")
                          .set_index("usage_group")["percent"] for flag, label in INDICATORS.items()})
    table.insert(0, "Students (n)", data.groupby("usage_group", observed=True).size())
    table = table[table["Students (n)"] >= MIN_GROUP_N]
    if table.empty:
        st.warning("Not enough students in any usage category for this selection.")
    else:
        table.index = table.index.astype(str)
        config = {label: st.column_config.ProgressColumn(label, format="%.1f%%", min_value=0, max_value=100)
                  for label in INDICATORS.values()}
        config["Students (n)"] = st.column_config.NumberColumn("Students (n)", format="%d")
        st.dataframe(table, width="stretch", column_config=config)
        st.caption("Each bar is the share of students in that usage category with the indicator. "
                   "Weighted if survey weights are on.")

    not_available("Nighttime social media use", "The 2023 YRBS has no question about phone or "
                  "social media use at night.")


# --------------------------------------------------------------------------------------
# Section 5: sleep
# --------------------------------------------------------------------------------------
def section_sleep(data: pd.DataFrame) -> None:
    st.subheader("Sleep")
    not_available("Screen time vs sleep scatter plot", "Screen time is not measured, and both "
                  "remaining variables are answer categories, so a point-per-student scatter "
                  "would only show overlapping dots.",
                  "a bubble chart of social media frequency vs sleep, with the average and a trend line")

    d = pd.DataFrame({"sm": data["social_media_code"].astype(float),
                      "sleep": data["sleep_hours_approx"].astype(float), "w": data["w"]}).dropna()
    if len(d) < MIN_GROUP_N:
        st.warning("Too few students answered both the social media and the sleep question in this selection.")
    else:
        cells = au.weighted_crosstab(d, "sm", "sleep", "w")
        means = au.weighted_mean_by(d, "sm", "sleep", "w")
        means = means[means["n"] >= MIN_GROUP_N]
        trend = au.weighted_linear_trend(d["sm"], d["sleep"], d["w"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=cells["sm"], y=cells["sleep"], mode="markers", name="Share of students (bubble size)",
            marker=dict(size=cells["percent"], sizemode="area",
                        sizeref=2.0 * max(cells["percent"].max(), 1) / 40 ** 2, sizemin=3,
                        color=pl.BLUE, opacity=0.45, line=dict(color=pl.SURFACE, width=1)),
            customdata=np.stack([cells["percent"], cells["n"]], axis=1),
            hovertemplate="%{customdata[0]:.1f}% of this usage level sleep %{y} h<br>"
                          "n = %{customdata[1]:,}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=means["sm"], y=means["mean"], mode="lines+markers", name="Average sleep",
            line=dict(color=pl.TEAL, width=2.5), marker=dict(size=8), customdata=means["n"],
            hovertemplate="Average: <b>%{y:.2f} h</b><br>n = %{customdata:,}<extra></extra>"))
        if trend:
            slope, intercept = trend
            xs = np.array([1, 8])
            fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines",
                                     name=f"Linear trend ({slope:+.2f} h per level)",
                                     line=dict(color=pl.INK_2, width=1.5, dash="dash"), hoverinfo="skip"))
        fig.update_xaxes(title="Social media use frequency", tickvals=list(SM_SHORT),
                         ticktext=list(SM_SHORT.values()))
        fig.update_yaxes(title="Sleep on school nights (hours)", tickvals=list(SLEEP_TICKS),
                         ticktext=list(SLEEP_TICKS.values()), range=[3.4, 10.6])
        show_chart(style_fig(fig, "Social media frequency vs hours of sleep", height=470))
        st.caption("Bubble size: share of students at each usage level who report that much sleep "
                   "(columns add up to 100%). The trend line treats the frequency levels as evenly "
                   "spaced, so read it as a rough summary only.")

    c1, c2 = st.columns(2)
    with c1:
        t = au.weighted_share_by(data, "usage_group", "sleep_8plus", "w")
        means = au.weighted_mean_by(data, "usage_group", "sleep_hours_approx", "w")
        t, hidden = drop_small_groups(t.merge(means[["usage_group", "mean"]], on="usage_group", how="left"))
        if t.empty:
            st.warning("Not enough students per usage category.")
        else:
            fig = go.Figure(go.Bar(
                x=t["usage_group"].astype(str), y=t["percent"], marker_color=pl.BLUE, error_y=error_bars(t),
                customdata=np.stack([t["n"], t["mean"]], axis=1),
                hovertemplate="%{x}<br><b>%{y:.1f}%</b> sleep 8+ h<br>Average %{customdata[1]:.2f} h"
                              "<br>n = %{customdata[0]:,}<extra></extra>"))
            fig.update_xaxes(title="Social media usage category")
            fig.update_yaxes(title="Sleeping 8+ hours (%)", ticksuffix="%", rangemode="tozero")
            show_chart(style_fig(fig, "Sleeping 8+ hours by usage category", legend=False))
            small_group_note(hidden)

    with c2:
        d2 = data.assign(group=data["social_media_frequent"].map(
            {1: "Frequent users", 0: "Less frequent / non-users"}))
        mix = au.weighted_crosstab(d2, "group", "sleep_code", "w")
        if mix.empty or mix["group"].nunique() < 2:
            st.warning("Both usage groups are needed for this comparison.")
        else:
            mix["sleep"] = mix["sleep_code"].astype(int).map(SLEEP_SHORT)
            fig = px.bar(mix, x="sleep", y="percent", color="group", barmode="group",
                         category_orders={"sleep": list(SLEEP_SHORT.values()),
                                          "group": ["Less frequent / non-users", "Frequent users"]},
                         color_discrete_map={"Less frequent / non-users": pl.BLUE, "Frequent users": pl.TEAL},
                         custom_data=["group", "n"])
            fig.update_traces(marker_line_color=pl.SURFACE, marker_line_width=1.5,
                              hovertemplate="%{customdata[0]}<br>%{x}: <b>%{y:.1f}%</b>"
                                            "<br>n = %{customdata[1]:,}<extra></extra>")
            fig.update_xaxes(title="Sleep on school nights")
            fig.update_yaxes(title="Students in the group (%)", ticksuffix="%")
            show_chart(style_fig(fig, "Sleep distribution: frequent vs less frequent users"))

    not_available("Nighttime usage vs sleep quality", "The 2023 YRBS measures neither nighttime "
                  "social media use nor sleep quality; only hours of sleep.")


# --------------------------------------------------------------------------------------
# Section 6: mental well-being
# --------------------------------------------------------------------------------------
def two_series_chart(data: pd.DataFrame, group: str, title: str, xtitle: str,
                     tickvals=None, ticktext=None, trend: bool = False) -> None:
    fig = go.Figure()
    hidden_total = 0
    for flag, name, color in [("poor_mental_health", "Poor mental health", pl.BLUE),
                              ("sad_hopeless", "Persistent sadness", pl.TEAL)]:
        t, hidden = drop_small_groups(au.weighted_share_by(data, group, flag, "w"))
        hidden_total = max(hidden_total, hidden)
        if t.empty:
            continue
        x = t[group].astype(float)
        fig.add_trace(go.Scatter(
            x=x, y=t["percent"], mode="lines+markers", name=name, line=dict(color=color, width=2.5),
            marker=dict(size=9), error_y=error_bars(t),
            customdata=np.stack([t["n"], t["ci_low"], t["ci_high"]], axis=1),
            hovertemplate=f"{name}<br><b>%{{y:.1f}}%</b><br>95% CI %{{customdata[1]:.1f}}–"
                          f"%{{customdata[2]:.1f}}%<br>n = %{{customdata[0]:,}}<extra></extra>"))
        if trend and len(t) >= 3:
            slope, intercept = np.polyfit(x, t["percent"], 1, w=np.sqrt(t["n"]))
            xs = np.array([x.min(), x.max()])
            fig.add_trace(go.Scatter(x=xs, y=slope * xs + intercept, mode="lines",
                                     name=f"{name} trend ({slope:+.1f} pp per day)",
                                     line=dict(color=color, width=1.3, dash="dash"), hoverinfo="skip"))
    if not fig.data:
        st.warning("Not enough students per group in this selection.")
        return
    fig.update_xaxes(title=xtitle, tickvals=tickvals, ticktext=ticktext)
    fig.update_yaxes(title="Students with the indicator (%)", ticksuffix="%", rangemode="tozero")
    show_chart(style_fig(fig, title, height=440))
    small_group_note(hidden_total)


def section_wellbeing(data: pd.DataFrame, tests: Dict[str, Dict[str, object]]) -> None:
    st.subheader("Mental well-being")
    not_available("Social media use vs anxiety", "There is no anxiety question in the 2023 YRBS.",
                  "poor mental health and persistent sadness. These are related to anxiety but are "
                  "not anxiety measures")

    c1, c2 = st.columns(2)
    with c1:
        two_series_chart(data, "social_media_code", "Mental health indicators by social media frequency",
                         "Social media use frequency", tickvals=list(SM_SHORT),
                         ticktext=list(SM_SHORT.values()))
    with c2:
        two_series_chart(data, "active_days", "Mental health indicators by physical activity",
                         "Days physically active 60+ min (past week)", tickvals=list(range(8)), trend=True)
    st.caption("Poor mental health: 'not good' most of the time or always (past 30 days). "
               "Persistent sadness: sad or hopeless almost every day for 2+ weeks (past 12 months). "
               "Error bars are approximate 95% confidence intervals.")

    c3, c4 = st.columns([1, 1.15])
    with c3:
        st.markdown("##### Correlation heatmap (Spearman)")
        matrix = correlation_matrix(data)
        if matrix.shape[0] < 2:
            st.warning("Not enough variation in this selection to compute correlations.")
        else:
            fig = pl.correlation_heatmap(matrix, figsize=(6.4, 5.4), annot_size=8)
            st.pyplot(fig, width="stretch")
            plt.close(fig)
            st.caption("Blue = the two variables tend to rise together; red = one rises as the other "
                       "falls. Higher 'Poor mental health' = worse. Each pair uses students who "
                       "answered both questions.")
    with c4:
        st.markdown("##### Statistical summary")
        rows = []
        for key, (label, _, _) in TESTS.items():
            r = tests[key]
            stat = "–" if pd.isna(r["statistic"]) else f"{r['statistic_name']} = {r['statistic']:,.3f}"
            rows.append({"Comparison": label, "Test": r["test"], "n": r["n"], "Statistic": stat,
                         "p-value": au.format_p(r["p_value"]),
                         "Effect size": "–" if pd.isna(r["effect_size"]) else f"{r['effect_size']:.3f}",
                         "Strength": r["effect"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Effect size: Spearman ρ or Cramér's V. Rough guide: below 0.1 negligible, "
                   "0.1–0.3 small, 0.3–0.5 moderate. Tests are unweighted and treat students as "
                   "independent, so p-values are optimistic. With large samples tiny effects can be "
                   "'significant': focus on the strength column.")


# --------------------------------------------------------------------------------------
# Section 7: insights (generated from the filtered data)
# --------------------------------------------------------------------------------------
def build_insights(data: pd.DataFrame, tests: Dict[str, Dict[str, object]]) -> List[str]:
    insights: List[str] = []

    pct, lo, hi, n = au.weighted_share(data["social_media_frequent"], data["w"])
    if n >= MIN_GROUP_N:
        insights.append(f"**{pct:.1f}%** of students in this selection use social media several times a "
                        f"day or more (95% CI {lo:.1f}–{hi:.1f}%, n = {n:,}).")

    r = tests["sm_sleep"]
    if r["n"] >= MIN_GROUP_N and not pd.isna(r["statistic"]):
        insights.append(with_n(au.association_phrase(r, "More frequent social media use", "school-night sleep",
                                                     "**more school-night sleep**", "**less school-night sleep**"),
                               r["n"]))

    is_freq = au.is_level(data["social_media_frequent"], 1)
    is_less = au.is_level(data["social_media_frequent"], 0)
    a = au.weighted_share(data.loc[is_freq, "poor_mental_health"], data.loc[is_freq, "w"])
    b = au.weighted_share(data.loc[is_less, "poor_mental_health"], data.loc[is_less, "w"])
    chi = tests["freq_x_poor_mh"]
    if a[3] >= MIN_GROUP_N and b[3] >= MIN_GROUP_N and not pd.isna(chi["effect_size"]):
        insights.append(f"Poor mental health is reported by **{a[0]:.1f}%** of frequent users and "
                        f"**{b[0]:.1f}%** of less frequent users or non-users (a {a[0] - b[0]:+.1f} "
                        f"percentage-point difference; Cramér's V = {chi['effect_size']:.2f}, "
                        f"conventionally {chi['effect']}).")

    r = tests["active_poor_mh"]
    if r["n"] >= MIN_GROUP_N and not pd.isna(r["statistic"]):
        insights.append(with_n(au.association_phrase(r, "Being active on more days", "poor mental health",
                                                     "reporting **poor mental health more often**",
                                                     "reporting **poor mental health less often**"), r["n"]))

    by_age = drop_small_groups(au.weighted_share_by(data, "age_group", "social_media_frequent", "w"))[0]
    if len(by_age) >= 2:
        top, bottom = by_age.loc[by_age["percent"].idxmax()], by_age.loc[by_age["percent"].idxmin()]
        insights.append(f"Frequent use ranges from **{bottom['percent']:.1f}%** (age {bottom['age_group']}) "
                        f"to **{top['percent']:.1f}%** (age {top['age_group']}) across age groups.")

    matrix = correlation_matrix(data)
    if matrix.shape[0] >= 2:
        pairs = matrix.where(np.tril(np.ones(matrix.shape, dtype=bool), k=-1)).stack().dropna()
        if not pairs.empty:
            (v1, v2) = pairs.abs().idxmax()
            rho = pairs[(v1, v2)]
            insights.append(f"The strongest correlation in the heatmap is between **{v1}** and **{v2}** "
                            f"(ρ = {rho:.2f}, {au.effect_label(rho)}).")
    return insights


def section_insights(data: pd.DataFrame, tests: Dict[str, Dict[str, object]], weighted: bool) -> None:
    st.subheader("Key insights")
    st.caption("Calculated from the current selection "
               f"({'weighted national estimates' if weighted else 'unweighted sample'}). "
               "They describe associations, not causes.")
    insights = build_insights(data, tests)
    if not insights:
        st.warning(f"The selection is too small (fewer than {MIN_GROUP_N} students per comparison) "
                   "to produce reliable insights. Widen the filters.")
    for text in insights:
        st.markdown(f'<div class="insight">{md_bold_to_html(text)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------------------
# Section 8: limitations
# --------------------------------------------------------------------------------------
def section_limitations() -> None:
    st.subheader("Limitations")
    st.markdown(
        "- **Self-reported data.** Students answered a questionnaire; answers may be misremembered "
        "or under- or over-reported.\n"
        "- **Correlation does not prove causation.** The survey is cross-sectional (one point in time), "
        "so it cannot show what came first.\n"
        "- **Other factors** may affect the relationships shown: family, school stress, bullying, "
        "loneliness, health and more. None of these are adjusted for here.\n"
        "- **Findings depend on this dataset.** It covers US high-school students (about 14–18) in 2023. "
        "Social media is measured as *frequency*, not hours. Mental health is measured by single "
        "questions, not clinical scales.\n"
        "- **Survey design.** Weighted percentages estimate national values, but the confidence "
        "intervals and tests are approximate and ignore the survey's clustering.\n"
        "- **Missing answers** are not filled in. Each chart uses the students who answered the "
        "questions it needs.")

    support = pd.DataFrame([
        {"Variable": k.replace("_", " ").capitalize(),
         "Available": {True: "Yes", False: "No", "partial": "Partly"}[v["supported"]],
         "Note": v["note"]} for k, v in dp.VARIABLE_SUPPORT.items()])
    st.markdown("##### What the dataset contains")
    st.dataframe(support, hide_index=True, width="stretch")

    with st.expander("Data source"):
        st.markdown(
            "**Youth Risk Behavior Survey (YRBS) 2023**, national high-school data, published by the U.S. "
            "Centers for Disease Control and Prevention (CDC): "
            "[cdc.gov/yrbs/data](https://www.cdc.gov/yrbs/data/index.html). Cleaned with "
            "`src/data_processing.py`; see `docs/data_dictionary.md` for all columns.")


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    try:
        full = load_data()
    except dp.DataProcessingError as exc:
        st.error("The dataset could not be loaded. What to do:")
        st.code(str(exc), language=None)
        st.stop()

    filters = sidebar()
    data = filter_data(**filters)
    full_view = filter_data(age=tuple(AGE_OPTIONS), sex=tuple(SEX_OPTIONS), grade=tuple(GRADE_OPTIONS),
                            race=tuple(RACE_OPTIONS), weighted=filters["weighted"], **FULL_RANGES)
    is_filtered = len(data) != len(full)

    if data.empty:
        st.warning("No students match the current filters. Widen a filter or press **Reset filters**.")
        st.stop()

    metric_cards(data, full_view, is_filtered)
    st.write("")

    tests = run_tests(data)
    tabs = st.tabs(["Digital habits", "Sleep", "Mental well-being", "Key insights", "Limitations",
                    "AI Predictions & Recommendations"])
    with tabs[0]:
        section_digital(data)
    with tabs[1]:
        section_sleep(data)
    with tabs[2]:
        section_wellbeing(data, tests)
    with tabs[3]:
        section_insights(data, tests, filters["weighted"])
    with tabs[4]:
        section_limitations()
    with tabs[5]:
        st.caption("The sidebar filters do not affect this tab: the model was trained once on the full dataset.")
        render_ai_tab(style_fig, show_chart)


if __name__ == "__main__":  # Streamlit runs the script as __main__; tests can import it safely
    main()
