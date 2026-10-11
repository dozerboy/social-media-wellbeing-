"""Execute the notebook top to bottom on the synthetic fixture and check its content rules."""
import json
import re

import nbformat
import pytest
from nbclient import NotebookClient

from src import plotting as pl
from tests.conftest import PROJECT_ROOT

NOTEBOOK = PROJECT_ROOT / "notebooks" / "social_media_mental_wellbeing.ipynb"


def _cells(kind):
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return ["".join(c["source"]) if isinstance(c["source"], list) else c["source"]
            for c in nb["cells"] if c["cell_type"] == kind]


@pytest.mark.slow
def test_notebook_runs_in_order_without_errors(built_dataset):
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(nb, timeout=900, kernel_name="python3",
                            resources={"metadata": {"path": str(NOTEBOOK.parent)}})
    client.execute()   # raises CellExecutionError with the failing cell if anything breaks
    errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
              if o.get("output_type") == "error"]
    assert not errors
    saved = {p.name for p in pl.CHARTS_DIR.glob("*.png")}
    assert {"01_social_media_frequency.png", "08_spearman_heatmap.png", "09_roc_curves.png"} <= saved


def test_markdown_contains_no_hardcoded_results():
    """Results must be computed in code cells, never typed into text cells."""
    allowed_percents = {"5%", "25%", "50%", "95%", "100%"}
    for text in _cells("markdown"):
        for match in re.findall(r"\d+(?:\.\d+)?\s?%", text):
            assert match.replace(" ", "") in allowed_percents, f"hard-coded percentage {match!r} in: {text[:80]}"
        # Definitions used in explanations are allowed; anything else looks like a typed-in result.
        cleaned = text
        for definition in ("AUC = 0.5", "OR of 1.5", "OR = 1 means", "rho = 0"):
            cleaned = cleaned.replace(definition, "")
        assert not re.search(r"(rho|ρ|OR|AUC)\s*=\s*-?\d", cleaned), f"hard-coded statistic in: {text[:80]}"


def test_ml_section_has_no_target_leakage():
    code = "\n".join(_cells("code"))
    features = eval(re.search(r"FEATURES = (\[.*?\])", code).group(1))
    assert re.search(r'TARGET = "poor_mental_health"', code)
    leaky = {"poor_mental_health", "poor_mh_code", "poor_mh_frequency", "sad_hopeless",
             "difficulty_concentrating"}
    assert not leaky & set(features)
    assert "make_pipeline(StandardScaler()" in code      # scaling fitted inside each CV fold


def test_notebook_uses_shared_modules_only():
    code = "\n".join(_cells("code"))
    for forbidden in ("def weighted_share", "def spearman_test", "def chi_square_test", "read_fwf"):
        assert forbidden not in code, f"notebook re-implements shared code: {forbidden}"
    assert "dp.load_raw_data()" in code and "dp.process(raw_df)" in code and "dp.load_cleaned_data()" in code
