# Presentation script (about 4 minutes)

**Before you start:**
- Run `streamlit run app.py` and have the dashboard open at http://localhost:8501.
- Have `notebooks/social_media_mental_wellbeing.ipynb` open in another tab.
- Have the report open.

All numbers below come from the executed notebook (CDC YRBS 2023). Re-check them if you re-run anything.

---

## 1. Introduction (≈30 s)

> "Our project is *Social Media Usage and Mental Well-Being: A Data Science Approach Using Python*.
> We asked whether teenagers who use social media more often sleep less or report poorer mental health,
> and how physical activity and age fit in. We wanted real, checkable data, so we used the CDC's
> 2023 Youth Risk Behavior Survey: a national survey of 20,103 US high-school students."

## 2. The data, and what it can't do (≈40 s)

> "Before writing code, we checked which questions the survey actually asks. It measures how
> often students use social media, sleep hours, physical activity and self-reported mental health.
> It does **not** measure screen-time hours, night-time phone use, sleep quality or anxiety. So we
> didn't fake those analyses; the notebook and the dashboard clearly mark them as not available."

*Show:* the "not available in this dataset" notice in the dashboard's **Digital habits** tab.

## 3. Pipeline and validation (≈40 s)

> "One Python module, `data_processing.py`, reads CDC's fixed-width file, validates it and cleans it.
> The notebook and the dashboard both use it, so they always agree. To check the data was read
> correctly, we compared it with CDC's own published figures. We got the same sample size, 20,103.
> We got the same number of social-media answers, 15,203. And we got the same weighted share of
> frequent users, 77.0%. We didn't fill in missing answers, because that would invent data."

*Show:* the architecture diagram in the report.

## 4. Dashboard demo (≈80 s)

1. Point to the metric cards:
   > "These are live national estimates: 77.0% use social media several times a day or more,
   > and 28.5% report poor mental health most of the time or always."
2. In the sidebar, set **Sex → Female**:
   > "Every card and chart updates. Among female students, frequent use is 81.8% and poor
   > mental health is 38.8%."
3. Open the **Mental well-being** tab:
   > "Both lines rise with social media frequency, but this is an association."
4. Open the **Key insights** tab:
   > "These sentences are generated from the filtered data, not written in advance."
5. Press **Reset filters**.

## 4b. AI predictions and recommendations (≈60 s)

Open the **AI Predictions & Recommendations** tab and choose a profile, for example: more than once an hour, 5 hours of sleep, 1 active day, age 16, female. Then press **Predict**.

> "Our teacher asked for an AI feature, so we trained a scikit-learn model on the same CDC data. It
> estimates the likelihood that a student with these answers reported poor mental health. It is an
> estimate, not a diagnosis. We compared Logistic Regression and Random Forest using cross-validation on
> the training data only, then tested once on 3,141 held-out students."

Scroll to the suggestions:

> "These suggestions come from simple, transparent rules based on CDC sleep and activity guidelines.
> They're separate from the model, and each one shows why it appeared."

Scroll to **Model performance**:

> "ROC-AUC is about 0.69. That's modest, which is honest: five survey answers can't explain mental health."

*Tip:* rehearse once with the live app. The figures on screen come from `models/model_metadata.json`.

## 5. Findings (≈40 s)

> "Three results stand out.
>
> First, frequent users reported poor mental health more often: 30.6% versus 20.0%. After adjusting
> for sex, age, race, sleep and activity, the odds ratio is 1.64.
>
> Second, social media frequency had only a **negligible** link with sleep hours: rho is −0.07.
>
> Third, more active students reported poor mental health less often: rho is −0.12, a small effect.
>
> With about 15,000 students, almost everything is statistically significant, so we focused on
> effect sizes."

## 6. Limitations and close (≈30 s)

> "The survey is cross-sectional and self-reported. So we can't say whether social media causes poorer
> mental health, poorer mental health leads to more social media use, or something else drives both.
> Future work would use data with screen-time logs, sleep quality, an anxiety scale, and students
> followed over time. Thank you, we're happy to take questions."
