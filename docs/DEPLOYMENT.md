# Deploying the dashboard on Streamlit Community Cloud

Streamlit Community Cloud is free. It runs `app.py` straight from a GitHub repository and gives you a
public link ending in `.streamlit.app`. Its default Python version is 3.12, the version this project was
tested with ([Streamlit docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)).

The app does **not** depend on anything stored only on your computer:
- It reads `data/processed/cleaned_data.csv`, which is part of the repository.
- It never downloads from CDC while running.

This was checked by running the app from a clean copy of the repository files, with only `requirements.txt` installed and no raw CDC file present.

---

## 1. Final folder and file checklist

Upload these files, about 50 in all. A ready-made copy with exactly these files is in the folder
`social-media-wellbeing-github`, next to your project folder.

```
app.py                         ← entry file
requirements.txt               ← packages the app needs (Cloud installs this)
requirements-dev.txt           ← extra packages for the notebook and tests (Cloud ignores it)
README.md
DATA_SOURCE.md                 ← source, licence, attribution
.gitignore
pytest.ini
.streamlit/config.toml         ← theme (no secrets)
src/__init__.py
src/data_processing.py
src/analysis_utils.py
src/plotting.py
src/download_data.py
data/processed/cleaned_data.csv      ← REQUIRED by the app (2.5 MB)
data/processed/data_dictionary.csv
data/raw/download_log.json
data/raw/documentation/              ← CDC's SAS programs + Data User's Guide (3 files)
data/interim/.gitkeep
notebooks/social_media_mental_wellbeing.ipynb
outputs/charts/                      ← 11 PNG charts + .gitkeep
report/                              ← project_review.md, data_quality_report.json, .gitkeep
docs/                                ← this guide and the other docs
tests/                               ← automated tests
```

**Do not upload:**
- `data/raw/XXH2023_YRBS_Data.dat` (the raw file can be downloaded from CDC)
- `data/interim/*.csv`
- `__pycache__/`, `.venv/`
- any file containing passwords, keys or tokens

The project uses no secrets at all, so leave the **Secrets** box on Streamlit empty.

---

## 2. Create the GitHub repository

1. Sign in at https://github.com, or create a free account.
2. **Protect your email (recommended):** in **Settings → Emails**, tick **Keep my email addresses private**. Commits made on the website then do not show your personal email.
3. Click **+** (top right) → **New repository**.
4. Fill in the form:
   - **Repository name:** `social-media-wellbeing`
   - **Visibility:** **Public**, so faculty can see the code and the app can be shared publicly
   - Leave **Add a README**, **.gitignore** and **license** *unticked*, because the project already has them
5. Click **Create repository**.

---

## 3. Upload the project files (no Git needed)

GitHub's website accepts up to 100 files at once, each up to 25 MB. This project has about 50 files, the largest about 2.5 MB ([GitHub docs](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)).

1. On the new repository's page, click **uploading an existing file**, or **Add file → Upload files**.
2. Open the `social-media-wellbeing-github` folder in File Explorer.
3. Select **everything inside it** (Ctrl + A) and drag it into the browser window.
   - Drag the *folders* themselves (`src`, `data`, `.streamlit`, …), not the individual files, so the folder structure is kept.
4. Wait until every file is listed, then check the list for `.streamlit/config.toml` and `data/processed/cleaned_data.csv`.
5. Write a commit message such as `Initial upload` → **Commit changes**.
6. On the repository page, confirm that `app.py`, `requirements.txt` and the `src/` and `data/` folders are at the **top level**, not inside an extra folder.

If you install Git later, `git add` / `git push` from the project folder also works. The `.gitignore` already excludes the raw file and the caches.

---

## 4. requirements.txt

Already in the repository:

```
streamlit==1.65.0
pandas==3.0.6
numpy==2.5.4
scipy==1.18.1
matplotlib==3.11.2
seaborn==0.13.2
plotly==7.1.0
```

- These are the exact versions the app was tested with on Python 3.12.
- The notebook-only packages (statsmodels, scikit-learn, Jupyter) and the test tools live in `requirements-dev.txt`, which Streamlit Cloud ignores. That keeps the cloud install small.
- Keep **only one** dependency file named `requirements.txt` in the repository root. Streamlit uses the first dependency file it finds, so don't add a `Pipfile` or `pyproject.toml` ([Streamlit docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)).

---

## 5. Configuring the dataset path

Nothing to configure:
- `src/data_processing.py` builds every path relative to the repository folder: `data/processed/cleaned_data.csv`.
- That works the same on Windows and on Streamlit's Linux servers. There are no `C:\...` paths in the code.
- If the cleaned file were missing, the app would show a clear "dataset could not be loaded" message with instructions instead of crashing.

**Getting the raw data separately (only for the notebook or rebuilding):**
- The original CDC file is not in the repository; anyone can download it.
- Script: `python -m src.download_data`.
- Browser:
  1. Open https://www.cdc.gov/yrbs/data/index.html.
  2. Under 2023, click **ASCII**.
  3. Save the file as `data/raw/XXH2023_YRBS_Data.dat`.
  4. Run `python -m src.download_data --verify`.
- CDC's website sometimes blocks scripted downloads. The browser route always works.

### Licensing and redistribution

- **Licence:** CDC's data page states no licence. As US federal government work, the data is generally public domain in the US (17 U.S.C. § 105), so sharing the derived `cleaned_data.csv` publicly is generally permitted.
- **Attribution:** keep the attribution in `DATA_SOURCE.md` and on the dashboard's Limitations tab.
- **Privacy:** the YRBS public file is anonymous, with no names or school identifiers.
- **College rules:** if your college has its own rules about publishing data, follow them. This is not legal advice.

---

## 6. Connect the repository to Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with your GitHub account. Approve the permissions Streamlit asks for.
2. In your workspace, click **Create app** (upper right).
3. When asked *"Do you already have an app?"* → **Yup, I have an app.**
4. Fill in:
   - **Repository:** `<your-github-username>/social-media-wellbeing`
   - **Branch:** `main`
   - **Main file path:** `app.py` (see step 7)
   - **App URL (optional):** choose a readable name, for example `social-media-wellbeing-demo`
5. Click **Advanced settings**:
   - **Python version:** 3.12, matching the tested setup
   - **Secrets:** leave empty
   - Click **Save**
6. Click **Deploy**. The first build installs the packages and takes a few minutes; you can watch the log at the bottom right.

---

## 7. Choosing the correct entry file

The entry file is **`app.py`**, in the repository root. Enter exactly `app.py`, not `src/app.py` and not a notebook. Everything else (the `src/` modules, the data file) is found from there.

---

## 8. Common deployment errors and fixes

| What you see | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'plotly'` (or another package) | `requirements.txt` missing or not in the repo root | Check that `requirements.txt` is at the top level of the repo, then **Reboot app** |
| `ModuleNotFoundError: No module named 'src'` | `src/` was not uploaded, or its files were uploaded flat without the folder | Upload the `src` folder itself (with `__init__.py`) so the repo shows `src/data_processing.py` |
| "The dataset could not be loaded" in the app | `data/processed/cleaned_data.csv` not uploaded, or the path differs in capital letters (Linux is case-sensitive) | Upload it to exactly `data/processed/cleaned_data.csv` |
| Package install fails during build | Python version too old or too new for the pinned packages | Set **Python 3.12** in the app's settings, then reboot. pandas 3.0 needs Python 3.11 or newer |
| "Main module does not exist" | Wrong **Main file path** | Use `app.py`; check the repo has `app.py` at the top level |
| Everything is inside one extra folder (e.g. `social-media-wellbeing-github/app.py`) | The outer folder was dragged instead of its contents | Delete and re-upload the *contents*, or set the main file path to that folder's `app.py` |
| Default grey theme | `.streamlit/config.toml` not uploaded | Upload the `.streamlit` folder |
| "Oh no." error page, or the app stops responding | Resource limit or crash | **Manage app** (lower right) → check the logs → **Reboot app** |
| "This app has gone to sleep" | No visitors for 12 hours (normal on the free tier) | Click the wake-up button. Open the link yourself shortly before your presentation |
| Changes on GitHub not showing | Build still running | Wait for the redeploy, or **Reboot app** |

Sources: [Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies) · [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

---

## 9. Test the live application

Open the `.streamlit.app` link in a **private/incognito window**, so you see what faculty will see without being logged in.

- [ ] The page loads with the title and six metric cards.
- [ ] With no filters, the cards show **20,078** respondents and **77.0%** frequent social media use. These are the same values as the notebook.
- [ ] Sidebar → **Age group**: keep only `16` → Respondents changes to **5,203**.
- [ ] **Reset filters** brings back 20,078.
- [ ] Switch **Use survey weights** off and on: the percentages change, and the respondent count does not.
- [ ] Each tab (Digital habits, Sleep, Mental well-being, Key insights, Limitations) opens without an error box.
- [ ] Hovering over a chart shows the value and n.
- [ ] Remove every age group → the app shows "No students match the current filters" instead of crashing.
- [ ] Open the link on a phone to check the layout.
- [ ] Only now, once all of the above work: copy the link into the README's **Live demo** section and share it with your faculty.
