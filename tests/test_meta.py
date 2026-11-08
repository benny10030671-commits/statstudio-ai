"""Meta-analysis procedures: analytic invariants plus comparison with R meta/metafor reference values.

The reference values in validation/meta/synthetic_oracle.json were produced by
validation/meta/synthetic_oracle.R (meta 8.5.0, metafor 5.0.1). They are
measured oracle output for one fixed fixture, not a certificate for all data.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from statstudio.engine import analyze
from statstudio.meta import lan_demets_boundaries

ORACLE = json.loads((Path(__file__).resolve().parents[1] / "validation" / "meta" / "synthetic_oracle.json").read_text(encoding="utf-8"))
FIXTURE = pd.DataFrame({"study": [f"S{i}" for i in range(1, 7)], "e1": [12, 3, 0, 45, 8, 10], "n1": [100, 40, 30, 500, 60, 150],
                        "e2": [18, 5, 2, 40, 19, 35], "n2": [98, 42, 31, 490, 58, 148], "x": [60, 65, 70, 55, 72, 68], "g": ["a", "a", "b", "b", "a", "b"]})
ROLES = {"study": "study", "event_exp": "e1", "n_exp": "n1", "event_ctrl": "e2", "n_ctrl": "n2"}


def table(result, title):
    return next(t for t in result["tables"] if t["title"] == title)


def row(result, title, first):
    tab = table(result, title)
    return dict(zip(tab["columns"], next(r for r in tab["rows"] if r[0] == first)))


def test_meta_binary_matches_r_meta():
    res = analyze(FIXTURE, "meta_binary", {**ROLES, "subgroup": "g"})
    est = table(res, "Study estimates")
    for r, te, se in zip(est["rows"], ORACLE["TE"], ORACLE["seTE"]):
        assert r[8] == pytest.approx(te, abs=1e-10)
        assert r[9] == pytest.approx(se, abs=1e-10)
    common = row(res, "Pooled estimates", "Common effect (inverse variance)")
    assert common["log OR"] == pytest.approx(ORACLE["common"][0], abs=1e-10)
    assert common["SE"] == pytest.approx(ORACLE["common"][1], abs=1e-10)
    assert common["p"] == pytest.approx(ORACLE["common"][4], rel=1e-7)
    random = row(res, "Pooled estimates", "Random effects (inverse variance, DL)")
    assert random["log OR"] == pytest.approx(ORACLE["random"][0], abs=1e-9)
    assert random["OR lower"] == pytest.approx(math.exp(ORACLE["random"][2]), rel=1e-8)
    assert random["OR upper"] == pytest.approx(math.exp(ORACLE["random"][3]), rel=1e-8)
    hk = row(res, "Pooled estimates", "Random effects, Hartung–Knapp CI (DL)")
    assert hk["SE"] == pytest.approx(ORACLE["hk"][1], abs=1e-9)
    assert hk["OR lower"] == pytest.approx(math.exp(ORACLE["hk"][2]), rel=1e-8)
    assert hk["p"] == pytest.approx(ORACLE["hk"][4], rel=1e-7)
    het = dict(zip(table(res, "Heterogeneity")["columns"], table(res, "Heterogeneity")["rows"][0]))
    assert het["tau²"] == pytest.approx(ORACLE["tau2"], abs=1e-9)
    assert het["I² %"] == pytest.approx(ORACLE["I2"], abs=1e-7)
    assert het["Q"] == pytest.approx(ORACLE["Q"], abs=1e-9)
    assert het["p (Q)"] == pytest.approx(ORACLE["pQ"], rel=1e-7)
    assert het["Prediction interval lower (OR)"] == pytest.approx(math.exp(ORACLE["predict"][0]), rel=1e-7)
    assert het["Prediction interval upper (OR)"] == pytest.approx(math.exp(ORACLE["predict"][1]), rel=1e-7)
    assert het["tau² lower (Q-profile)"] == pytest.approx(ORACLE["tau2_ci"][0], rel=2e-3)  # metafor confint root-finding tolerance
    assert het["tau² upper (Q-profile)"] == pytest.approx(ORACLE["tau2_ci"][1], rel=2e-3)
    peto = row(res, "Pooled estimates", "Peto common-effect OR (no continuity correction)")
    assert peto["log OR"] == pytest.approx(ORACLE["peto"][0], abs=1e-10)
    assert peto["SE"] == pytest.approx(ORACLE["peto"][1], abs=1e-10)
    mh = row(res, "Pooled estimates", "Mantel–Haenszel common-effect OR (no continuity correction)")
    assert mh["log OR"] == pytest.approx(ORACLE["mh"][0], abs=1e-10)
    assert mh["SE"] == pytest.approx(ORACLE["mh"][1], abs=1e-9)
    egger = table(res, "Small-study effects (Egger regression)")["rows"][0]
    assert egger[1] == pytest.approx(ORACLE["egger"][0], abs=1e-9)
    assert egger[2] == pytest.approx(ORACLE["egger"][1], abs=1e-9)
    assert egger[5] == pytest.approx(ORACLE["egger"][3], rel=1e-6)
    sub = table(res, "Subgroups")
    for r, te, lo, up, t2 in zip(sub["rows"], ORACLE["sub_TE"], ORACLE["sub_lower"], ORACLE["sub_upper"], ORACLE["sub_tau2"]):
        assert r[2] == pytest.approx(math.exp(te), rel=1e-8)
        assert r[3] == pytest.approx(math.exp(lo), rel=1e-8)
        assert r[4] == pytest.approx(math.exp(up), rel=1e-8)
        assert r[5] == pytest.approx(t2, abs=1e-9)
    diff = sub["rows"][-1]
    assert diff[7] == pytest.approx(ORACLE["Qb"], abs=1e-9)
    assert diff[9] == pytest.approx(ORACLE["pb"], rel=1e-7)
    json.dumps(res, allow_nan=False)


def test_tau2_estimators_and_measures():
    reml = analyze(FIXTURE, "meta_binary", {**ROLES, "tau2_method": "REML"})
    assert table(reml, "Heterogeneity")["rows"][0][0] == pytest.approx(ORACLE["reml_tau2"], abs=1e-5)  # Fisher-scoring vs bounded optimiser
    pm = analyze(FIXTURE, "meta_binary", {**ROLES, "tau2_method": "PM"})
    assert table(pm, "Heterogeneity")["rows"][0][0] == pytest.approx(ORACLE["pm_tau2"], abs=1e-5)  # meta PM iteration tolerance
    single = analyze(FIXTURE.iloc[:1], "meta_binary", ROLES)
    r = table(single, "Study estimates")["rows"][0]
    pooled = row(single, "Pooled estimates", "Common effect (inverse variance)")
    assert pooled["OR"] == pytest.approx(r[5])


def test_double_zero_and_manual_corrections_rejected():
    df = FIXTURE.copy()
    df.loc[2, ["e1", "e2"]] = 0
    res = analyze(df, "meta_binary", ROLES)
    assert res["details"]["k_pooled"] == 5
    assert "S3" in res["details"]["double_zero_excluded"]
    bad = FIXTURE.astype({"e1": float})
    bad.loc[0, "e1"] = 12.5
    with pytest.raises(ValueError, match="連續性校正"):
        analyze(bad, "meta_binary", ROLES)
    with pytest.raises(ValueError):
        analyze(FIXTURE, "meta_binary", {**ROLES, "weights": "x"})


def test_meta_regression_matches_metafor():
    res = analyze(FIXTURE, "meta_regression", {**ROLES, "moderator": "x"})
    coef = table(res, "Meta-regression coefficients")["rows"]
    assert coef[0][1] == pytest.approx(ORACLE["mr_beta"][0], abs=1e-6)
    assert coef[1][1] == pytest.approx(ORACLE["mr_beta"][1], abs=1e-8)
    assert coef[1][2] == pytest.approx(ORACLE["mr_se"][1], rel=1e-5)
    assert coef[1][7] == pytest.approx(ORACLE["mr_p"][1], rel=1e-5)
    het = table(res, "Meta-regression heterogeneity")["rows"][0]
    assert het[1] == pytest.approx(ORACLE["mr_tau2"], abs=1e-6)
    assert het[4] == pytest.approx(ORACLE["mr_QE"], rel=1e-6)
    dl = analyze(FIXTURE, "meta_regression", {**ROLES, "moderator": "x", "tau2_method": "DL", "knapp_hartung": "no"})
    coef = table(dl, "Meta-regression coefficients")["rows"]
    assert coef[1][1] == pytest.approx(ORACLE["mrdl_beta"][1], abs=1e-8)
    assert coef[1][2] == pytest.approx(ORACLE["mrdl_se"][1], rel=1e-7)
    assert table(dl, "Meta-regression heterogeneity")["rows"][0][1] == pytest.approx(ORACLE["mrdl_tau2"], abs=1e-9)
    with pytest.raises(ValueError, match="4"):
        analyze(FIXTURE.iloc[:3], "meta_regression", {**ROLES, "moderator": "x"})


def test_bayes_meta_runs_and_recovers_frequentist_scale():
    res = analyze(FIXTURE, "bayes_meta_binary", {**ROLES, "iterations": 4000, "burnin": 1000, "chains": 2, "seed": 7, "prior_effect_sd": 10, "prior_tau_scale": 0.5})
    post = table(res, "Posterior summary")
    d = dict(zip(post["columns"], post["rows"][0]))
    # with a vague effect prior the posterior median of d is close to the DL random-effects estimate
    assert abs(d["Median"] - ORACLE["random"][0]) < 0.15
    assert d["R-hat (split)"] < 1.1
    probs = dict(table(res, "Posterior probabilities")["rows"])
    assert 0 <= probs["OR < 1"] <= 1
    fit = table(res, "Model fit")["rows"][0]
    assert fit[3] > 0  # pD positive
    fixed = analyze(FIXTURE, "bayes_meta_binary", {**ROLES, "model": "fixed", "iterations": 2000, "burnin": 500, "chains": 2, "seed": 3})
    assert table(fixed, "Model fit")["rows"][0][0] == "fixed"
    json.dumps(res, allow_nan=False)


def test_lan_demets_obrien_fleming_equal_looks():
    # Classic two-sided alpha=0.05, five equally spaced looks (Lan & DeMets 1983; e.g. gsDesign/ldbounds tables)
    expected = [4.8769, 3.3569, 2.6803, 2.2898, 2.0310]
    bounds = lan_demets_boundaries([0.2, 0.4, 0.6, 0.8, 1.0], alpha=0.05, grid=0.002)
    for b, e in zip(bounds, expected):
        assert b == pytest.approx(e, abs=0.01)
    single = lan_demets_boundaries([1.0], alpha=0.05)
    assert single[0] == pytest.approx(1.95996, abs=1e-3)


def test_tsa_binary_contract():
    df = FIXTURE.assign(year=[2001, 2003, 2005, 2007, 2009, 2011])
    res = analyze(df, "tsa_binary", {**ROLES, "order": "year", "rrr": 0.2})
    ris = dict(zip(table(res, "Required information size")["columns"], table(res, "Required information size")["rows"][0]))
    pc = ris["Control event proportion"]
    pe = pc * 0.8
    pbar = (pc + pe) / 2
    from scipy import stats as st
    manual = 4 * (st.norm.ppf(0.975) + st.norm.ppf(0.8)) ** 2 * pbar * (1 - pbar) / (pc - pe) ** 2
    assert ris["RIS (no heterogeneity adjustment)"] == pytest.approx(manual, rel=1e-9)
    assert ris["Diversity-adjusted RIS"] >= ris["RIS (no heterogeneity adjustment)"]
    z = table(res, "Cumulative Z-curve")
    assert len(z["rows"]) == 6
    assert z["rows"][-1][1] == int((FIXTURE["n1"] + FIXTURE["n2"]).sum())
    assert all(r[7] is None or r[7] >= 1.9 for r in z["rows"])
    json.dumps(res, allow_nan=False)


def test_lan_demets_small_information_fractions():
    """Very small information fractions must give finite, monotone boundaries from the closed form, not a clamp."""
    from scipy import stats as _st
    import math as _m
    a = _st.norm.ppf(1 - 0.05 / 4)
    fr = [0.0039, 0.0045, 0.0422, 0.1012, 0.3452]
    b = lan_demets_boundaries(fr, alpha=0.05)
    exact = [float(_st.norm.isf(2 * _st.norm.sf(a / _m.sqrt(t)))) for t in fr]
    assert abs(b[0] - exact[0]) < 1e-6
    assert abs(b[2] - exact[2]) < 1e-3          # earlier looks spend ~1e-280, so the first-look form is exact
    assert all(x > 8 for x in b[:3]) and all(b[i] > b[i + 1] for i in range(len(b) - 1))
    assert 3.4 < b[-1] < 3.9 and b[-1] < exact[-1]  # alpha already spent at earlier looks lowers the final boundary slightly
