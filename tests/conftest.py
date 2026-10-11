"""Test setup: point every project path at a temporary folder BEFORE the project modules load.

This guarantees the tests never read or write data/, report/ or outputs/ in the project.
"""
import os
import sys
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="smw_tests_"))
os.environ["SMW_DATA_DIR"] = str(TEST_ROOT / "data")
os.environ["SMW_REPORT_DIR"] = str(TEST_ROOT / "report")
os.environ["SMW_OUTPUT_DIR"] = str(TEST_ROOT / "outputs")
os.environ.setdefault("MPLBACKEND", "Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from src import data_processing as dp  # noqa: E402
from tests.synthetic_yrbs import write_dat  # noqa: E402

assert dp.DATA_DIR == TEST_ROOT / "data", "tests must never use the real data folder"


@pytest.fixture(scope="session")
def built_dataset():
    """Synthetic raw file -> full pipeline. Returns (cleaned DataFrame, quality report)."""
    write_dat(dp.RAW_DAT_FILE, n=3000, seed=7)
    clean, report = dp.run_pipeline(force=True)
    return clean, report


@pytest.fixture(scope="session")
def raw_df(built_dataset):
    return dp.load_raw_csv(dp.INTERIM_CSV_FILE)
