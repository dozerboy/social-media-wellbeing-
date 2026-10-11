# Data Dictionary: `data/processed/cleaned_data.csv`

**Source:** CDC Youth Risk Behavior Survey (YRBS), 2023 national high-school file `XXH2023_YRBS_Data.dat`.
Column positions and answer codes are taken from CDC's `2023XXH-SAS-Input-Program.sas` and
`2023XXH-Formats-Program.sas`, saved in `data/raw/documentation/`.

A machine-readable copy of this table is written to `data/processed/data_dictionary.csv` by
`python -m src.data_processing`. That file is generated from the code, so if the two ever disagree, trust the CSV.

## Raw fields used (fixed-width positions, 1-based)

| CDC variable | Position | Width | CDC label |
|---|---|---|---|
| Q1 | 17 | 1 | How old are you |
| Q2 | 18 | 1 | What is your sex |
| Q3 | 19 | 1 | In what grade are you |
| Q26 | 57 | 1 | Sad or hopeless |
| Q76 | 107 | 1 | Physical activity >= 5 days |
| Q80 | 111 | 1 | Social media |
| Q84 | 115 | 1 | Current mental health |
| Q85 | 116 | 1 | Hours of sleep on school night |
| Q106 | 137 | 1 | Difficulty concentrating |
| QN26, QN76, QN80, QN84, QN85 | 203, 253, 257, 261, 262 | 1 | CDC's own yes/no indicators. Used only to check our recoding |
| WEIGHT | 388 | 10 (SAS `10.4`) | Overall Analysis Weight |
| STRATUM | 398 | 3 | Sampling Strata |
| PSU | 401 | 6 | Primary Sampling Unit |
| RACEETH | 414 | 2 | Race/Ethnicity |

## Cleaned columns

| Column | From | Type | Values | Meaning |
|---|---|---|---|---|
| `row_id` | line number | int | 1..N | Row position in CDC file (there is no respondent ID) |
| `age_code` | Q1 | int (ordinal) | 1–7 | Age answer code |
| `age_label` | Q1 | ordered category | 12 years old or younger … 18 years old or older | Age |
| `age_group` | Q1 | ordered category | 14 or younger, 15, 16, 17, 18 or older | CDC MMWR age grouping |
| `sex` | Q2 | category | Female, Male | Sex |
| `grade_code` | Q3 | int | 1–5 | Grade code (5 = ungraded/other) |
| `grade_label` | Q3 | category | 9th–12th grade, Ungraded or other grade | Grade |
| `race_ethnicity` | RACEETH | category | 8 CDC groups | Race/ethnicity |
| `social_media_code` | Q80 | int (ordinal) | 1–8 | Social media frequency code |
| `social_media_freq` | Q80 | ordered category | I do not use social media; A few times a month; About once a week; A few times a week; About once a day; Several times a day; About once an hour; More than once an hour | **How often**, not hours/day |
| `social_media_frequent` | Q80 | 0/1 | 1 = several times a day or more | Same cut-off as CDC QN80 |
| `sleep_code` | Q85 | int (ordinal) | 1–7 | Sleep code |
| `sleep_hours_cat` | Q85 | ordered category | 4 or less hours … 10 or more hours | Sleep on an average school night |
| `sleep_hours_approx` | Q85 | int | 4–10 | Approximate hours (≤4 → 4, ≥10 → 10) |
| `sleep_8plus` | Q85 | 0/1 | 1 = 8+ hours | Same cut-off as CDC QN85 |
| `active_days` | Q76 | int | 0–7 | Days active 60+ min in past 7 days |
| `active_5plus` | Q76 | 0/1 | 1 = 5+ days | Same cut-off as CDC QN76 |
| `poor_mh_code` | Q84 | int (ordinal) | 1–5 | How often mental health was not good, past 30 days. **Higher = worse** |
| `poor_mh_frequency` | Q84 | ordered category | Never, Rarely, Sometimes, Most of the time, Always | Same |
| `poor_mental_health` | Q84 | 0/1 | 1 = most of the time / always | Same cut-off as CDC QN84 |
| `sad_hopeless` | Q26 | 0/1 | 1 = yes | Sad/hopeless almost every day ≥2 weeks, past 12 months |
| `difficulty_concentrating` | Q106 | 0/1 | 1 = yes | CDC label "Difficulty concentrating". Check exact wording in the 2023 questionnaire |
| `weight` | WEIGHT | float | > 0 | Survey analysis weight |
| `stratum` | STRATUM | int | | Survey design stratum |
| `psu` | PSU | int | | Survey design primary sampling unit |

Missing values are blank in the CSV. They mean the student didn't answer, or gave an answer outside CDC's
code list. They are **not** imputed.

## Requested variables not in this dataset

| Requested variable | Status | Effect on the project |
|---|---|---|
| Daily social media usage | Partial: frequency only | Analyses use frequency categories, not hours |
| Screen time | Not available | Screen-time analysis disabled |
| Nighttime social media usage | Not available | Nighttime-use analysis disabled |
| Sleep quality | Not available | Only sleep duration is analysed |
| Self-reported anxiety | Not available | Replaced by clearly labelled mental-health measures (`poor_mental_health`, `sad_hopeless`). These are **not** anxiety measures |
