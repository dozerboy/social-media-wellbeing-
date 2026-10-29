# Likely viva questions and answers

Numbers quoted here come from the executed notebook on the CDC YRBS 2023 data.

## About the data

**1. Why did you use the CDC YRBS instead of a Kaggle dataset?**
- Many Kaggle mental-health datasets have no documented collection method, and some are synthetic, so they cannot be verified.
- The YRBS is a documented, nationally representative government survey.
- We could check our processed data against CDC's published figures, and they matched: 20,103 records, 15,203 social-media answers and 77.0% frequent users.

**2. What does your dataset not contain?**
- Screen-time hours, nighttime social media use, sleep quality and anxiety.
- We marked those analyses as unavailable instead of approximating them.

**3. How is social media use measured?**
- As frequency (question Q80), on 8 levels from "I do not use social media" to "More than once an hour".
- "Frequent use" means several times a day or more, the same cut-off CDC uses.

**4. Why is the raw file a .dat file and not a CSV?**
- CDC publishes a fixed-width text file, where every answer is at a fixed character position.
- We read those positions from CDC's own SAS program, and a test checks that our positions match it.
- We save the selected columns as a CSV and load that with pandas.

**5. How did you handle missing values?**
- We did not impute them, because filling in an answer would invent a response.
- Each analysis uses the students who answered the questions it needs (available-case analysis), and we report n for every result.
- We only removed 25 rows that had no answer to any study question.

**6. Did you find duplicates or invalid values?**
- We checked for both. There were no invalid codes, no duplicate records and no missing weights.

## Statistics

**7. What are survey weights and why use them?**
- Each student represents a number of US students.
- Some groups were sampled more than others, so weighting is needed to estimate national percentages.
- Unweighted numbers describe only the sample.

**8. Why Spearman instead of Pearson correlation?**
- Our variables are ordered categories, not evenly spaced measurements.
- Spearman uses only the order of the values; Pearson assumes a numeric, linear scale.

**9. Everything was significant. Does that mean the effects are important?**
- No. With 11,000–15,000 students, even tiny effects give very small p-values.
- Six of our seven tests had negligible effect sizes. That is why we report effect sizes such as Cramér's V and ρ.

**10. What is Cramér's V, and why do you call 0.09 "negligible" when the gap is 10 percentage points?**
- Cramér's V measures association strength between categorical variables, from 0 to 1.
- By Cohen's convention, below 0.1 counts as negligible.
- For yes/no outcomes V stays small even for noticeable gaps, so we also report the percentage-point difference (30.6% vs 20.0%) and the odds ratio (1.64).

**11. What is the Holm correction?**
- Running many tests raises the chance of a false positive.
- Holm's method adjusts the p-values to keep the overall false-positive rate at 5%.

**12. Explain the odds ratio of 1.64.**
- Frequent users had about 1.6 times the odds of reporting poor mental health.
- That is after adjusting for sex, age, race/ethnicity, sleep and activity.
- The 95% CI is 1.23–2.17. It excludes 1, so the association is unlikely to be zero.

**13. Why clustered standard errors?**
- Students were sampled in groups (schools within primary sampling units), and students in the same group can be similar.
- Clustering accounts for that, so the standard errors aren't too small.
- Our tests confirmed the standard errors match a hand-computed calculation.

**14. Does social media cause poor mental health?**
- The data cannot tell us. It is cross-sectional: one survey at one time.
- The link could run either way, or a third factor such as stress or loneliness could drive both.

## Machine learning

**15. Why include machine learning, and what did it show?**
- It shows how much these few survey answers can *predict* poor mental health.
- The best model reached a ROC-AUC of 0.701, against 0.5 for a baseline. That means most of what shapes mental health is not captured here.

**16. What is target leakage and how did you prevent it?**
- Target leakage means the model sees the answer in another form.
- We excluded the mental-health code, sadness and difficulty concentrating from the features.
- An assert in the notebook and an automated test check this.

**17. What is ROC-AUC?**
- The probability that the model ranks a random positive case above a random negative case.
- 0.5 is chance level; 1.0 is perfect.

## AI prediction and recommendations

**A1. What exactly does the AI model predict?**
- It predicts `poor_mental_health`: whether a student said their mental health was "not good" most of the time or always in the past 30 days (survey question Q84).
- It outputs an *estimated likelihood* for a profile, learned from 15,705 surveyed students. It is not a diagnosis.

**A2. Which inputs does it use, and why not more?**
- It uses social media frequency, school-night sleep, active days, age group and sex: the lifestyle and demographic answers a user can describe.
- Other mental-health answers (sadness, difficulty concentrating) are outcomes, so using them would be leakage.
- Grade duplicates age. Race/ethnicity was left out by design.

**A3. How did you prevent data leakage?**
- Outcome columns are excluded from the inputs, which a test checks.
- The train/test split happens first.
- Imputation and scaling sit inside a scikit-learn Pipeline, so they learn only from training rows; a test also checks this.
- Model selection, the threshold and the calibration check all use cross-validation on the training set only.
- The test set is used once, for the final evaluation.

**A4. How were missing answers handled?**
- Students without a target answer are dropped, not counted as "no".
- Missing inputs, such as the 26% who skipped the social media question, are filled inside the pipeline: the training median plus a "was missing" flag, or a "Not answered" category.

**A5. Why Logistic Regression and not the Random Forest?**
- The rule, fixed before testing, was: highest 5-fold cross-validated ROC-AUC on the training data, preferring Logistic Regression if within 0.01.
- Logistic Regression scored 0.692 against 0.689, and it is easier to interpret.
- On the test set they are practically equal (0.694 vs 0.695).

**A6. Your accuracy is only about 0.60. Is the model bad?**
- Accuracy is the wrong single measure here. About 69% of test students are "no", so a model that always said "no" would get about 69% accuracy while finding nobody.
- Our model finds 72% of the positive students (recall 0.719), with precision 0.412, at a threshold chosen to balance the two (F1).
- ROC-AUC is 0.694: modest discrimination, which is honest for five survey answers.

**A7. Why is the threshold 0.27 and not 0.5?**
- The positive class is the minority (31%). With 0.5 the model would flag very few students.
- 0.27 maximised F1 on out-of-fold training predictions.
- Lowering it trades more false alarms for fewer missed cases.

**A8. Are the displayed probabilities trustworthy?**
- On average, yes. The cross-validated calibration error was 0.010, and the test-set calibration plot follows the diagonal.
- They are population-level estimates and may not apply to any one person.

**A9. Which inputs matter most, and does that mean they cause poor mental health?**
- Permutation importance on the test set ranks sex and sleep highest.
- That measures what the model *relies on* for prediction, not causes.
- Sex reflects a group-level difference in the survey, not a personal trait.

**A10. How do the recommendations work?**
- They are transparent rules in `src/recommendations.py`, separate from the model:
    - sleep below the CDC guideline (8–10 h for ages 13–17; 7+ h for 18+)
    - fewer than 7 active days (the CDC recommends 60 minutes every day for ages 6–17)
    - social media several times a day or more
- At most three are shown, by priority, each with its reason and the answer that triggered it.
- They never promise to change the estimate, and a support note is always shown.

**A11. What are the ethical limits?**
- It is not a diagnosis, and it was trained on US high-school students in 2023, so it is not for college students or other countries.
- It shows associations only, and it is unweighted.
- It must never be used to make decisions about real people.

## Implementation

**18. How do the notebook and dashboard stay consistent?**
- Both use the same modules in `src/` for cleaning, statistics and the heatmap.
- Both read the same `cleaned_data.csv`.
- Tests guard against copying that code into the notebook.

**19. How did you test the project?**
- 94 automated pytest tests on a synthetic file in CDC's layout. They cover file errors, cleaning rules, statistical functions, dashboard metrics and filters, the AI model (leakage, split, imputation, predictions, save/load), the recommendation rules, running the whole notebook, and hard-coded results.
- We also ran everything on the real data.

**20. Why Streamlit caching?**
- `st.cache_data` stores the loaded data and filter results.
- Changing a filter then doesn't reload or reprocess the 20,078-row file.

**21. What would you do with more time?**
- Use data with screen-time logs, sleep quality and an anxiety scale.
- Follow students over time.
- Run a full survey-design analysis including strata.
- Deploy the dashboard online.
