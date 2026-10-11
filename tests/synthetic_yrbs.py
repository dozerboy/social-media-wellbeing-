"""SYNTHETIC test fixture: random records in the CDC 2023 YRBS fixed-width layout.

These records are randomly generated and are NOT survey data. They exist only so the
automated tests can run the pipeline, notebook and dashboard end to end. They are written
to a temporary folder and never to data/. Results computed from them mean nothing.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np

LINE_LENGTH = 421  # the 2023 file's last field (Q7ORIG) ends at column 421

# 1-based start positions and widths (same as CDC's SAS input program)
POS = {"Q1": (17, 1), "Q2": (18, 1), "Q3": (19, 1), "Q26": (57, 1), "Q76": (107, 1),
       "Q80": (111, 1), "Q84": (115, 1), "Q85": (116, 1), "Q106": (137, 1),
       "QN26": (203, 1), "QN76": (253, 1), "QN80": (257, 1), "QN84": (261, 1), "QN85": (262, 1),
       "WEIGHT": (388, 10), "STRATUM": (398, 3), "PSU": (401, 6), "RACEETH": (414, 2)}
CODES = {"Q1": 7, "Q2": 2, "Q3": 4, "Q26": 2, "Q76": 8, "Q80": 8, "Q84": 5, "Q85": 7, "Q106": 2,
         "RACEETH": 8}
QN_RULES = {"QN26": ("Q26", {"1"}), "QN76": ("Q76", {"6", "7", "8"}), "QN80": ("Q80", {"6", "7", "8"}),
            "QN84": ("Q84", {"4", "5"}), "QN85": ("Q85", {"5", "6", "7"})}
STUDY = ["Q26", "Q76", "Q80", "Q84", "Q85", "Q106"]


def make_line(values: dict) -> str:
    chars = [" "] * LINE_LENGTH
    for name, text in values.items():
        start, width = POS[name]
        text = "" if text is None else str(text)
        text = text.rjust(width)[:width]
        chars[start - 1:start - 1 + width] = list(text)
    return "".join(chars)


def random_record(rng: np.random.Generator, missing_rate: float = 0.05,
                  implied_decimal_weight: bool = False) -> dict:
    rec = {}
    for name, k in CODES.items():
        rec[name] = None if rng.random() < missing_rate and name != "RACEETH" else str(rng.integers(1, k + 1))
    rec["Q1"] = rec["Q1"] or str(rng.integers(3, 8))
    for qn, (q, yes) in QN_RULES.items():
        rec[qn] = None if rec[q] is None else ("1" if rec[q] in yes else "2")
    weight = rng.uniform(0.2, 3.0)
    rec["WEIGHT"] = f"{round(weight * 10_000):d}" if implied_decimal_weight else f"{weight:.4f}"
    rec["STRATUM"] = str(rng.integers(100, 130))
    rec["PSU"] = str(rng.integers(100000, 100060))
    return rec


def make_lines(n: int = 3000, seed: int = 7) -> List[str]:
    """n random records plus four planted problems (see SPECIAL_ROWS)."""
    rng = np.random.default_rng(seed)
    lines = [make_line(random_record(rng, implied_decimal_weight=(i % 10 == 0))) for i in range(n)]

    invalid = random_record(rng)
    invalid.update({"Q80": "9", "QN80": None, "Q85": "8", "QN85": None})   # codes outside CDC's list
    blank_weight = random_record(rng)
    blank_weight["WEIGHT"] = None
    no_answers = random_record(rng)
    for q in STUDY:
        no_answers[q] = None
    for qn in QN_RULES:
        no_answers[qn] = None
    lines += [make_line(invalid), make_line(blank_weight), make_line(no_answers), lines[0]]  # last = duplicate
    return lines


SPECIAL_ROWS = {"invalid_Q80": 1, "invalid_Q85": 1, "blank_weight": 1, "no_study_answers": 1,
                "exact_duplicates": 1}


def write_dat(path: Path, n: int = 3000, seed: int = 7) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(make_lines(n, seed)) + "\n", encoding="latin-1")
    return path
