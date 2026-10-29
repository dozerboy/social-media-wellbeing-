# Project review and test report

**Date:** 2026-10-11
**Environment:** Python 3.12.8 on Windows 10. Packages: pandas 3.0.6, numpy 2.5.4, scipy 1.18.1, statsmodels 0.15.0, scikit-learn 1.9.1, matplotlib 3.11.2, seaborn 0.13.2, plotly 7.1.0, streamlit 1.65.0.

The work falls into three kinds:
- **Automated tests:** `python -m pytest` runs 94 tests on a synthetic file in CDC's layout, 52 from the first review and 42 added for the AI feature. All pass (re-run 2026-10-30).
- **Real-data runs:** the pipeline, notebook and dashboard were executed on the real CDC 2023 file.
- **Code review:** reading the code, without running it.

## Results by task

| # | Task | How it was checked | Result |
|---|---|---|---|
| 1 | Imports and dependencies | Fresh install from `requirements*.txt`; `compileall`; every module imported by tests | Pass. Fixed: scikit-learn ≥1.8 rejects `RocCurveDisplay(color=…)`, so ROC curves are now drawn with `roc_curve` |
| 2 | Dataset paths | Test checks default paths point into the project; tests run on redirected temp paths; CLI run on real paths | Pass |
| 3 | Expected columns | Raw positions and labels compared with CDC's own SAS input and formats programs; `validate_columns` tested with typo and case hints | Pass |
| 4 | Missing values and empty datasets | Tests for:<br>- missing, empty, header-only, HTML and ZIP files<br>- a folder instead of a file<br>- the wrong layout<br>- no usable rows<br>- an empty dashboard selection<br>- tiny subgroups | Pass. Fixed: an explicit `--raw` path that did not exist silently fell back to an old extract made from a different file |
| 5 | Metric cards | AppTest compares every card with an independent `numpy.average` calculation, weighted and unweighted | Pass |
| 6 | Filters and chart updates | AppTest: age, sex, race, the three range sliders, reset, and the weights toggle. Chart specs change after filtering; counts match pandas | Pass |
| 7 | Statistical methods | Unit tests against SciPy and hand calculations: weighted share, Spearman, chi-square / Cramér's V, Mann-Whitney rank-biserial, Kruskal ε², trend line. The regression's cluster-robust SEs match a hand-computed sandwich estimator to 1e-13 | Pass |
| 8 | Target leakage | Notebook asserts no outcome-related column is a feature; a test parses the notebook; scaling happens inside each CV fold | Pass |
| 9 | No fake findings | Tests check:<br>- markdown cells contain no hard-coded percentages or statistics<br>- dashboard insights equal recomputed values<br>- unsupported variables show "not available" messages, never invented numbers | Pass |
| 10 | Duplicated or unnecessary code | Code review. Weighted statistics, tests, colours and the heatmap now live once in `src/`. The notebook's copies were removed and a test guards against re-adding them. The unused `dashboard/` and `reports/` folders were removed | Done |
| 11 | Consistent preprocessing | The notebook and dashboard both call `dp.load_cleaned_data()` on the file written by the same `process()` / `save_outputs()` functions. Same headline value in both (see below) | Pass |
| 12 | Clear error messages | Each file error names the problem and the fix: download steps, the `--raw` option, or re-running the pipeline. The dashboard shows them instead of a traceback | Pass |

## Real-data validation (CDC file downloaded 2026-10-11)

| Check | Value from this project | Published by CDC |
|---|---|---|
| Records in file | 20,103 | N = 20,103 (MMWR Suppl 2024;73(4)) |
| Students answering the social media question | 15,203 | 15,203 (MMWR Suppl 2024;73(4), report on social media use) |
| Weighted % frequent social media users | 77.0% | 77.0% (same report) |
| Agreement of our recoding with CDC's QN indicators (QN26, QN76, QN80, QN84, QN85) | 100% each | n/a |

- **Cleaning:** 25 rows had no answer to any study question and were removed.
- **Data quality:** no invalid codes, duplicates or missing weights were found.
- **Missing answers** are high for `difficulty_concentrating` (about 45%), the social media question (about 24%) and the mental-health question (about 22%). They are reported, not imputed.

## Known limitations of the checks

- **Synthetic fixture:** the automated tests use random synthetic data, so they verify the *code*, not the *findings*. The findings come from the real-data run of the notebook.
- **Dashboard rendering:** the dashboard was driven through Streamlit's AppTest, and the real server was started and answered its health check. Nobody inspected it in a browser.
- **Third-party warning:** seaborn emits a `PendingDeprecationWarning` from inside its own code. It is harmless.

## AI prediction and recommendation update (2026-10-30)

| Check | How | Result |
|---|---|---|
| Target verified | `poor_mental_health` compared with `poor_mh_code` on the real data | Pass: 1 exactly when Q84 = 4–5; 4,373 missing targets excluded, not counted as 0 |
| No leakage | Outcome columns asserted absent from the inputs (module, test, notebook) | Pass |
| Train-only preprocessing | Test checks the imputer's medians equal the training medians | Pass |
| Split | Disjoint, reproducible, stratified (tests) | Pass |
| Training on real data | `python -m src.ml_model --train` (about 15 s); run twice, identical metrics | Pass. Selected: Logistic Regression; test ROC-AUC 0.694 |
| Save / load / predict | Round-trip test; missing, corrupt and mismatched files give clear errors | Pass |
| Recommendations | Every rule, invalid inputs, the three-suggestion cap, banned wording (tests) | Pass |
| Dashboard tab | AppTest on the real model:<br>- the prediction equals `ml.predict`<br>- the suggestions appear<br>- "Prefer not to answer" reaches the model<br>- the "not trained" and "unreadable model" messages appear | Pass |
| Notebook | Executed top to bottom on the real data; uses `src/ml_model.py`, with no second copy of the training code | Pass |
| Not checked | The new tab has not been viewed in a browser. The live Streamlit Cloud app has not been redeployed with these files yet | Pending |
