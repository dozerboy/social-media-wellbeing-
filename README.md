# Social Media Usage and Mental Well-Being

College data-science project analysing associations between social media use, sleep, physical activity,
age and self-reported mental health among US high-school students. It uses the CDC Youth Risk Behavior
Survey (YRBS) 2023.

> The data is cross-sectional and self-reported. Results show **associations, not causes**.

## Project structure

```
social-media-wellbeing/
├── app.py                         # Streamlit dashboard
├── data/
│   ├── raw/                       # CDC file (read-only) + documentation/ (SAS programs, user guide)
│   ├── interim/                   # selected raw columns as CSV (untouched CDC codes)
│   └── processed/                 # cleaned_data.csv, data_dictionary.csv
├── notebooks/
│   └── social_media_mental_wellbeing.ipynb
├── src/
│   ├── data_processing.py         # shared pipeline: load, validate, audit, clean, save
│   ├── analysis_utils.py          # shared weighted summaries + statistical tests
│   ├── plotting.py                # shared colours + reusable chart functions
│   ├── download_data.py           # CDC download + verification
│   ├── ml_model.py                # AI model: features, pipelines, training, evaluation, save/load, predict
│   ├── recommendations.py         # rule-based well-being suggestions
│   └── dashboard_ai.py            # the dashboard's "AI Predictions & Recommendations" tab
├── models/                        # wellbeing_model.joblib + model_metadata.json (trained model and its metrics)
├── outputs/charts/                # PNG charts written by the notebook
├── report/                        # data_quality_report.json, project_review.md
├── docs/
│   ├── data_dictionary.md         # every column, its CDC source and answer scale
│   ├── presentation_script.md     # 3–5 minute demo script
│   ├── viva_questions.md          # likely viva questions with answers
│   ├── DEPLOYMENT.md              # how to publish the dashboard on Streamlit Community Cloud
│   └── python_libraries.md        # what each library does in this project
├── tests/                         # automated tests (synthetic fixture only)
├── .streamlit/config.toml         # dashboard theme
├── DATA_SOURCE.md                 # data source, licence, what is and isn't redistributed
├── requirements.txt               # dashboard packages (installed by Streamlit Cloud)
└── requirements-dev.txt           # + notebook and test tools
```

The notebook and the dashboard both use the same code in `src/` for loading, cleaning, statistics and
the correlation heatmap, so they always produce the same numbers.

## Dataset

| | |
|---|---|
| Name | Youth Risk Behavior Survey (YRBS), 2023 national high-school data |
| Publisher | U.S. Centers for Disease Control and Prevention (CDC) |
| Data page | https://www.cdc.gov/yrbs/data/index.html |
| File used | `XXH2023_YRBS_Data.dat` (fixed-width ASCII), 20,103 records |
| License | CDC's data page states no license or terms of use. As a work of the U.S. federal government it is generally in the public domain in the US. Cite CDC as the source. See `DATA_SOURCE.md`. |

The repository includes `data/processed/cleaned_data.csv`, so the dashboard runs straight after cloning,
locally or online. The original CDC file is not committed. Download it only if you want to re-run the
pipeline or the notebook.

## Live demo

https://social-media-wellbeing-demo.streamlit.app (deployment steps: `docs/DEPLOYMENT.md`).

## Setup (Windows, PowerShell)

Install Python 3.12 from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"**.
Then, in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt      # dashboard + notebook + tests
# pip install -r requirements.txt        # dashboard only (this is what Streamlit Cloud installs)
```

## Run

```powershell
streamlit run app.py                     # dashboard at http://localhost:8501 (works right after cloning)
python -m src.ml_model --train           # (re)train the AI model on data/processed/cleaned_data.csv (~15 s)
python -m src.ml_model --show            # print the saved model's metrics

# Only to rebuild the data or run the notebook:
python -m src.download_data              # 1. download the CDC file (see below if blocked)
python -m src.data_processing            # 2. rebuild data/processed/cleaned_data.csv
jupyter notebook notebooks/social_media_mental_wellbeing.ipynb   # 3. Kernel > Restart & Run All
```

**If CDC blocks the download** (HTTP 403 "Access Denied"):
1. Open https://www.cdc.gov/yrbs/data/index.html in a browser.
2. Under 2023, click **ASCII**.
3. Save the file as `data/raw/XXH2023_YRBS_Data.dat`.
4. Run `python -m src.download_data --verify`.

If `cleaned_data.csv` is missing, the dashboard builds it on first start. If the raw file is missing
too, the dashboard shows the download instructions.

## AI predictions and recommendations

The dashboard's **AI Predictions & Recommendations** tab estimates the likelihood that a student with a
given profile reported poor mental health, and shows rule-based well-being suggestions. It is a locally
trained scikit-learn model; no external AI service is used.

| | |
|---|---|
| Training data | This project's existing `data/processed/cleaned_data.csv` (CDC YRBS 2023). Only the 15,705 students who answered the target question are used; the 4,373 who did not are excluded, not counted as 0 |
| Target | `poor_mental_health`: 1 = mental health "not good" most of the time or always in the past 30 days (Q84 answers 4–5); 0 = never, rarely or sometimes (answers 1–3) |
| Inputs | social media use frequency (Q80), school-night sleep hours (Q85), days active 60+ min (Q76), age group (Q1), sex (Q2) |
| Not used | the target in other forms and other mental-health outcomes (leakage), duplicate versions of the inputs, grade (≈ age), race/ethnicity (by design), survey-design variables. Full list with reasons: `EXCLUDED_COLUMNS` in `src/ml_model.py` |
| Missing inputs | imputed inside the pipeline from training data only (median + "was missing" flag; "Not answered" category) |
| Split | stratified 80/20, seed 42, made before any preprocessing is fitted |
| Models | Logistic Regression (scaled, interpretable) and Random Forest (300 trees) |
| Selection | highest 5-fold cross-validated ROC-AUC **on the training set**; Logistic Regression preferred if within 0.01 |
| Threshold | maximises F1 on out-of-fold training predictions (no class weights or resampling) |
| Calibration | checked on training cross-validation; recalibration only if the calibration error exceeds 0.05 |

**Results of the training run on the real dataset** (12,564 training / 3,141 test students). Regenerate
them with `python -m src.ml_model --train`; the saved values are in `models/model_metadata.json`.

| Held-out test set | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC | Brier |
|---|---|---|---|---|---|---|---|
| **Logistic Regression (selected)** | 0.599 | 0.412 | 0.719 | 0.524 | 0.694 | 0.495 | 0.191 |
| Random Forest | 0.578 | 0.402 | 0.774 | 0.529 | 0.695 | 0.507 | 0.191 |

- **Why Logistic Regression was chosen:** it had the higher cross-validated ROC-AUC (0.692 vs 0.689). The test-set difference of 0.001 is negligible, and the test set is never used for selection.
- **Threshold and calibration:** the decision threshold is 0.27. Calibration was already good (cross-validated error 0.010), so no recalibration was applied.
- **What the model relies on:** by permutation importance on the test set, sex and sleep matter most. Social media frequency and activity add little, and age adds nothing. This shows what the model uses, not causes.

**Recommendations** (`src/recommendations.py`) are transparent rules on the same answers, separate from the
model, and capped at the three most relevant:
- sleep below the CDC guideline (8–10 hours for ages 13–17; 7+ hours for 18+)
- fewer than 7 active days (the CDC recommends 60 minutes every day for ages 6–17)
- social media use several times a day or more

Each suggestion shows its reason and the answer it is based on. None claims that a change will lower the
estimate or that social media causes poor mental health. A support note is always shown.

**Limitations and ethics:**
- **Not a diagnosis:** it is an estimate from one self-reported survey question.
- **Population:** it was trained on US high-school students in 2023, so it may not apply to college students, adults or other countries.
- **Associations only:** the survey cannot show cause and effect.
- **Unweighted:** the metrics describe the sample, not the nation.
- **Few inputs:** with only five inputs, individual estimates are uncertain.
- **Demographics:** sex and age carry group-level patterns, not personal traits, and the dashboard's fairness table shows errors by group.
- **Use:** never use it to make decisions about real people.

## Tests

```powershell
python -m pytest                          # all 94 tests (about 1.5 minutes)
python -m pytest -m "not slow"            # skip the full notebook execution
```

`tests/test_ml_model.py` and `tests/test_recommendations.py` cover:
- target and column validation
- leakage
- the train/test split and train-only imputation
- predictions and their format
- invalid inputs
- saving and loading
- unreadable model files
- every recommendation rule

`tests/test_app.py` also drives the new tab, including the "model not trained" and "unreadable model" cases.

The tests use a **synthetic** file in CDC's layout, generated in a temporary folder. It contains random
values, so it never replaces or mixes with real data. They check:
- column positions and labels against CDC's SAS programs
- file errors
- cleaning rules
- metric-card values
- filters
- chart updates
- statistical functions
- that the notebook runs top to bottom
- that there is no target leakage
- that no results are hard-coded

See `report/project_review.md` for the review and test results.

## Project report

The full report (19 sections, with the real charts and results) is a separate document. It can be
exported to Word or PDF.

## Limitations

- **Not in the data:** screen time, nighttime social media use, sleep quality and anxiety. The analyses that need them are disabled (see `ANALYSES` in `src/data_processing.py`).
- **Social media is measured as frequency** ("several times a day", ...), not hours per day.
- **Ages are about 14–18 only.**
- **Answers are self-reported and the survey is cross-sectional,** so associations cannot be read as causes.
- **Weights:** weighted percentages are national estimates. The classical tests ignore the survey design, so their p-values are too small. The regression uses weights and PSU clustering but not strata.
- **AI model:** an estimate learned from survey answers, not a diagnosis; see "AI predictions and recommendations" above.
