# Major Python libraries and their roles

| Library | What it is, simply | What this project uses it for |
|---|---|---|
| **pandas** | Spreadsheet-like tables (DataFrames) in Python | Loading the CSV, filtering students, grouping by age or usage, cleaning and recoding, saving `cleaned_data.csv` |
| **NumPy** | Fast maths on lists of numbers | Weighted averages and percentages, confidence intervals, the hand-check of the regression's standard errors |
| **SciPy** (`scipy.stats`) | Ready-made statistical tests | Spearman correlation, chi-square, Mann–Whitney U and Kruskal–Wallis tests |
| **statsmodels** | Statistical models with detailed output | Weighted logistic regression (odds ratios, clustered standard errors); Holm multiple-testing correction |
| **scikit-learn** | Machine-learning toolkit | Logistic regression and random forest models, cross-validation, ROC-AUC, permutation importance |
| **Matplotlib** | The basic Python plotting library | All static charts in the notebook, saved to `outputs/charts/` |
| **seaborn** | Statistical plots built on Matplotlib | The correlation heatmap, used by both the notebook and the dashboard |
| **Plotly** | Interactive web charts | Dashboard charts with hover details (value, confidence interval, n) |
| **Streamlit** | Turns a Python script into a web app | The dashboard: sidebar filters, metric cards, tabs, caching |
| **Jupyter** | Interactive notebooks mixing code, text and output | The step-by-step analysis notebook |
| **pytest** | Testing framework | 52 automated tests |
| **nbclient / nbformat** | Run and read notebooks from code | Testing that the notebook runs top to bottom without errors |

The standard library's `pathlib`, `urllib`, `hashlib`, `json` and `argparse` handle the following:
- file paths
- the CDC download
- the file fingerprint (SHA-256)
- the quality report
- the command-line options
