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
│   └── download_data.py           # CDC download + verification
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

Deployment steps are in `docs/DEPLOYMENT.md`. Once the app is deployed, add its link here. https://social-media-wellbeing-demo.streamlit.app.

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

## Tests

```powershell
python -m pytest                          # all tests (about 1 minute)
python -m pytest -m "not slow"            # skip the full notebook execution
```

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
