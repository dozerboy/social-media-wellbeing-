"""Weighted summaries and statistical tests shared by the notebook and the dashboard.

Summary functions take the name of a weight column, so the same code produces weighted
(national) results with ``"weight"`` and unweighted (sample) results with a column of ones.

Test functions all return a dict with the same keys:
    test, x, y, n, statistic, statistic_name, p_value, effect_size, effect_name, effect
The tests are classical, unweighted tests that treat students as independent observations.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Coarser social media groups for comparisons (codes from CDC question Q80).
USAGE_GROUPS = {
    1: "Non-user",
    2: "Less than daily", 3: "Less than daily", 4: "Less than daily",
    5: "About once a day",
    6: "Several times a day",
    7: "Hourly or more", 8: "Hourly or more",
}
USAGE_GROUP_ORDER = ["Non-user", "Less than daily", "About once a day",
                     "Several times a day", "Hourly or more"]


def add_usage_group(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["usage_group"] = pd.Categorical(out["social_media_code"].map(USAGE_GROUPS),
                                        categories=USAGE_GROUP_ORDER, ordered=True)
    return out


def is_level(series: pd.Series, value) -> pd.Series:
    """True where series == value; missing values count as False (safe for filtering)."""
    return series.eq(value).fillna(False).astype(bool)


# --------------------------------------------------------------------------------------
# Weighted summaries
# --------------------------------------------------------------------------------------
def weighted_share(flag: pd.Series, weight: pd.Series) -> Tuple[float, float, float, int]:
    """Weighted % of 1s in a 0/1 column, approximate 95% CI, and n.

    The CI uses Kish's effective sample size, n_eff = (sum w)^2 / sum(w^2), which accounts
    for unequal weights but not for clustering, so it is somewhat too narrow.
    """
    mask = flag.notna() & weight.notna()
    n = int(mask.sum())
    if n == 0:
        return np.nan, np.nan, np.nan, 0
    y = flag[mask].astype(float).to_numpy()
    w = weight[mask].astype(float).to_numpy()
    p = float(np.sum(w * y) / np.sum(w))
    n_eff = w.sum() ** 2 / np.sum(w ** 2)
    se = np.sqrt(p * (1 - p) / n_eff)
    return 100 * p, 100 * max(p - 1.96 * se, 0.0), 100 * min(p + 1.96 * se, 1.0), n


def weighted_share_by(df: pd.DataFrame, group: str, flag: str, wcol: str = "weight") -> pd.DataFrame:
    """weighted_share() for every level of ``group``."""
    rows = []
    for level, g in df.groupby(group, observed=True):
        pct, lo, hi, n = weighted_share(g[flag], g[wcol])
        rows.append({group: level, "percent": pct, "ci_low": lo, "ci_high": hi, "n": n})
    return pd.DataFrame(rows, columns=[group, "percent", "ci_low", "ci_high", "n"])


def weighted_distribution(df: pd.DataFrame, col: str, wcol: str = "weight") -> pd.DataFrame:
    """Weighted % of students in each category of ``col`` (columns: col, percent, n)."""
    d = df[[col, wcol]].dropna()
    if d.empty:
        return pd.DataFrame(columns=[col, "percent", "n"])
    pct = d.groupby(col, observed=True)[wcol].sum() / d[wcol].sum() * 100
    n = d.groupby(col, observed=True).size()
    return pd.DataFrame({"percent": pct, "n": n}).reset_index()


def weighted_crosstab(df: pd.DataFrame, row: str, col: str, wcol: str = "weight") -> pd.DataFrame:
    """Weighted % of each ``col`` category within each ``row`` category (long format)."""
    d = df[[row, col, wcol]].dropna()
    if d.empty:
        return pd.DataFrame(columns=[row, col, "percent", "n"])
    total = d.groupby(row, observed=True)[wcol].transform("sum")
    d = d.assign(share=d[wcol] / total * 100)
    out = d.groupby([row, col], observed=True).agg(percent=("share", "sum"), n=(wcol, "size"))
    return out.reset_index()


def weighted_mean(values: pd.Series, weight: pd.Series) -> float:
    mask = values.notna() & weight.notna()
    if mask.sum() == 0:
        return np.nan
    return float(np.average(values[mask].astype(float), weights=weight[mask].astype(float)))


def weighted_mean_by(df: pd.DataFrame, group: str, value: str, wcol: str = "weight") -> pd.DataFrame:
    rows = []
    for level, g in df.groupby(group, observed=True):
        rows.append({group: level, "mean": weighted_mean(g[value], g[wcol]),
                     "n": int(g[value].notna().sum())})
    return pd.DataFrame(rows, columns=[group, "mean", "n"])


def weighted_median_category(df: pd.DataFrame, col: str, wcol: str = "weight"):
    """Category where the weighted cumulative share first reaches 50% (ordered categories)."""
    dist = weighted_distribution(df, col, wcol)
    if dist.empty:
        return None
    cum = dist["percent"].cumsum().to_numpy()
    return dist[col].iloc[int(np.argmax(cum >= 50))]


def weighted_linear_trend(x: pd.Series, y: pd.Series, w: pd.Series) -> Optional[Tuple[float, float]]:
    """Weighted least-squares line y = slope * x + intercept (descriptive only)."""
    d = pd.DataFrame({"x": x, "y": y, "w": w}).dropna().astype(float)
    if len(d) < 3 or d["x"].nunique() < 2:
        return None
    slope, intercept = np.polyfit(d["x"], d["y"], 1, w=np.sqrt(d["w"]))
    return float(slope), float(intercept)


# --------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------
def effect_label(value: float) -> str:
    """Rough verbal label for |rho|, Cramer's V or rank-biserial r (Cohen, 1988 conventions)."""
    if value is None or pd.isna(value):
        return "n/a"
    a = abs(value)
    return "negligible" if a < 0.1 else "small" if a < 0.3 else "moderate" if a < 0.5 else "large"


def association_phrase(result: Dict[str, object], subject: str, topic: str, positive: str,
                       negative: str) -> str:
    """One plain-language sentence about an association that never overstates a negligible effect.

    association_phrase(r, "More frequent social media use", "sleep", "more sleep", "less sleep") ->
      "More frequent social media use goes with less sleep (small association, Spearman rho = -0.12)."
      "More frequent social media use shows only a negligible association with sleep (Spearman rho = -0.07)."
    """
    value, effect = result["effect_size"], result["effect"]
    if value is None or pd.isna(value):
        return f"The association between {subject.lower()} and {topic} could not be computed for this data."
    stat = f"{result['effect_name']} = {value:.2f}"
    if effect == "negligible":
        return f"{subject} shows only a negligible association with {topic} ({stat})."
    return f"{subject} goes with {positive if value > 0 else negative} ({effect} association, {stat})."


def format_p(p: float) -> str:
    if p is None or pd.isna(p):
        return "n/a"
    if p == 0:
        return "< 1e-300"
    return f"{p:.2e}" if p < 0.001 else f"{p:.4f}"


def _result(test: str, x: str, y: str, n: int, statistic: float, statistic_name: str,
            p_value: float, effect_size: float, effect_name: str, **extra) -> Dict[str, object]:
    out = {"test": test, "x": x, "y": y, "n": int(n), "statistic": statistic,
           "statistic_name": statistic_name, "p_value": p_value, "effect_size": effect_size,
           "effect_name": effect_name, "effect": effect_label(effect_size)}
    out.update(extra)
    return out


def spearman(df: pd.DataFrame, x: str, y: str) -> Dict[str, object]:
    """Spearman rank correlation for two ordered variables (pairwise complete cases)."""
    d = df[[x, y]].dropna().astype(float)
    if len(d) < 3 or d[x].nunique() < 2 or d[y].nunique() < 2:
        return _result("Spearman", x, y, len(d), np.nan, "rho", np.nan, np.nan, "Spearman rho")
    rho, p = stats.spearmanr(d[x], d[y])
    return _result("Spearman", x, y, len(d), float(rho), "rho", float(p), float(rho), "Spearman rho")


def chi_square(df: pd.DataFrame, row: str, col: str) -> Dict[str, object]:
    """Chi-square test of independence (no continuity correction) with Cramer's V."""
    d = df[[row, col]].dropna()
    table = pd.crosstab(d[row], d[col])
    n = int(table.to_numpy().sum())
    if table.shape[0] < 2 or table.shape[1] < 2:
        return _result("Chi-square", row, col, n, np.nan, "chi2", np.nan, np.nan, "Cramer's V",
                       dof=0, min_expected=np.nan, table=table)
    chi2, p, dof, expected = stats.chi2_contingency(table, correction=False)
    v = float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))
    return _result("Chi-square", row, col, n, float(chi2), f"chi2 (df={dof})", float(p), v,
                   "Cramer's V", dof=int(dof), min_expected=float(expected.min()), table=table)


def mann_whitney(df: pd.DataFrame, value: str, group: str, a, b) -> Dict[str, object]:
    """Two-sided Mann-Whitney U. Rank-biserial r > 0 means group ``a`` tends to have HIGHER values."""
    xa = df.loc[is_level(df[group], a), value].dropna().astype(float)
    xb = df.loc[is_level(df[group], b), value].dropna().astype(float)
    label = f"{group} ({a} vs {b})"
    if len(xa) == 0 or len(xb) == 0:
        return _result("Mann-Whitney U", label, value, len(xa) + len(xb), np.nan, "U", np.nan,
                       np.nan, "rank-biserial r", n_a=len(xa), n_b=len(xb))
    u, p = stats.mannwhitneyu(xa, xb, alternative="two-sided")
    r = 2 * u / (len(xa) * len(xb)) - 1
    return _result("Mann-Whitney U", label, value, len(xa) + len(xb), float(u), "U", float(p),
                   float(r), "rank-biserial r", n_a=len(xa), n_b=len(xb),
                   median_a=float(xa.median()), median_b=float(xb.median()),
                   mean_a=float(xa.mean()), mean_b=float(xb.mean()))


def kruskal(df: pd.DataFrame, value: str, group: str) -> Dict[str, object]:
    """Kruskal-Wallis H across the levels of ``group`` with epsilon-squared effect size."""
    d = df[[value, group]].dropna()
    samples = [g[value].astype(float).to_numpy() for _, g in d.groupby(group, observed=True)]
    n, k = len(d), len(samples)
    if k < 2 or n <= k:
        return _result("Kruskal-Wallis", group, value, n, np.nan, "H", np.nan, np.nan,
                       "epsilon-squared")
    h, p = stats.kruskal(*samples)
    eps2 = float((h - k + 1) / (n - k))
    out = _result("Kruskal-Wallis", group, value, n, float(h), f"H (groups={k})", float(p), eps2,
                  "epsilon-squared")
    # epsilon-squared has its own conventions (~0.01 small, ~0.06 medium, ~0.14 large)
    out["effect"] = ("negligible" if eps2 < 0.01 else "small" if eps2 < 0.06
                     else "medium" if eps2 < 0.14 else "large")
    return out


def describe_test(result: Dict[str, object], h0: str, h1: str) -> str:
    """Readable multi-line description of a test result."""
    def num(v, fmt):
        return "n/a" if v is None or pd.isna(v) else format(v, fmt)

    lines = [f"{result['test']}: {result['x']}  vs  {result['y']}",
             f"  H0: {h0}",
             f"  H1: {h1}",
             f"  Sample size (n): {result['n']:,}",
             f"  Test statistic {result['statistic_name']}: {num(result['statistic'], ',.4f')}",
             f"  p-value: {format_p(result['p_value'])}",
             f"  Effect size ({result['effect_name']}): {num(result['effect_size'], '.4f')}"
             f"  [{result['effect']}]"]
    if "min_expected" in result and not pd.isna(result["min_expected"]):
        ok = "OK" if result["min_expected"] >= 5 else "WARNING: below 5, test may be unreliable"
        lines.append(f"  Smallest expected cell count: {result['min_expected']:,.1f} ({ok})")
    if not pd.isna(result["p_value"]):
        lines.append("  Decision at alpha = 0.05: "
                     + ("reject H0" if result["p_value"] < 0.05 else "do not reject H0"))
    return "\n".join(lines)


def spearman_matrix(df: pd.DataFrame, columns: Dict[str, str]) -> pd.DataFrame:
    """Pairwise-complete Spearman correlation matrix with readable labels."""
    data = df[list(columns)].astype(float).rename(columns=columns)
    data = data.loc[:, data.nunique() > 1]
    return data.corr(method="spearman")


CORRELATION_VARIABLES = {
    "age_code": "Age",
    "social_media_code": "Social media frequency",
    "sleep_hours_approx": "Sleep hours",
    "active_days": "Active days",
    "poor_mh_code": "Poor mental health (freq.)",
    "sad_hopeless": "Sad / hopeless",
    "difficulty_concentrating": "Difficulty concentrating",
}
