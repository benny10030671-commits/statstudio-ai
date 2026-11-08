"""R backend (meta/metafor, rjags, RTSA) versus the Python engine on the same fixture.

Skipped when R or any required package is not installed; the Python engine never needs R.
"""
import json
import math

import pytest

from statstudio import r_backend
from statstudio.engine import analyze
from tests.test_meta import FIXTURE, ROLES, row, table

pytestmark = pytest.mark.skipif(not r_backend.available(), reason="R with meta, metafor, rjags, RTSA and JAGS is not available")


def het(res):
    tab = table(res, "Heterogeneity")
    return dict(zip(tab["columns"], tab["rows"][0]))


def test_environment_reports_versions():
    env = r_backend.environment(refresh=True)
    assert env["available"] and env["rscript"]
    assert all(env["packages"].get(p) for p in r_backend.REQUIRED) and env["jags"]


def test_meta_binary_r_matches_python_engine():
    # R meta reports Q-based I²/H² and a k-1 prediction interval; select the matching Python conventions explicitly
    py = analyze(FIXTURE, "meta_binary", {**ROLES, "subgroup": "g", "prediction_df": "k-1", "heterogeneity_method": "q"})
    rr = analyze(FIXTURE, "meta_binary_r", {**ROLES, "subgroup": "g"})
    assert rr["details"]["backend"] == "R" and rr["details"]["software"]["meta"]
    assert [t["title"] for t in rr["tables"]] == [t["title"] for t in py["tables"]]
    est_py, est_r = table(py, "Study estimates"), table(rr, "Study estimates")
    assert est_r["columns"] == est_py["columns"]
    for a, b in zip(est_py["rows"], est_r["rows"]):
        assert a[8] == pytest.approx(b[8], abs=1e-9) and a[9] == pytest.approx(b[9], abs=1e-9) and a[11] == pytest.approx(b[11], abs=1e-7)
    for model in ["Common effect (inverse variance)", "Random effects (inverse variance, DL)", "Random effects, Hartung–Knapp CI (DL)",
                  "Peto common-effect OR (no continuity correction)", "Mantel–Haenszel common-effect OR (no continuity correction)"]:
        a, b = row(py, "Pooled estimates", model), row(rr, "Pooled estimates", model)
        assert a["log OR"] == pytest.approx(b["log OR"], abs=1e-9) and a["SE"] == pytest.approx(b["SE"], abs=1e-9) and a["p"] == pytest.approx(b["p"], rel=1e-6)
    hp, hr = het(py), het(rr)
    assert table(rr, "Heterogeneity")["columns"] == table(py, "Heterogeneity")["columns"]
    assert hp["Prediction interval df"] == hr["Prediction interval df"]
    for key in ["tau²", "I² %", "H", "H²", "Q", "p (Q)", "Prediction interval lower (OR)", "Prediction interval upper (OR)"]:
        assert hp[key] == pytest.approx(hr[key], rel=1e-7, abs=1e-9)
    assert hp["tau² upper (Q-profile)"] == pytest.approx(hr["tau² upper (Q-profile)"], rel=2e-3)
    sp, sr = table(py, "Subgroups"), table(rr, "Subgroups")
    for a, b in zip(sp["rows"], sr["rows"]):
        assert a[0] == b[0] and a[1] == b[1] and (a[2] is None or a[2] == pytest.approx(b[2], rel=1e-7)) and a[9] == pytest.approx(b[9], rel=1e-6)
    json.dumps(rr, allow_nan=False)


def test_meta_binary_r_hts_prediction_interval_matches_k_minus_2():
    py = analyze(FIXTURE, "meta_binary", {**ROLES, "prediction_df": "k-2", "heterogeneity_method": "q"})
    rr = analyze(FIXTURE, "meta_binary_r", {**ROLES, "prediction_df": "k-2"})
    hp, hr = het(py), het(rr)
    assert hr["Prediction interval df"] == hp["Prediction interval df"] == 4
    assert hp["Prediction interval lower (OR)"] == pytest.approx(hr["Prediction interval lower (OR)"], rel=1e-7)


def test_meta_regression_r_matches_python_engine():
    py = analyze(FIXTURE, "meta_regression", {**ROLES, "moderator": "x"})
    rr = analyze(FIXTURE, "meta_regression_r", {**ROLES, "moderator": "x"})
    cp, cr = table(py, "Meta-regression coefficients"), table(rr, "Meta-regression coefficients")
    assert cr["columns"] == cp["columns"]
    for a, b in zip(cp["rows"], cr["rows"]):
        assert a[1] == pytest.approx(b[1], abs=1e-5) and a[2] == pytest.approx(b[2], rel=1e-4) and a[7] == pytest.approx(b[7], rel=1e-3, abs=1e-6)
    hp = dict(zip(table(py, "Meta-regression heterogeneity")["columns"], table(py, "Meta-regression heterogeneity")["rows"][0]))
    hr = dict(zip(table(rr, "Meta-regression heterogeneity")["columns"], table(rr, "Meta-regression heterogeneity")["rows"][0]))
    assert hp["tau² residual"] == pytest.approx(hr["tau² residual"], abs=1e-5) and hp["Q_E (residual)"] == pytest.approx(hr["Q_E (residual)"], rel=1e-7)


def test_tsa_binary_r_matches_python_engine():
    opts = {**ROLES, "rrr": 0.2}
    py = analyze(FIXTURE, "tsa_binary", opts)
    rr = analyze(FIXTURE, "tsa_binary_r", opts)
    rp = dict(zip(table(py, "Required information size")["columns"], table(py, "Required information size")["rows"][0]))
    rrr_ = dict(zip(table(rr, "Required information size")["columns"], table(rr, "Required information size")["rows"][0]))
    assert rp["Accrued participants"] == rrr_["Accrued participants"]
    assert rp["RIS (no heterogeneity adjustment)"] == pytest.approx(rrr_["RIS (no heterogeneity adjustment)"], abs=1.0)
    assert rp["D² (diversity)"] == pytest.approx(rrr_["D² (diversity)"], abs=1e-6)
    zp, zr = table(py, "Cumulative Z-curve"), table(rr, "Cumulative Z-curve")
    for a, b in zip(zp["rows"], zr["rows"]):
        assert a[0] == b[0] and a[6] == pytest.approx(b[6], abs=1e-6)
    bp, br = zp["rows"][-1][7], zr["rows"][-1][7]
    if br is not None:
        assert bp == pytest.approx(br, abs=0.02)
    assert rr["details"]["boundary_curve"]["t"]


def test_bayes_meta_binary_r_runs_and_agrees_within_mc_error():
    opts = {**ROLES, "chains": 2, "iterations": 4000, "burnin": 1000, "seed": 7}
    py = analyze(FIXTURE, "bayes_meta_binary", opts)
    rr = analyze(FIXTURE, "bayes_meta_binary_r", opts)
    sp, sr = table(py, "Posterior summary"), table(rr, "Posterior summary")
    assert [r_[0] for r_ in sr["rows"]] == [r_[0] for r_ in sp["rows"]]
    assert sp["rows"][0][1] == pytest.approx(sr["rows"][0][1], abs=0.15)  # median log OR within Monte Carlo error
    assert sr["rows"][0][6] < 1.1
    fit = dict(zip(table(rr, "Model fit")["columns"], table(rr, "Model fit")["rows"][0]))
    assert math.isfinite(fit["DIC"]) and rr["details"]["software"]["JAGS"]
    for tab in rr["tables"]:
        assert all(len(r_) == len(tab["columns"]) for r_ in tab["rows"]), tab["title"]
