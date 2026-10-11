"""Shared colours, Matplotlib style and reusable chart functions.

The notebook uses the Matplotlib functions. The dashboard uses the same colours and the
same correlation heatmap function, so both look consistent.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.environ.get("SMW_OUTPUT_DIR", PROJECT_ROOT / "outputs"))
CHARTS_DIR = OUTPUT_DIR / "charts"

# ---- Palette (blue / teal / neutrals) -------------------------------------------------
BLUE = "#2a78d6"     # first series
TEAL = "#1baf7a"     # second series
INK = "#1b1f24"      # titles and values
INK_2 = "#52514e"    # axis titles, secondary text
MUTED = "#898781"    # tick labels, notes
GRID = "#e4e5e8"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"
BLUE_RAMP = ["#b7d3f6", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
# Diverging map for correlations: red (negative) - grey (zero) - blue (positive)
DIVERGING = LinearSegmentedColormap.from_list("red_grey_blue", ["#e34948", "#f0efec", BLUE])
FONT_STACK = ["Inter", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"]


def ordinal_colors(k: int) -> List[str]:
    """k shades of blue, light to dark, for ordered categories."""
    idx = np.linspace(1, len(BLUE_RAMP) - 1, k).round().astype(int)
    return [BLUE_RAMP[i] for i in idx]


def apply_style() -> None:
    """Matplotlib defaults used by every notebook chart."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "figure.dpi": 110, "savefig.dpi": 150,
        "font.family": "sans-serif", "font.sans-serif": FONT_STACK, "font.size": 10.5,
        "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 10.5, "axes.labelcolor": INK_2, "text.color": INK,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "xtick.color": MUTED, "ytick.color": MUTED, "legend.frameon": False,
    })


def save_fig(fig: plt.Figure, name: str) -> Path:
    """Save a figure as outputs/charts/<name>.png and return the path."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    return path


def _ci_errors(t: pd.DataFrame) -> np.ndarray:
    return np.vstack([(t["percent"] - t["ci_low"]).to_numpy(), (t["ci_high"] - t["percent"]).to_numpy()])


# ---- Reusable Matplotlib charts --------------------------------------------------------
def hbar_distribution(dist: pd.DataFrame, label_col: str, title: str, xlabel: str, ylabel: str,
                      figsize: Tuple[float, float] = (9, 5)) -> plt.Figure:
    """Horizontal bars of a weighted distribution (columns: label_col, percent), first row on top."""
    fig, ax = plt.subplots(figsize=figsize)
    labels = dist[label_col].astype(str).tolist()
    ax.barh(labels, dist["percent"], color=BLUE, height=0.6)
    for y, pct in enumerate(dist["percent"]):
        ax.text(pct + 0.4, y, f"{pct:.1f}%", va="center", fontsize=9, color=INK_2)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def share_points(series: Sequence[Tuple[pd.DataFrame, str, str]], x_col: str, title: str,
                 xlabel: str, ylabel: str, connect: bool = False, numeric_x: bool = False,
                 figsize: Tuple[float, float] = (9.5, 5.2)) -> plt.Figure:
    """Dot (or line) chart of weighted percentages with 95% CI error bars.

    series: list of (table from weighted_share_by, legend label, colour). Tables must share x values.
    """
    fig, ax = plt.subplots(figsize=figsize)
    offsets = np.linspace(-0.12, 0.12, len(series)) if len(series) > 1 else [0.0]
    ticks: Optional[List[str]] = None
    for (t, label, color), off in zip(series, offsets):
        if numeric_x:
            x = t[x_col].astype(float).to_numpy() + off
        else:
            ticks = t[x_col].astype(str).tolist()
            x = np.arange(len(t)) + off
        if connect:
            ax.plot(x, t["percent"], color=color, linewidth=2)
        ax.errorbar(x, t["percent"], yerr=_ci_errors(t), fmt="o", color=color, ecolor=color,
                    elinewidth=1.2, capsize=3, markersize=7, label=label)
    if not numeric_x and ticks is not None:
        ax.set_xticks(np.arange(len(ticks)))
        ax.set_xticklabels(ticks, rotation=30, ha="right")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(bottom=0)
    ax.grid(axis="x", visible=False)
    if len(series) > 1:
        ax.legend(loc="best")
    fig.tight_layout()
    return fig


def bar_with_ci(t: pd.DataFrame, x_col: str, title: str, xlabel: str, ylabel: str,
                ylim: Optional[Tuple[float, float]] = None,
                figsize: Tuple[float, float] = (8, 4.8)) -> plt.Figure:
    """Vertical bars of weighted percentages with 95% CI error bars."""
    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(t))
    ax.bar(x, t["percent"], color=BLUE, width=0.6)
    ax.errorbar(x, t["percent"], yerr=_ci_errors(t), fmt="none", ecolor=INK_2, elinewidth=1.2, capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels(t[x_col].astype(str))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    if ylim:
        ax.set_ylim(*ylim)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def stacked_100(wide: pd.DataFrame, title: str, xlabel: str, ylabel: str, legend_title: str,
                figsize: Tuple[float, float] = (10, 5.5)) -> plt.Figure:
    """100% stacked horizontal bars. Rows of ``wide`` are bars, columns are ordered segments."""
    fig, ax = plt.subplots(figsize=figsize)
    left = np.zeros(len(wide))
    for color, cat in zip(ordinal_colors(wide.shape[1]), wide.columns):
        ax.barh(wide.index.astype(str), wide[cat], left=left, color=color, edgecolor=SURFACE,
                linewidth=1.5, height=0.65, label=str(cat))
        left += wide[cat].fillna(0).to_numpy()
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlim(0, 100)
    ax.grid(False)
    ax.legend(title=legend_title, bbox_to_anchor=(1.01, 1), loc="upper left")
    fig.tight_layout()
    return fig


def grouped_bars(wide: pd.DataFrame, title: str, xlabel: str, ylabel: str,
                 colors: Iterable[str] = (BLUE, TEAL), figsize: Tuple[float, float] = (9, 5)) -> plt.Figure:
    """Side-by-side bars: rows of ``wide`` on the x-axis, one bar per column."""
    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(wide))
    k = wide.shape[1]
    width = 0.8 / k
    for i, (col, color) in enumerate(zip(wide.columns, colors)):
        ax.bar(x + (i - (k - 1) / 2) * width, wide[col], width, color=color, edgecolor=SURFACE,
               linewidth=1.5, label=str(col))
    ax.set_xticks(x)
    ax.set_xticklabels(wide.index.astype(str))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.grid(axis="x", visible=False)
    ax.legend(loc="best")
    fig.tight_layout()
    return fig


def correlation_heatmap(matrix: pd.DataFrame, title: Optional[str] = None,
                        figsize: Tuple[float, float] = (8.5, 7), annot_size: int = 9) -> plt.Figure:
    """Lower-triangle heatmap of a correlation matrix on a fixed -1..1 diverging scale."""
    fig, ax = plt.subplots(figsize=figsize)
    lower = matrix.iloc[1:, :-1]          # drop the always-empty first row and last column
    mask = np.triu(np.ones_like(lower, dtype=bool), k=1)
    sns.heatmap(lower, mask=mask, cmap=DIVERGING, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
                annot_kws={"size": annot_size}, linewidths=1.5, linecolor=SURFACE, square=True,
                cbar_kws={"label": "Spearman rho", "shrink": 0.75}, ax=ax)
    if title:
        ax.set_title(title)
    ax.grid(False)
    ax.tick_params(length=0)
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    return fig
