"""Loading, validation and preprocessing for the 2023 national YRBS (CDC).

Pipeline
--------
1. ``convert_raw_to_csv``  CDC fixed-width ``.dat`` file -> ``data/interim/yrbs2023_selected_raw.csv``
   (only the columns this project uses; values are the untouched CDC answer codes)
2. ``load_raw_csv``        reads that CSV with pandas (every column as text)
3. ``validate_columns``    checks that the expected columns exist
4. ``audit_data``          missing values, duplicates, data types, invalid codes, outliers
5. ``clean_data``          turns CDC codes into labelled, analysis-ready columns
6. ``save_cleaned_data``   writes ``data/processed/cleaned_data.csv`` (+ data dictionary)

The raw ``.dat`` file is only ever opened read-only and is never modified.

Run from the project root:
    python -m src.data_processing
    python -m src.data_processing --raw "D:/downloads/XXH2023_YRBS_Data.dat"

Column positions and answer codes come from CDC's own programs, stored in
``data/raw/documentation/2023XXH-SAS-Input-Program.sas`` and
``data/raw/documentation/2023XXH-Formats-Program.sas``.
"""
from __future__ import annotations

import argparse
import difflib
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The SMW_DATA_DIR / SMW_REPORT_DIR environment variables let the automated tests run the
# whole project on a temporary folder. Normal use never sets them.
DATA_DIR = Path(os.environ.get("SMW_DATA_DIR", PROJECT_ROOT / "data"))
REPORT_DIR = Path(os.environ.get("SMW_REPORT_DIR", PROJECT_ROOT / "report"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

RAW_DAT_FILE = RAW_DIR / "XXH2023_YRBS_Data.dat"
INTERIM_CSV_FILE = INTERIM_DIR / "yrbs2023_selected_raw.csv"
CLEANED_CSV_FILE = PROCESSED_DIR / "cleaned_data.csv"
DICTIONARY_CSV_FILE = PROCESSED_DIR / "data_dictionary.csv"
QUALITY_REPORT_FILE = REPORT_DIR / "data_quality_report.json"

DATA_PAGE_URL = "https://www.cdc.gov/yrbs/data/index.html"
DAT_URL = "https://www.cdc.gov/yrbs/files/2023/XXH2023_YRBS_Data.dat"

# Sample size published in MMWR Suppl 2024;73(4) for the 2023 national YRBS.
PUBLISHED_SAMPLE_SIZE = 20_103


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------
class DataProcessingError(Exception):
    """Base class for every error raised by this module."""


class DataFileNotFoundError(DataProcessingError, FileNotFoundError):
    """The expected data file does not exist."""


class DataFileError(DataProcessingError):
    """The file exists but is not usable (empty, a web page, wrong layout, ...)."""


class MissingColumnsError(DataProcessingError):
    """One or more expected columns are absent from a DataFrame."""


# --------------------------------------------------------------------------------------
# Raw file layout (from CDC's 2023XXH SAS Input Program)
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RawField:
    name: str
    start: int  # 1-based column, exactly as written after "@" in the SAS program
    width: int
    cdc_label: str


RAW_FIELDS: List[RawField] = [
    RawField("Q1", 17, 1, "How old are you"),
    RawField("Q2", 18, 1, "What is your sex"),
    RawField("Q3", 19, 1, "In what grade are you"),
    RawField("Q26", 57, 1, "Sad or hopeless"),
    RawField("Q76", 107, 1, "Physical activity >= 5 days"),
    RawField("Q80", 111, 1, "Social media"),
    RawField("Q84", 115, 1, "Current mental health"),
    RawField("Q85", 116, 1, "Hours of sleep on school night"),
    RawField("Q106", 137, 1, "Difficulty concentrating"),
    RawField("QN26", 203, 1, "Felt sad or hopeless"),
    RawField("QN76", 253, 1, "Were physically active at least 60 minutes per day on 5 or more days"),
    RawField("QN80", 257, 1, "Used social media several times a day"),
    RawField("QN84", 261, 1, "Reported that their mental health was most of the time or always not good"),
    RawField("QN85", 262, 1, "Got 8 or more hours of sleep"),
    RawField("WEIGHT", 388, 10, "Overall Analysis Weight"),  # SAS informat 10.4
    RawField("STRATUM", 398, 3, "Sampling Strata"),
    RawField("PSU", 401, 6, "Primary Sampling Unit"),
    RawField("RACEETH", 414, 2, "Race/Ethnicity"),
]
RAW_FIELD_NAMES = [f.name for f in RAW_FIELDS]
WEIGHT_IMPLIED_DECIMALS = 4  # SAS informat "10.4"

# Columns added by convert_raw_to_csv
ID_COLUMNS = ["row_id", "is_duplicate_record"]
EXPECTED_RAW_COLUMNS = ID_COLUMNS + RAW_FIELD_NAMES

# Valid answer codes (from CDC's 2023XXH Formats Program). Anything else is a data error.
VALID_CODES: Dict[str, set] = {
    "Q1": set("1234567"),
    "Q2": set("12"),
    "Q3": set("12345"),
    "Q26": set("12"),
    "Q76": set("12345678"),
    "Q80": set("12345678"),
    "Q84": set("12345"),
    "Q85": set("1234567"),
    "Q106": set("12"),
    "RACEETH": set("12345678"),
    "QN26": set("12"),
    "QN76": set("12"),
    "QN80": set("12"),
    "QN84": set("12"),
    "QN85": set("12"),
}
CODE_COLUMNS = list(VALID_CODES)

# CDC's pre-computed QN indicators (1 = yes, 2 = no) and the rule that should reproduce
# them from the raw answer. Used only as a consistency check on our own recoding.
QN_RULES: Dict[str, Tuple[str, set]] = {
    "QN26": ("Q26", {"1"}),
    "QN76": ("Q76", {"6", "7", "8"}),
    "QN80": ("Q80", {"6", "7", "8"}),
    "QN84": ("Q84", {"4", "5"}),
    "QN85": ("Q85", {"5", "6", "7"}),
}

# --------------------------------------------------------------------------------------
# Value labels (from CDC's 2023XXH Formats Program)
# --------------------------------------------------------------------------------------
AGE_LABELS = {
    1: "12 years old or younger",
    2: "13 years old",
    3: "14 years old",
    4: "15 years old",
    5: "16 years old",
    6: "17 years old",
    7: "18 years old or older",
}
# Age groups as used in CDC's MMWR reports on the 2023 YRBS.
AGE_GROUPS = {1: "14 or younger", 2: "14 or younger", 3: "14 or younger",
              4: "15", 5: "16", 6: "17", 7: "18 or older"}
AGE_GROUP_ORDER = ["14 or younger", "15", "16", "17", "18 or older"]
SEX_LABELS = {1: "Female", 2: "Male"}
GRADE_LABELS = {1: "9th grade", 2: "10th grade", 3: "11th grade", 4: "12th grade",
                5: "Ungraded or other grade"}
RACE_LABELS = {
    1: "Am Indian/Alaska Native",
    2: "Asian",
    3: "Black or African American",
    4: "Native Hawaiian/Other PI",
    5: "White",
    6: "Hispanic/Latino",
    7: "Multiple - Hispanic",
    8: "Multiple - Non-Hispanic",
}
SOCIAL_MEDIA_LABELS = {
    1: "I do not use social media",
    2: "A few times a month",
    3: "About once a week",
    4: "A few times a week",
    5: "About once a day",
    6: "Several times a day",
    7: "About once an hour",
    8: "More than once an hour",
}
SLEEP_LABELS = {1: "4 or less hours", 2: "5 hours", 3: "6 hours", 4: "7 hours",
                5: "8 hours", 6: "9 hours", 7: "10 or more hours"}
# Bottom/top-coded approximation: "4 or less" -> 4, "10 or more" -> 10.
SLEEP_HOURS_APPROX = {1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10}
POOR_MH_LABELS = {1: "Never", 2: "Rarely", 3: "Sometimes", 4: "Most of the time", 5: "Always"}

# (category order, is the order meaningful?)
CATEGORY_ORDERS: Dict[str, Tuple[List[str], bool]] = {
    "age_label": (list(AGE_LABELS.values()), True),
    "age_group": (AGE_GROUP_ORDER, True),
    "sex": (list(SEX_LABELS.values()), False),
    "grade_label": (list(GRADE_LABELS.values()), False),
    "race_ethnicity": (list(RACE_LABELS.values()), False),
    "social_media_freq": (list(SOCIAL_MEDIA_LABELS.values()), True),
    "sleep_hours_cat": (list(SLEEP_LABELS.values()), True),
    "poor_mh_frequency": (list(POOR_MH_LABELS.values()), True),
}

# --------------------------------------------------------------------------------------
# Cleaned dataset: columns, types and dictionary
# --------------------------------------------------------------------------------------
INT_COLUMNS = ["row_id", "age_code", "grade_code", "social_media_code", "sleep_code",
               "sleep_hours_approx", "active_days", "poor_mh_code", "stratum", "psu"]
FLAG_COLUMNS = ["social_media_frequent", "sleep_8plus", "active_5plus", "poor_mental_health",
                "sad_hopeless", "difficulty_concentrating"]
FLOAT_COLUMNS = ["weight"]

DATA_DICTIONARY: List[Dict[str, str]] = [
    {"column": "row_id", "source": "line number in .dat", "type": "integer",
     "values": "1..N", "description": "Row position in the CDC file (the file has no respondent ID)."},
    {"column": "age_code", "source": "Q1", "type": "integer (ordinal)", "values": "1-7",
     "description": "CDC answer code for 'How old are you'."},
    {"column": "age_label", "source": "Q1", "type": "ordered category",
     "values": "; ".join(AGE_LABELS.values()), "description": "Age in years as answered."},
    {"column": "age_group", "source": "Q1", "type": "ordered category",
     "values": "; ".join(AGE_GROUP_ORDER),
     "description": "Age grouped as in CDC MMWR reports (12, 13 and 14 merged)."},
    {"column": "sex", "source": "Q2", "type": "category", "values": "Female; Male",
     "description": "'What is your sex'."},
    {"column": "grade_code", "source": "Q3", "type": "integer", "values": "1-5",
     "description": "CDC answer code for 'In what grade are you' (5 = ungraded/other)."},
    {"column": "grade_label", "source": "Q3", "type": "category",
     "values": "; ".join(GRADE_LABELS.values()), "description": "School grade."},
    {"column": "race_ethnicity", "source": "RACEETH", "type": "category",
     "values": "; ".join(RACE_LABELS.values()), "description": "CDC-derived race/ethnicity."},
    {"column": "social_media_code", "source": "Q80", "type": "integer (ordinal)", "values": "1-8",
     "description": "CDC answer code for how often the student uses social media."},
    {"column": "social_media_freq", "source": "Q80", "type": "ordered category",
     "values": "; ".join(SOCIAL_MEDIA_LABELS.values()),
     "description": "Frequency of social media use. This is FREQUENCY, not hours per day."},
    {"column": "social_media_frequent", "source": "Q80 (checked against QN80)", "type": "0/1",
     "values": "1 = several times a day or more often",
     "description": "Frequent social media use, same cut-off as CDC's QN80."},
    {"column": "sleep_code", "source": "Q85", "type": "integer (ordinal)", "values": "1-7",
     "description": "CDC answer code for hours of sleep on an average school night."},
    {"column": "sleep_hours_cat", "source": "Q85", "type": "ordered category",
     "values": "; ".join(SLEEP_LABELS.values()), "description": "Hours of sleep on a school night."},
    {"column": "sleep_hours_approx", "source": "Q85", "type": "integer", "values": "4-10",
     "description": "Approximate hours (bottom-coded at 4, top-coded at 10). For plots/correlation only."},
    {"column": "sleep_8plus", "source": "Q85 (checked against QN85)", "type": "0/1",
     "values": "1 = 8 or more hours", "description": "Got 8+ hours of sleep on a school night."},
    {"column": "active_days", "source": "Q76", "type": "integer", "values": "0-7",
     "description": "Days in the past 7 physically active for 60+ minutes in total."},
    {"column": "active_5plus", "source": "Q76 (checked against QN76)", "type": "0/1",
     "values": "1 = 5 or more days", "description": "Physically active 60+ minutes on 5+ days."},
    {"column": "poor_mh_code", "source": "Q84", "type": "integer (ordinal)", "values": "1-5",
     "description": "CDC answer code: in the past 30 days, how often mental health was not good. "
                    "HIGHER = WORSE."},
    {"column": "poor_mh_frequency", "source": "Q84", "type": "ordered category",
     "values": "; ".join(POOR_MH_LABELS.values()),
     "description": "How often mental health was not good in the past 30 days."},
    {"column": "poor_mental_health", "source": "Q84 (checked against QN84)", "type": "0/1",
     "values": "1 = most of the time or always",
     "description": "Poor mental health most of the time or always (CDC's QN84 definition)."},
    {"column": "sad_hopeless", "source": "Q26 (checked against QN26)", "type": "0/1",
     "values": "1 = yes", "description": "Felt sad or hopeless almost every day for 2+ weeks in a row "
                                         "in the past 12 months."},
    {"column": "difficulty_concentrating", "source": "Q106", "type": "0/1", "values": "1 = yes",
     "description": "CDC label 'Difficulty concentrating'. Check the exact question wording in the "
                    "2023 questionnaire before interpreting."},
    {"column": "weight", "source": "WEIGHT", "type": "float", "values": "> 0",
     "description": "CDC overall analysis weight. Use for national (weighted) estimates."},
    {"column": "stratum", "source": "STRATUM", "type": "integer", "values": "",
     "description": "Sampling stratum (complex survey design)."},
    {"column": "psu", "source": "PSU", "type": "integer", "values": "",
     "description": "Primary sampling unit (complex survey design)."},
]
CLEANED_COLUMNS = [entry["column"] for entry in DATA_DICTIONARY]

# Columns that represent a study variable; a row with all of them missing is unusable.
STUDY_COLUMNS = ["social_media_code", "sleep_code", "active_days", "poor_mh_code",
                 "sad_hopeless", "difficulty_concentrating"]

# --------------------------------------------------------------------------------------
# What the dataset can and cannot support
# --------------------------------------------------------------------------------------
VARIABLE_SUPPORT: Dict[str, Dict[str, object]] = {
    "age": {"supported": True, "columns": ["age_label", "age_group"],
            "note": "High-school students only (about 14-18); not adults."},
    "daily_social_media_usage": {"supported": "partial",
                                 "columns": ["social_media_freq", "social_media_frequent"],
                                 "note": "How OFTEN students use social media, not hours per day."},
    "screen_time": {"supported": False, "columns": [],
                    "note": "No screen-time item in the 2023 national YRBS file."},
    "nighttime_social_media_usage": {"supported": False, "columns": [],
                                     "note": "Not asked in the 2023 national YRBS."},
    "sleep_duration": {"supported": True, "columns": ["sleep_hours_cat", "sleep_8plus"],
                       "note": "School nights only, in 1-hour bands (<=4 and 10+ are open-ended)."},
    "sleep_quality": {"supported": False, "columns": [],
                      "note": "Not asked in the 2023 national YRBS."},
    "physical_activity": {"supported": True, "columns": ["active_days", "active_5plus"],
                          "note": "Days active 60+ minutes in the past 7 days."},
    "self_reported_anxiety": {"supported": False, "columns": [],
                              "note": "No anxiety-specific item. Related (not equivalent) measures: "
                                      "poor_mental_health, sad_hopeless, difficulty_concentrating."},
    "mental_health_wellbeing": {"supported": True,
                                "columns": ["poor_mh_frequency", "poor_mental_health",
                                            "sad_hopeless", "difficulty_concentrating"],
                                "note": "Self-reported frequency of poor mental health and "
                                        "persistent sadness/hopelessness."},
}

# Research analyses: the columns each needs, or None + reason when the data cannot support it.
ANALYSES: Dict[str, Dict[str, object]] = {
    "social_media_distribution": {
        "columns": ["social_media_freq"], "reason": ""},
    "screen_time_analysis": {
        "columns": None, "reason": "Screen time is not in the 2023 national YRBS."},
    "social_media_vs_sleep_duration": {
        "columns": ["social_media_freq", "sleep_hours_cat"], "reason": ""},
    "nighttime_use_vs_sleep_quality": {
        "columns": None, "reason": "Neither nighttime use nor sleep quality is measured."},
    "physical_activity_vs_wellbeing": {
        "columns": ["active_days", "poor_mh_frequency", "sad_hopeless"], "reason": ""},
    "social_media_by_age_group": {
        "columns": ["age_group", "social_media_freq"], "reason": ""},
    "social_media_vs_anxiety": {
        "columns": None,
        "reason": "No anxiety item; use 'social_media_vs_mental_health' and label it accordingly."},
    "social_media_vs_mental_health": {
        "columns": ["social_media_freq", "poor_mh_frequency", "sad_hopeless",
                    "difficulty_concentrating"], "reason": ""},
    "correlation_matrix": {
        "columns": ["age_code", "social_media_code", "sleep_code", "active_days", "poor_mh_code",
                    "sad_hopeless", "difficulty_concentrating"], "reason": ""},
}


def analysis_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Table of which research analyses can run on ``df`` and, if not, why."""
    rows = []
    for name, spec in ANALYSES.items():
        columns = spec["columns"]
        if columns is None:
            rows.append({"analysis": name, "available": False, "reason": spec["reason"]})
            continue
        missing = [c for c in columns if c not in df.columns]
        empty = [c for c in columns if c in df.columns and df[c].notna().sum() == 0]
        if missing or empty:
            reason = "; ".join(filter(None, [
                f"missing columns: {missing}" if missing else "",
                f"columns with no data: {empty}" if empty else "",
            ]))
            rows.append({"analysis": name, "available": False, "reason": reason})
        else:
            rows.append({"analysis": name, "available": True, "reason": ""})
    return pd.DataFrame(rows)


def is_analysis_supported(name: str, df: Optional[pd.DataFrame] = None) -> bool:
    """True if ``name`` is supported by the dataset (and by ``df``'s columns, if given)."""
    if name not in ANALYSES:
        raise KeyError(f"Unknown analysis '{name}'. Known analyses: {sorted(ANALYSES)}")
    if ANALYSES[name]["columns"] is None:
        return False
    if df is None:
        return True
    table = analysis_availability(df)
    return bool(table.loc[table["analysis"] == name, "available"].iloc[0])


# --------------------------------------------------------------------------------------
# File checks
# --------------------------------------------------------------------------------------
def _similar_files(path: Path) -> List[str]:
    folder = path.parent
    if not folder.is_dir():
        return []
    stem = path.stem.lower()
    hits = [p.name for p in folder.iterdir()
            if p.is_file() and ("yrbs" in p.name.lower() or p.stem.lower() == stem)]
    return sorted(hits)


def _raw_missing_message(path: Path) -> str:
    lines = [f"Raw data file not found: {path}", ""]
    if not path.parent.exists():
        lines.append(f"(The folder {path.parent} does not exist either.)")
    similar = _similar_files(path)
    if similar:
        lines.append(f"Files in {path.parent} that look related: {', '.join(similar)}")
        lines.append("If one of them is the data file, rename it or pass it with --raw.")
    lines += [
        "",
        "The 2023 national YRBS data must be downloaded from CDC first:",
        "  1. Run:  python -m src.download_data",
        "  2. If CDC blocks the scripted download, open this page in a web browser:",
        f"       {DATA_PAGE_URL}",
        "     find '2023' national data, click 'ASCII', and save the file as:",
        f"       {RAW_DAT_FILE}",
        "  3. Or point to a file elsewhere:",
        '       python -m src.data_processing --raw "C:/path/to/XXH2023_YRBS_Data.dat"',
    ]
    return "\n".join(lines)


def check_raw_file(path: Path) -> None:
    """Raise a helpful error if ``path`` is not a plausible YRBS 2023 ASCII data file."""
    path = Path(path)
    if not path.exists():
        raise DataFileNotFoundError(_raw_missing_message(path))
    if path.is_dir():
        raise DataFileError(f"{path} is a folder, not a file. Pass the path to "
                            f"XXH2023_YRBS_Data.dat inside it.")
    if path.stat().st_size == 0:
        raise DataFileError(f"{path} is empty (0 bytes). Delete it and download it again "
                            f"from {DATA_PAGE_URL}")
    with path.open("rb") as fh:
        head = fh.read(512).lstrip().lower()
    if head.startswith((b"<html", b"<!doctype", b"<?xml", b"<head")):
        raise DataFileError(
            f"{path} is a web page, not the data file (probably CDC's 'Access Denied' page "
            f"from a blocked download). Delete it and download the ASCII file manually from "
            f"{DATA_PAGE_URL}")
    if head.startswith((b"pk\x03\x04", b"%pdf")):
        raise DataFileError(
            f"{path} looks like a ZIP or PDF file. This project needs the ASCII (.dat) "
            f"file, not the Access (.zip) download.")


# --------------------------------------------------------------------------------------
# Step 1: fixed-width .dat -> CSV
# --------------------------------------------------------------------------------------
def read_fixed_width(path: Path = RAW_DAT_FILE) -> pd.DataFrame:
    """Read the selected fields from the CDC fixed-width file. Values stay as raw text codes."""
    path = Path(path)
    check_raw_file(path)

    with path.open("r", encoding="latin-1", newline=None) as fh:  # read-only
        lines = [line.rstrip("\r\n") for line in fh]
    lines = [line for line in lines if line.strip()]
    if not lines:
        raise DataFileError(f"{path} contains only blank lines.")

    min_len = max(f.start - 1 + f.width for f in RAW_FIELDS)
    too_short = sum(len(line) < min_len for line in lines)
    if too_short > len(lines) / 2:
        raise DataFileError(
            f"{too_short:,} of {len(lines):,} lines in {path} are shorter than {min_len} "
            f"characters. This does not match the 2023 national YRBS layout; check that you "
            f"downloaded the 2023 national ASCII file (XXH2023_YRBS_Data.dat).")

    columns = {}
    for field in RAW_FIELDS:
        lo, hi = field.start - 1, field.start - 1 + field.width
        columns[field.name] = [line[lo:hi].strip() for line in lines]

    df = pd.DataFrame(columns)
    df = df.where(df.ne(""))  # blank field -> missing
    df.insert(0, "row_id", np.arange(1, len(df) + 1))
    # Exact duplicate of a whole record (all ~420 characters), not just of the selected fields.
    df.insert(1, "is_duplicate_record", pd.Series(lines).duplicated(keep="first").to_numpy())
    logger.info("Read %s records from %s", f"{len(df):,}", path)
    return df


def convert_raw_to_csv(raw_path: Path = RAW_DAT_FILE, csv_path: Path = INTERIM_CSV_FILE,
                       overwrite: bool = False) -> Path:
    """Write the selected raw fields to CSV. Skips the work if an up-to-date CSV exists."""
    raw_path, csv_path = Path(raw_path), Path(csv_path)
    check_raw_file(raw_path)
    if (csv_path.exists() and not overwrite
            and csv_path.stat().st_mtime >= raw_path.stat().st_mtime):
        logger.info("Using existing extract %s (pass --force to rebuild)", csv_path)
        return csv_path
    df = read_fixed_width(raw_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    logger.info("Wrote raw extract to %s", csv_path)
    return csv_path


# --------------------------------------------------------------------------------------
# Step 2: load CSV
# --------------------------------------------------------------------------------------
def _to_bool(series: pd.Series) -> pd.Series:
    mapped = series.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False, "1": True, "0": False})
    return mapped.fillna(False).astype(bool)


def load_raw_csv(path: Path = INTERIM_CSV_FILE) -> pd.DataFrame:
    """Load the raw-extract CSV with pandas. Every survey column is read as text."""
    path = Path(path)
    if not path.exists():
        raise DataFileNotFoundError(
            f"CSV file not found: {path}\n"
            f"Create it from the CDC .dat file with:  python -m src.data_processing\n"
            f"(the .dat file is expected at {RAW_DAT_FILE})")
    if path.is_dir():
        raise DataFileError(f"{path} is a folder, not a CSV file.")
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=True)
    except pd.errors.EmptyDataError as exc:
        raise DataFileError(f"{path} is empty. Rebuild it with "
                            f"'python -m src.data_processing --force'.") from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataFileError(f"{path} could not be parsed as CSV ({exc}). Rebuild it with "
                            f"'python -m src.data_processing --force'.") from exc
    if df.empty:
        raise DataFileError(f"{path} has a header but no rows.")
    if "row_id" in df.columns:
        df["row_id"] = pd.to_numeric(df["row_id"], errors="coerce").astype("Int64")
    if "is_duplicate_record" in df.columns:
        df["is_duplicate_record"] = _to_bool(df["is_duplicate_record"])
    logger.info("Loaded %s rows x %s columns from %s", f"{len(df):,}", df.shape[1], path)
    return df


# --------------------------------------------------------------------------------------
# Step 3: column validation
# --------------------------------------------------------------------------------------
def validate_columns(df: pd.DataFrame, expected: Iterable[str] = EXPECTED_RAW_COLUMNS,
                     strict: bool = True) -> List[str]:
    """Check that every expected column exists.

    Returns the list of missing columns. With ``strict=True`` (default) a
    ``MissingColumnsError`` is raised instead, with close-match suggestions.
    """
    expected = list(expected)
    present = list(df.columns)
    missing = [c for c in expected if c not in present]
    if missing and strict:
        lower_map = {c.lower(): c for c in present}
        hints = []
        for col in missing:
            if col.lower() in lower_map:
                hints.append(f"  '{col}': found '{lower_map[col.lower()]}' (different case)")
                continue
            close = difflib.get_close_matches(col, present, n=3, cutoff=0.6)
            if close:
                hints.append(f"  '{col}': did you mean {close}?")
        message = [f"{len(missing)} expected column(s) missing: {missing}",
                   f"Columns present ({len(present)}): {present}"]
        if hints:
            message += ["Possible matches:"] + hints
        raise MissingColumnsError("\n".join(message))
    return missing


# --------------------------------------------------------------------------------------
# Step 4: audit
# --------------------------------------------------------------------------------------
def _normalise_code(value):
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if text == "":
        return np.nan
    if text.isdigit():
        return str(int(text))  # "05" -> "5"
    return text


def normalise_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Copy of ``df`` with code columns stripped and leading zeros removed."""
    out = df.copy()
    for col in CODE_COLUMNS:
        if col in out.columns:
            out[col] = out[col].map(_normalise_code)
    return out


def parse_implied_decimal(series: pd.Series, decimals: int) -> pd.Series:
    """Parse numbers stored with a SAS 'w.d' informat.

    SAS reads ``10.4`` values as-is when they contain a decimal point and divides by
    10**4 when they do not. Non-numeric text becomes NaN.
    """
    text = series.map(lambda v: np.nan if pd.isna(v) else str(v).strip())
    numeric = pd.to_numeric(text, errors="coerce").astype(float)
    has_point = text.map(lambda v: isinstance(v, str) and "." in v).astype(bool)
    return numeric.where(has_point, numeric / (10 ** decimals))


def check_qn_consistency(codes: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Compare our recoding rules with CDC's own QN indicator variables."""
    results = {}
    for qn, (q, yes_codes) in QN_RULES.items():
        both = codes[q].notna() & codes[qn].notna()
        n = int(both.sum())
        if n == 0:
            results[qn] = {"compared_rows": 0, "agreement": float("nan")}
            continue
        ours = codes.loc[both, q].isin(yes_codes)
        cdc = codes.loc[both, qn].eq("1")
        results[qn] = {"compared_rows": n, "agreement": round(float((ours == cdc).mean()), 4)}
    return results


def audit_data(raw_df: pd.DataFrame) -> Dict[str, object]:
    """Data-quality checks on the raw extract. Does not modify ``raw_df``."""
    validate_columns(raw_df, EXPECTED_RAW_COLUMNS)
    codes = normalise_codes(raw_df)
    n = len(codes)
    warnings: List[str] = []

    # Missing values
    missing = {c: {"count": int(codes[c].isna().sum()),
                   "percent": round(100 * float(codes[c].isna().mean()), 2)}
               for c in RAW_FIELD_NAMES}

    # Invalid codes ("** Data Error **" in CDC's formats)
    invalid = {}
    for col, valid in VALID_CODES.items():
        bad = codes[col].notna() & ~codes[col].isin(valid)
        invalid[col] = {"count": int(bad.sum()),
                        "examples": sorted(codes.loc[bad, col].astype(str).unique().tolist())[:5]}

    # Duplicates
    full_dups = int(raw_df["is_duplicate_record"].sum())
    selected_dups = int(codes[RAW_FIELD_NAMES].duplicated().sum())
    if full_dups:
        warnings.append(f"{full_dups} exact duplicate full records found; they will be removed.")

    # Survey weight: invalid values and outliers (reported, not removed)
    weight = parse_implied_decimal(codes["WEIGHT"], WEIGHT_IMPLIED_DECIMALS)
    non_numeric = int((codes["WEIGHT"].notna() & weight.isna()).sum())
    non_positive = int((weight <= 0).sum())
    w = weight[weight > 0]
    weight_summary: Dict[str, object] = {"non_numeric": non_numeric, "non_positive": non_positive,
                                         "missing": int(codes["WEIGHT"].isna().sum())}
    if len(w):
        q1, q3 = w.quantile([0.25, 0.75])
        iqr = q3 - q1
        weight_summary.update({
            "min": round(float(w.min()), 4), "median": round(float(w.median()), 4),
            "max": round(float(w.max()), 4), "mean": round(float(w.mean()), 4),
            "max_to_median_ratio": round(float(w.max() / w.median()), 2),
            "iqr_outliers_high": int((w > q3 + 1.5 * iqr).sum()),
            "iqr_outliers_low": int((w < q1 - 1.5 * iqr).sum()),
            "outlier_policy": "Kept. Survey weights legitimately vary; trimming them would change "
                              "the national estimates.",
        })

    # Outliers in survey answers: all are bounded codes, so out-of-range = invalid code.
    answer_outliers = {
        "policy": "All survey answers are bounded categorical codes; values outside the CDC "
                  "code list are counted under 'invalid_codes' and set to missing.",
    }

    qn = check_qn_consistency(codes)
    for name, res in qn.items():
        if res["compared_rows"] and res["agreement"] < 0.99:
            warnings.append(f"Recoding of {QN_RULES[name][0]} agrees with CDC's {name} for only "
                            f"{res['agreement']:.1%} of rows. Check the cut-off before analysis.")

    if n != PUBLISHED_SAMPLE_SIZE:
        warnings.append(f"File has {n:,} records; CDC's MMWR reports N = {PUBLISHED_SAMPLE_SIZE:,} "
                        f"for the 2023 national YRBS. Check you have the right file.")

    dtypes = {c: str(t) for c, t in raw_df.dtypes.items()}

    return {
        "source_file_rows": n,
        "published_sample_size": PUBLISHED_SAMPLE_SIZE,
        "dtypes_as_loaded": dtypes,
        "missing_values": missing,
        "invalid_codes": invalid,
        "duplicates": {
            "exact_full_record_duplicates": full_dups,
            "rows_identical_on_selected_columns": selected_dups,
            "note": "The file has no respondent ID. Different students can give identical answers "
                    "to the selected questions, so only exact full-record duplicates are removed.",
        },
        "weight": weight_summary,
        "answer_outliers": answer_outliers,
        "qn_consistency": qn,
        "warnings": warnings,
    }


# --------------------------------------------------------------------------------------
# Step 5: clean
# --------------------------------------------------------------------------------------
def _codes_to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _flag(codes: pd.Series, yes: Iterable[int]) -> pd.Series:
    """0/1 indicator that stays missing where the answer is missing."""
    return codes.isin(list(yes)).astype("Int8").where(codes.notna(), pd.NA)


def clean_data(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, object]]]:
    """Clean the raw extract. Returns (cleaned DataFrame, list of cleaning steps).

    Missing-data policy: survey answers are NOT imputed. Filling in a student's answer would
    create a response that was never given. Missing answers stay missing and each analysis
    uses the students who answered the questions it needs (available-case analysis).
    """
    validate_columns(raw_df, EXPECTED_RAW_COLUMNS)
    steps: List[Dict[str, object]] = []
    df = normalise_codes(raw_df)
    steps.append({"step": "start", "rows": len(df)})

    # 1. Invalid codes -> missing
    invalid_total = 0
    for col, valid in VALID_CODES.items():
        bad = df[col].notna() & ~df[col].isin(valid)
        invalid_total += int(bad.sum())
        df.loc[bad, col] = np.nan
    steps.append({"step": "set invalid answer codes to missing", "values_changed": invalid_total,
                  "rows": len(df)})

    # 2. Exact duplicate records
    dup = df["is_duplicate_record"].astype(bool)
    df = df.loc[~dup]
    steps.append({"step": "drop exact duplicate full records", "rows_removed": int(dup.sum()),
                  "rows": len(df)})

    # 3. Weights: needed for every national estimate
    weight = parse_implied_decimal(df["WEIGHT"], WEIGHT_IMPLIED_DECIMALS)
    bad_weight = weight.isna() | (weight <= 0)
    df, weight = df.loc[~bad_weight], weight.loc[~bad_weight]
    steps.append({"step": "drop rows with missing or non-positive survey weight",
                  "rows_removed": int(bad_weight.sum()), "rows": len(df)})

    # 4. Recode
    age = _codes_to_int(df["Q1"])
    grade = _codes_to_int(df["Q3"])
    sm = _codes_to_int(df["Q80"])
    sleep = _codes_to_int(df["Q85"])
    active = _codes_to_int(df["Q76"])
    poor_mh = _codes_to_int(df["Q84"])

    clean = pd.DataFrame({
        "row_id": df["row_id"].astype("Int64"),
        "age_code": age,
        "age_label": age.map(AGE_LABELS),
        "age_group": age.map(AGE_GROUPS),
        "sex": _codes_to_int(df["Q2"]).map(SEX_LABELS),
        "grade_code": grade,
        "grade_label": grade.map(GRADE_LABELS),
        "race_ethnicity": _codes_to_int(df["RACEETH"]).map(RACE_LABELS),
        "social_media_code": sm,
        "social_media_freq": sm.map(SOCIAL_MEDIA_LABELS),
        "social_media_frequent": _flag(sm, [6, 7, 8]),
        "sleep_code": sleep,
        "sleep_hours_cat": sleep.map(SLEEP_LABELS),
        "sleep_hours_approx": pd.to_numeric(sleep.map(SLEEP_HOURS_APPROX),
                                            errors="coerce").astype("Int64"),
        "sleep_8plus": _flag(sleep, [5, 6, 7]),
        "active_days": (active - 1).astype("Int64"),
        "active_5plus": _flag(active, [6, 7, 8]),
        "poor_mh_code": poor_mh,
        "poor_mh_frequency": poor_mh.map(POOR_MH_LABELS),
        "poor_mental_health": _flag(poor_mh, [4, 5]),
        "sad_hopeless": _flag(_codes_to_int(df["Q26"]), [1]),
        "difficulty_concentrating": _flag(_codes_to_int(df["Q106"]), [1]),
        "weight": weight.astype(float),
        "stratum": _codes_to_int(df["STRATUM"]),
        "psu": _codes_to_int(df["PSU"]),
    })
    steps.append({"step": "recode CDC answer codes to labelled columns", "rows": len(clean)})

    # 5. Rows that answered none of the study questions carry no information
    empty = clean[STUDY_COLUMNS].isna().all(axis=1)
    clean = clean.loc[~empty].reset_index(drop=True)
    steps.append({"step": "drop rows with no answer to any study question",
                  "rows_removed": int(empty.sum()), "rows": len(clean)})

    steps.append({"step": "missing answers left as missing (no imputation)", "rows": len(clean)})
    validate_columns(clean, CLEANED_COLUMNS)
    return clean[CLEANED_COLUMNS], steps


# --------------------------------------------------------------------------------------
# Step 6: save / load cleaned data
# --------------------------------------------------------------------------------------
def save_cleaned_data(clean: pd.DataFrame, path: Path = CLEANED_CSV_FILE) -> Path:
    path = Path(path)
    if path.resolve() == RAW_DAT_FILE.resolve() or RAW_DIR.resolve() in path.resolve().parents:
        raise DataProcessingError(f"Refusing to write into the raw data folder: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(path, index=False)
    logger.info("Saved cleaned data (%s rows) to %s", f"{len(clean):,}", path)
    return path


def save_data_dictionary(path: Path = DICTIONARY_CSV_FILE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(DATA_DICTIONARY).to_csv(path, index=False)
    return path


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if obj is pd.NA:
        return None
    if isinstance(obj, set):
        return sorted(obj)
    return str(obj)


def save_quality_report(report: Dict[str, object], path: Path = QUALITY_REPORT_FILE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
    return path


def load_cleaned_data(path: Path = CLEANED_CSV_FILE) -> pd.DataFrame:
    """Load cleaned_data.csv with proper dtypes and ordered categories restored."""
    path = Path(path)
    if not path.exists():
        raise DataFileNotFoundError(
            f"Cleaned data not found: {path}\n"
            f"Create it with:  python -m src.data_processing")
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise DataFileError(f"{path} is empty. Re-run 'python -m src.data_processing'.") from exc
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise DataFileError(f"{path} could not be read as CSV ({exc}). "
                            f"Re-run 'python -m src.data_processing'.") from exc
    validate_columns(df, CLEANED_COLUMNS)
    if df.empty:
        raise DataFileError(f"{path} has column headers but no rows. "
                            f"Re-run 'python -m src.data_processing'.")
    for col in INT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in FLAG_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int8")
    for col in FLOAT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    for col, (order, ordered) in CATEGORY_ORDERS.items():
        df[col] = pd.Categorical(df[col], categories=order, ordered=ordered)
    return df


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def load_raw_data(raw_path: Path = RAW_DAT_FILE, interim_csv: Path = INTERIM_CSV_FILE,
                  force: bool = False) -> pd.DataFrame:
    """Steps 1-3: make sure the CSV extract exists, load it with pandas and validate its columns."""
    raw_path, interim_csv = Path(raw_path), Path(interim_csv)
    if raw_path.exists():
        convert_raw_to_csv(raw_path, interim_csv, overwrite=force)
    elif raw_path == RAW_DAT_FILE and interim_csv.exists():
        # Only for the default location: an explicitly given --raw path must exist, otherwise we
        # would silently analyse an extract made from a different file.
        logger.warning("Raw file %s not found; using existing extract %s", raw_path, interim_csv)
    else:
        raise DataFileNotFoundError(_raw_missing_message(raw_path))
    raw_df = load_raw_csv(interim_csv)
    validate_columns(raw_df, EXPECTED_RAW_COLUMNS)
    return raw_df


def process(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Steps 4-5: audit and clean. Returns (cleaned data, quality report). Writes nothing."""
    report = audit_data(raw_df)
    clean, steps = clean_data(raw_df)
    if clean.empty:
        raise DataFileError("No usable rows remain after cleaning. Check that the raw file is the "
                            "2023 national YRBS ASCII file and that it is not damaged.")
    report["cleaning_steps"] = steps
    report["cleaned_rows"] = len(clean)
    report["cleaned_dtypes"] = {c: str(t) for c, t in clean.dtypes.items()}
    report["cleaned_missing_percent"] = {c: round(100 * float(clean[c].isna().mean()), 2)
                                         for c in clean.columns}
    report["variable_support"] = VARIABLE_SUPPORT
    report["analysis_availability"] = analysis_availability(clean).to_dict("records")
    return clean, report


def save_outputs(clean: pd.DataFrame, report: Dict[str, object],
                 output_csv: Path = CLEANED_CSV_FILE) -> None:
    """Step 6: cleaned CSV, data dictionary and quality report."""
    save_cleaned_data(clean, output_csv)
    save_data_dictionary()
    save_quality_report(report)


def run_pipeline(raw_path: Path = RAW_DAT_FILE, interim_csv: Path = INTERIM_CSV_FILE,
                 output_csv: Path = CLEANED_CSV_FILE, force: bool = False
                 ) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """The whole pipeline. The notebook calls the same three steps one by one."""
    raw_df = load_raw_data(raw_path, interim_csv, force=force)
    clean, report = process(raw_df)
    save_outputs(clean, report, output_csv)
    return clean, report


def print_summary(report: Dict[str, object]) -> None:
    print("\n=== YRBS 2023 preprocessing summary ===")
    print(f"Records in file:      {report['source_file_rows']:,} "
          f"(CDC published N = {report['published_sample_size']:,})")
    print(f"Rows after cleaning:  {report['cleaned_rows']:,}")
    print("\nCleaning steps:")
    for step in report["cleaning_steps"]:
        extra = {k: v for k, v in step.items() if k not in ("step", "rows")}
        print(f"  - {step['step']}: rows={step['rows']:,} {extra if extra else ''}")
    print("\nMissing values in cleaned data (%):")
    for col, pct in report["cleaned_missing_percent"].items():
        if pct:
            print(f"  {col:<26}{pct:>6.2f}")
    print("\nRecoding vs CDC QN indicators (agreement):")
    for name, res in report["qn_consistency"].items():
        print(f"  {name:<6} {res['agreement']} over {res['compared_rows']:,} rows")
    print("\nAnalyses NOT supported by this dataset:")
    for row in report["analysis_availability"]:
        if not row["available"]:
            print(f"  - {row['analysis']}: {row['reason']}")
    if report["warnings"]:
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"  ! {w}")
    print(f"\nOutputs:\n  {CLEANED_CSV_FILE}\n  {DICTIONARY_CSV_FILE}\n  {QUALITY_REPORT_FILE}\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and clean the 2023 national YRBS data.")
    parser.add_argument("--raw", type=Path, default=RAW_DAT_FILE,
                        help=f"Path to XXH2023_YRBS_Data.dat (default: {RAW_DAT_FILE})")
    parser.add_argument("--output", type=Path, default=CLEANED_CSV_FILE,
                        help=f"Where to write the cleaned CSV (default: {CLEANED_CSV_FILE})")
    parser.add_argument("--force", action="store_true",
                        help="Rebuild the intermediate CSV even if it is up to date.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        _, report = run_pipeline(raw_path=args.raw, output_csv=args.output, force=args.force)
    except DataProcessingError as exc:
        print(f"\nERROR: {exc}\n", file=sys.stderr)
        return 1
    print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
