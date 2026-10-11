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

## Implementation

**18. How do the notebook and dashboard stay consistent?**
- Both use the same modules in `src/` for cleaning, statistics and the heatmap.
- Both read the same `cleaned_data.csv`.
- Tests guard against copying that code into the notebook.

**19. How did you test the project?**
- 52 automated pytest tests on a synthetic file in CDC's layout. They cover file errors, cleaning rules, statistical functions, dashboard metrics and filters, running the whole notebook, target leakage and hard-coded results.
- We also ran everything on the real data.

**20. Why Streamlit caching?**
- `st.cache_data` stores the loaded data and filter results.
- Changing a filter then doesn't reload or reprocess the 20,078-row file.

**21. What would you do with more time?**
- Use data with screen-time logs, sleep quality and an anxiety scale.
- Follow students over time.
- Run a full survey-design analysis including strata.
- Deploy the dashboard online.
