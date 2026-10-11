"""The notebook's weighted logistic regression hides statsmodels' generic warning
"cov_type not fully supported with var_weights". This test justifies that: the cluster-robust
standard errors statsmodels reports equal a hand-computed pseudo-likelihood sandwich estimator."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import pytest


def test_cluster_robust_se_with_var_weights_matches_manual_sandwich(built_dataset):
    df = built_dataset[0]
    cols = ["poor_mental_health", "social_media_frequent", "sleep_8plus", "active_5plus", "sex",
            "weight", "stratum", "psu"]
    md = df[cols].dropna().copy()
    for c in cols[:4]:
        md[c] = md[c].astype(int)
    md["sex"] = md["sex"].astype(str)
    md["w"] = md["weight"] / md["weight"].mean()
    md["cluster"] = pd.factorize(md["stratum"].astype(str) + "_" + md["psu"].astype(str))[0]

    with pytest.warns(Warning):  # the generic caution we hide in the notebook
        res = smf.glm("poor_mental_health ~ social_media_frequent + sleep_8plus + active_5plus + C(sex)",
                      data=md, family=sm.families.Binomial(), var_weights=md["w"]).fit(
            cov_type="cluster", cov_kwds={"groups": md["cluster"]})

    X, y, w = res.model.exog, res.model.endog, md["w"].to_numpy()
    p = 1 / (1 + np.exp(-X @ res.params.to_numpy()))
    bread = np.linalg.inv((X * (w * p * (1 - p))[:, None]).T @ X)
    scores = X * (w * (y - p))[:, None]
    groups = md["cluster"].to_numpy()
    meat = sum(np.outer(scores[groups == g].sum(0), scores[groups == g].sum(0)) for g in np.unique(groups))
    G, N, K = len(np.unique(groups)), len(y), X.shape[1]
    se = np.sqrt(np.diag(bread @ meat @ bread * G / (G - 1) * (N - 1) / (N - K)))
    np.testing.assert_allclose(res.bse.to_numpy(), se, rtol=1e-8)
