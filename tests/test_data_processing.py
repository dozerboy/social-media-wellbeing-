"""Tests for src/data_processing.py (loading, validation, cleaning, file errors)."""
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src import data_processing as dp
from tests.conftest import PROJECT_ROOT
from tests.synthetic_yrbs import SPECIAL_ROWS, make_line

DOC_DIR = PROJECT_ROOT / "data" / "raw" / "documentation"


# ---- Layout matches CDC's own documentation (real files in the project) -----------------
def test_field_positions_match_cdc_sas_input_program():
    sas = (DOC_DIR / "2023XXH-SAS-Input-Program.sas").read_text(encoding="latin-1")
    found = {m.group(2).upper(): (int(m.group(1)), int(m.group(3)))
             for m in re.finditer(r"@(\d+)\s+(\w+)\s+\$?(\d+)\.", sas)}
    for field in dp.RAW_FIELDS:
        assert found[field.name.upper()] == (field.start, field.width), field.name


def test_value_labels_match_cdc_formats_program():
    sas = (DOC_DIR / "2023XXH-Formats-Program.sas").read_text(encoding="latin-1")

    def labels(fmt):
        block = re.search(rf"value \${fmt}\r?\n(.*?);", sas, re.S).group(1)
        return {int(k): v for k, v in re.findall(r'"(\d)"="([^"]+)"', block)}

    assert labels("H1S") == dp.AGE_LABELS
    assert labels("H2S") == dp.SEX_LABELS
    assert labels("H3S") == dp.GRADE_LABELS
    assert labels("H80S") == dp.SOCIAL_MEDIA_LABELS
    assert labels("H84S") == dp.POOR_MH_LABELS
    assert labels("H85S") == dp.SLEEP_LABELS
    assert labels("HRCE") == dp.RACE_LABELS
    assert set(labels("H76S")) == {int(c) for c in dp.VALID_CODES["Q76"]}


def test_default_paths_point_into_the_project():
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMW_")}
    out = subprocess.run([sys.executable, "-c",
                          "from src import data_processing as dp; print(dp.RAW_DAT_FILE); "
                          "print(dp.CLEANED_CSV_FILE); print(dp.QUALITY_REPORT_FILE)"],
                         cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, check=True)
    raw, cleaned, report = out.stdout.split()
    assert raw == str(PROJECT_ROOT / "data" / "raw" / "XXH2023_YRBS_Data.dat")
    assert cleaned == str(PROJECT_ROOT / "data" / "processed" / "cleaned_data.csv")
    assert report == str(PROJECT_ROOT / "report" / "data_quality_report.json")


# ---- File errors -------------------------------------------------------------------------
def test_missing_file_gives_download_instructions(tmp_path):
    with pytest.raises(dp.DataFileNotFoundError) as err:
        dp.check_raw_file(tmp_path / "nope.dat")
    assert "download" in str(err.value).lower() and dp.DATA_PAGE_URL in str(err.value)


@pytest.mark.parametrize("content, phrase", [
    (b"", "empty"),
    (b"<HTML><HEAD><TITLE>Access Denied</TITLE>", "web page"),
    (b"PK\x03\x04zipdata", "ZIP"),
])
def test_bad_raw_files_are_rejected(tmp_path, content, phrase):
    path = tmp_path / "bad.dat"
    path.write_bytes(content)
    with pytest.raises(dp.DataFileError) as err:
        dp.check_raw_file(path)
    assert phrase.lower() in str(err.value).lower()


def test_folder_instead_of_file(tmp_path):
    with pytest.raises(dp.DataFileError, match="folder"):
        dp.check_raw_file(tmp_path)


def test_wrong_layout_is_rejected(tmp_path):
    path = tmp_path / "short.dat"
    path.write_text("1234\n5678\n")
    with pytest.raises(dp.DataFileError, match="does not match"):
        dp.read_fixed_width(path)


def test_missing_and_empty_csv(tmp_path):
    with pytest.raises(dp.DataFileNotFoundError):
        dp.load_raw_csv(tmp_path / "missing.csv")
    (tmp_path / "empty.csv").write_text("")
    with pytest.raises(dp.DataFileError, match="empty"):
        dp.load_raw_csv(tmp_path / "empty.csv")
    header_only = tmp_path / "header.csv"
    header_only.write_text(",".join(dp.CLEANED_COLUMNS) + "\n")
    with pytest.raises(dp.DataFileError, match="no rows"):
        dp.load_cleaned_data(header_only)
    with pytest.raises(dp.DataFileNotFoundError, match="python -m src.data_processing"):
        dp.load_cleaned_data(tmp_path / "missing_clean.csv")


def test_cli_reports_missing_file_cleanly(tmp_path, capsys):
    assert dp.main(["--raw", str(tmp_path / "missing.dat")]) == 1
    assert "ERROR" in capsys.readouterr().err


def test_refuses_to_write_into_raw_folder(built_dataset):
    with pytest.raises(dp.DataProcessingError, match="raw data folder"):
        dp.save_cleaned_data(built_dataset[0], dp.RAW_DIR / "oops.csv")


# ---- Parsing -------------------------------------------------------------------------------
def test_fixed_width_parsing_reads_correct_positions(tmp_path):
    values = {"Q1": "5", "Q2": "1", "Q3": "2", "Q26": "1", "Q76": "8", "Q80": "6", "Q84": "4",
              "Q85": "3", "Q106": "2", "QN26": "1", "QN76": "1", "QN80": "1", "QN84": "1", "QN85": "2",
              "WEIGHT": "1.2345", "STRATUM": "101", "PSU": "123456", "RACEETH": "5"}
    path = tmp_path / "one.dat"
    path.write_text(make_line(values) + "\n")
    row = dp.read_fixed_width(path).iloc[0]
    for name, expected in values.items():
        assert row[name] == expected, name


def test_implied_decimal_weights():
    parsed = dp.parse_implied_decimal(pd.Series(["     12345", "1.5", None, "abc"]), 4)
    assert parsed.iloc[0] == pytest.approx(1.2345)
    assert parsed.iloc[1] == pytest.approx(1.5)
    assert np.isnan(parsed.iloc[2]) and np.isnan(parsed.iloc[3])


# ---- Validation ----------------------------------------------------------------------------
def test_validate_columns_reports_missing_with_hints():
    df = pd.DataFrame(columns=["row_id", "q80", "Q8O"])
    with pytest.raises(dp.MissingColumnsError) as err:
        dp.validate_columns(df, ["row_id", "Q80"])
    assert "Q80" in str(err.value) and "different case" in str(err.value)
    assert dp.validate_columns(df, ["row_id", "Q80"], strict=False) == ["Q80"]


# ---- Audit and cleaning --------------------------------------------------------------------
def test_audit_finds_planted_problems(raw_df):
    audit = dp.audit_data(raw_df)
    assert audit["duplicates"]["exact_full_record_duplicates"] == SPECIAL_ROWS["exact_duplicates"]
    assert audit["invalid_codes"]["Q80"]["count"] == SPECIAL_ROWS["invalid_Q80"]
    assert audit["invalid_codes"]["Q85"]["count"] == SPECIAL_ROWS["invalid_Q85"]
    assert audit["weight"]["missing"] == SPECIAL_ROWS["blank_weight"]
    assert all(r["agreement"] == 1.0 for r in audit["qn_consistency"].values())


def test_cleaning_steps_and_row_counts(built_dataset, raw_df):
    clean, report = built_dataset
    removed = {s["step"]: s.get("rows_removed", 0) for s in report["cleaning_steps"]}
    assert removed["drop exact duplicate full records"] == 1
    assert removed["drop rows with missing or non-positive survey weight"] == 1
    assert removed["drop rows with no answer to any study question"] >= 1
    assert len(clean) == len(raw_df) - sum(removed.values())
    assert clean["row_id"].is_unique
    assert (clean["weight"] > 0).all()


def test_no_imputation_and_invalid_codes_become_missing(built_dataset, raw_df):
    clean = built_dataset[0]
    raw = dp.normalise_codes(raw_df).set_index("row_id")
    kept = raw.loc[clean["row_id"].astype(int)]
    expected_missing = (~kept["Q80"].isin(dp.VALID_CODES["Q80"])).sum()   # blank or invalid
    assert clean["social_media_code"].isna().sum() == expected_missing
    assert set(clean["social_media_code"].dropna().unique()) <= set(range(1, 9))
    assert set(clean["sleep_code"].dropna().unique()) <= set(range(1, 8))


def test_recoded_flags_follow_definitions(built_dataset):
    c = built_dataset[0]
    ok = c["social_media_code"].notna()
    assert (c.loc[ok, "social_media_frequent"] == c.loc[ok, "social_media_code"].isin([6, 7, 8]).astype(int)).all()
    ok = c["poor_mh_code"].notna()
    assert (c.loc[ok, "poor_mental_health"] == c.loc[ok, "poor_mh_code"].isin([4, 5]).astype(int)).all()
    ok = c["sleep_code"].notna()
    assert (c.loc[ok, "sleep_8plus"] == (c.loc[ok, "sleep_hours_approx"] >= 8).astype(int)).all()
    ok = c["active_days"].notna()
    assert (c.loc[ok, "active_5plus"] == (c.loc[ok, "active_days"] >= 5).astype(int)).all()
    assert c["social_media_frequent"].isna().equals(c["social_media_code"].isna())


def test_saved_files_and_reload(built_dataset):
    assert dp.CLEANED_CSV_FILE.exists() and dp.DICTIONARY_CSV_FILE.exists() and dp.QUALITY_REPORT_FILE.exists()
    df = dp.load_cleaned_data()
    assert list(df.columns) == dp.CLEANED_COLUMNS
    assert df["social_media_freq"].cat.ordered
    assert list(df["social_media_freq"].cat.categories) == list(dp.SOCIAL_MEDIA_LABELS.values())
    assert str(df["social_media_frequent"].dtype) == "Int8"
    pd.testing.assert_series_equal(df["social_media_code"], built_dataset[0]["social_media_code"],
                                   check_names=False)


def test_raw_file_is_not_modified(built_dataset):
    before = dp.RAW_DAT_FILE.read_bytes()
    dp.run_pipeline(force=True)
    assert dp.RAW_DAT_FILE.read_bytes() == before


def test_unsupported_analyses_are_disabled(built_dataset):
    table = dp.analysis_availability(built_dataset[0])
    disabled = set(table.loc[~table["available"], "analysis"])
    assert disabled == {"screen_time_analysis", "nighttime_use_vs_sleep_quality", "social_media_vs_anxiety"}
    assert not dp.is_analysis_supported("social_media_vs_anxiety")
    with pytest.raises(KeyError):
        dp.is_analysis_supported("does_not_exist")


def test_dataset_with_no_usable_rows(raw_df):
    empty_answers = raw_df.copy()
    for col in ["Q26", "Q76", "Q80", "Q84", "Q85", "Q106"]:
        empty_answers[col] = np.nan
    with pytest.raises(dp.DataFileError, match="No usable rows"):
        dp.process(empty_answers)
