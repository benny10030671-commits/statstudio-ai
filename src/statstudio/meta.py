"""Independent meta-analysis procedures for two-arm binary outcomes.

Implements inverse-variance common/random-effects pooling (DerSimonian–Laird,
REML, Paule–Mandel), Hartung–Knapp confidence intervals, prediction intervals,
Peto and Mantel–Haenszel common-effect odds ratios, subgroup tests, Egger's
regression test, univariable mixed-effects meta-regression (Knapp–Hartung),
a Bayesian binomial–normal hierarchical model fitted by an adaptive
Metropolis-within-Gibbs sampler, and trial sequential analysis with
Lan–DeMets O'Brien–Fleming-type alpha-spending boundaries.

No SPSS, R or external meta-analysis code is used. Reference values for the
validation fixtures were produced with R packages meta/metafor/rjags and are
compared in validation/meta/compare_meta.py. Results keep float64 precision.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import optimize, stats


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _table(title, columns, rows):
    return {"title": title, "columns": columns, "rows": rows}


def _binary_frame(df, o, r):
    """Validate and return the per-study 2×2 counts in row order."""
    cols = [o["event_exp"], o["n_exp"], o["event_ctrl"], o["n_ctrl"]]
    if len(set(cols + [o["study"]])) != 5:
        raise ValueError("研究標籤與四個計數欄位必須互不相同。")
    for c in cols:
        if not pd.api.types.is_numeric_dtype(df[c]):
            raise ValueError(f"「{c}」必須為數值欄位。")
    data = df.loc[:, [o["study"]] + cols].copy()
    data.columns = ["study", "e1", "n1", "e2", "n2"]
    data["_orig_index"] = df.index
    before = len(data)
    data = data.dropna(subset=["study", "e1", "n1", "e2", "n2"])
    if len(data) < before:
        r["warnings"].append(f"排除 {before-len(data)} 列含缺失計數的研究。")
    for c in ("e1", "n1", "e2", "n2"):
        v = data[c].to_numpy(dtype=float)
        if np.any(v < 0) or np.any(v != np.round(v)):
            raise ValueError(f"「{c}」必須為非負整數（事件數與人數）。手動加 0.5 的連續性校正請移除，由程式處理。")
    if np.any(data["e1"] > data["n1"]) or np.any(data["e2"] > data["n2"]):
        raise ValueError("事件數不可大於人數。")
    if np.any(data["n1"] <= 0) or np.any(data["n2"] <= 0):
        raise ValueError("每個組別的人數必須大於 0。")
    if data["study"].duplicated().any():
        raise ValueError("研究標籤不可重複。")
    data["study"] = data["study"].astype(str)
    return data.reset_index(drop=True)


def _effects(data, measure, incr):
    """Study-level log effect and variance with continuity correction.

    incr is added to all four cells of a study with any zero cell (the
    meta/metafor default). Studies with zero events (or all events) in both
    arms are flagged as not estimable and excluded from inverse-variance pooling.
    """
    e1 = data["e1"].to_numpy(float); n1 = data["n1"].to_numpy(float)
    e2 = data["e2"].to_numpy(float); n2 = data["n2"].to_numpy(float)
    a, b, c, d = e1, n1 - e1, e2, n2 - e2
    zero = (a == 0) | (b == 0) | (c == 0) | (d == 0)
    double_zero = ((a == 0) & (c == 0)) | ((b == 0) & (d == 0))
    cc = np.where(zero & ~double_zero, incr, 0.0)
    a2, b2, c2, d2 = a + cc, b + cc, c + cc, d + cc
    with np.errstate(divide="ignore", invalid="ignore"):
        if measure == "OR":
            yi = np.log(a2 * d2 / (b2 * c2))
            vi = 1 / a2 + 1 / b2 + 1 / c2 + 1 / d2
        else:  # RR
            n1c, n2c = n1 + 2 * cc, n2 + 2 * cc
            yi = np.log((a2 / n1c) / (c2 / n2c))
            vi = 1 / a2 - 1 / n1c + 1 / c2 - 1 / n2c
    usable = ~double_zero
    return yi, vi, usable, cc


def _tau2(yi, vi, method):
    k = len(yi)
    w = 1 / vi
    theta = np.sum(w * yi) / np.sum(w)
    q = float(np.sum(w * (yi - theta) ** 2))
    df = k - 1
    if k < 2:
        return 0.0, q, df
    if method == "DL":
        c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
        return float(max(0.0, (q - df) / c)), q, df
    if method == "PM":
        def f(t2):
            ww = 1 / (vi + t2)
            th = np.sum(ww * yi) / np.sum(ww)
            return float(np.sum(ww * (yi - th) ** 2) - df)
        if f(0.0) <= 0:
            return 0.0, q, df
        hi = 1.0
        while f(hi) > 0 and hi < 1e6:
            hi *= 4
        return float(optimize.brentq(f, 0.0, hi, xtol=1e-12)), q, df
    if method == "REML":
        def negll(t2):
            ww = 1 / (vi + t2)
            th = np.sum(ww * yi) / np.sum(ww)
            return 0.5 * (np.sum(np.log(vi + t2)) + np.log(np.sum(ww)) + np.sum(ww * (yi - th) ** 2))
        upper = max(10.0, 50 * float(np.var(yi)) + 10 * float(np.max(vi)))
        res = optimize.minimize_scalar(negll, bounds=(0.0, upper), method="bounded", options={"xatol": 1e-10})
        t2 = float(res.x)
        if negll(0.0) <= negll(t2):
            t2 = 0.0
        return t2, q, df
    raise ValueError("未知的 tau² 估計法。")


def _tau2_ci(yi, vi, level=0.95):
    """Q-profile confidence interval for tau² (Viechtbauer 2007)."""
    k = len(yi)
    if k < 3:
        return None, None
    lo_q = stats.chi2.ppf((1 - level) / 2, k - 1)
    hi_q = stats.chi2.ppf((1 + level) / 2, k - 1)

    def qgen(t2):
        ww = 1 / (vi + t2)
        th = np.sum(ww * yi) / np.sum(ww)
        return float(np.sum(ww * (yi - th) ** 2))
    q0 = qgen(0.0)
    upper = 1.0
    while qgen(upper) > lo_q and upper < 1e8:
        upper *= 4
    lower_ci = 0.0 if q0 < hi_q else float(optimize.brentq(lambda t: qgen(t) - hi_q, 0.0, upper, xtol=1e-12))
    upper_ci = 0.0 if q0 < lo_q else float(optimize.brentq(lambda t: qgen(t) - lo_q, 0.0, upper, xtol=1e-12))
    return lower_ci, upper_ci


def _pool(yi, vi, tau2, confidence, hakn=False):
    w = 1 / (vi + tau2)
    theta = float(np.sum(w * yi) / np.sum(w))
    k = len(yi)
    se = float(math.sqrt(1 / np.sum(w)))
    if hakn and k > 1:
        se = float(math.sqrt(np.sum(w * (yi - theta) ** 2) / ((k - 1) * np.sum(w))))
        crit = stats.t.ppf((1 + confidence) / 2, k - 1)
        statistic = theta / se if se > 0 else float("nan")
        p = 2 * stats.t.sf(abs(statistic), k - 1) if se > 0 else float("nan")
    else:
        crit = stats.norm.ppf((1 + confidence) / 2)
        statistic = theta / se
        p = 2 * stats.norm.sf(abs(statistic))
    return {"estimate": theta, "se": se, "lower": theta - crit * se, "upper": theta + crit * se, "statistic": float(statistic), "p": float(p), "weights": w}


def _peto(data, confidence):
    e1 = data["e1"].to_numpy(float); n1 = data["n1"].to_numpy(float)
    e2 = data["e2"].to_numpy(float); n2 = data["n2"].to_numpy(float)
    n = n1 + n2; t = e1 + e2
    usable = (t > 0) & (t < n)
    if usable.sum() == 0:
        return None
    e1, n1, e2, n2, n, t = (x[usable] for x in (e1, n1, e2, n2, n, t))
    o_minus_e = e1 - n1 * t / n
    v = n1 * n2 * t * (n - t) / (n ** 2 * (n - 1))
    theta = float(np.sum(o_minus_e) / np.sum(v))
    se = float(1 / math.sqrt(np.sum(v)))
    z = stats.norm.ppf((1 + confidence) / 2)
    return {"estimate": theta, "se": se, "lower": theta - z * se, "upper": theta + z * se, "statistic": theta / se, "p": float(2 * stats.norm.sf(abs(theta / se))), "k": int(usable.sum())}


def _mantel_haenszel(data, confidence):
    """Common-effect MH odds ratio with Robins–Greenland–Breslow variance; no continuity correction."""
    a = data["e1"].to_numpy(float); n1 = data["n1"].to_numpy(float)
    c = data["e2"].to_numpy(float); n2 = data["n2"].to_numpy(float)
    b, d = n1 - a, n2 - c
    n = n1 + n2
    usable = ~(((a == 0) & (c == 0)) | ((b == 0) & (d == 0)))
    if usable.sum() == 0:
        return None
    a, b, c, d, n = (x[usable] for x in (a, b, c, d, n))
    r_i, s_i = a * d / n, b * c / n
    R, S = np.sum(r_i), np.sum(s_i)
    if R == 0 or S == 0:
        return None
    p_i, q_i = (a + d) / n, (b + c) / n
    var = np.sum(p_i * r_i) / (2 * R ** 2) + np.sum(p_i * s_i + q_i * r_i) / (2 * R * S) + np.sum(q_i * s_i) / (2 * S ** 2)
    theta, se = float(math.log(R / S)), float(math.sqrt(var))
    z = stats.norm.ppf((1 + confidence) / 2)
    return {"estimate": theta, "se": se, "lower": theta - z * se, "upper": theta + z * se, "statistic": theta / se, "p": float(2 * stats.norm.sf(abs(theta / se))), "k": int(usable.sum())}


def _egger(yi, vi):
    """Egger regression: standardized effect on precision (unweighted OLS), intercept test."""
    k = len(yi)
    if k < 3:
        return None
    se = np.sqrt(vi)
    x = 1 / se
    y = yi / se
    X = np.column_stack([np.ones(k), x])
    beta, res, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sigma2 = float(np.sum(resid ** 2) / (k - 2)) if k > 2 else float("nan")
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se_int = math.sqrt(cov[0, 0])
    t = beta[0] / se_int if se_int > 0 else float("nan")
    p = 2 * stats.t.sf(abs(t), k - 2)
    return {"intercept": float(beta[0]), "se": se_int, "t": float(t), "p": float(p), "df": k - 2}


def _exp(x):
    return None if x is None else float(math.exp(x))


# ----------------------------------------------------------------------------
# 1. meta_binary
# ----------------------------------------------------------------------------

def meta_binary(df, o, r):
    data = _binary_frame(df, o, r)
    measure, incr, conf = o["measure"], float(o["cc"]), o["confidence"]
    yi_all, vi_all, usable, cc = _effects(data, measure, incr)
    label = measure
    if (~usable).any():
        r["warnings"].append("兩組皆無事件（或皆為事件）的研究無法估計效應，已排除於反變異數合併之外：" + ", ".join(data.loc[~usable, "study"]))
    if (cc > 0).any():
        r["warnings"].append(f"對含零格的研究四格各加 {incr} 作連續性校正：" + ", ".join(data.loc[cc > 0, "study"]) + "。Peto 與 MH 估計不使用此校正。")
    yi, vi = yi_all[usable], vi_all[usable]
    k = int(usable.sum())
    if k < 1:
        raise ValueError("沒有可估計的研究。")
    tau2, q, dfq = _tau2(yi, vi, o["tau2_method"])
    fe = _pool(yi, vi, 0.0, conf)
    re = _pool(yi, vi, tau2, conf)
    re_hk = _pool(yi, vi, tau2, conf, hakn=True) if k > 1 else None
    p_q = float(stats.chi2.sf(q, dfq)) if dfq > 0 else None
    i2 = float(max(0.0, (q - dfq) / q) * 100) if q > 0 and dfq > 0 else (0.0 if dfq > 0 else None)
    h = float(math.sqrt(q / dfq)) if dfq > 0 else None
    t2_lo, t2_hi = _tau2_ci(yi, vi, conf)
    # prediction interval: t with k-1 df (meta >= 7 default method.predict = "V")
    if k >= 3:
        tcrit = stats.t.ppf((1 + conf) / 2, k - 1)
        pse = math.sqrt(tau2 + re["se"] ** 2)
        pred = (re["estimate"] - tcrit * pse, re["estimate"] + tcrit * pse)
    else:
        pred = (None, None)
    # per-study table
    rows = []
    wfe = fe["weights"] / fe["weights"].sum() * 100
    wre = re["weights"] / re["weights"].sum() * 100
    j = 0
    for i, row in data.iterrows():
        if usable[i]:
            z = stats.norm.ppf((1 + conf) / 2)
            rows.append([row["study"], int(row["e1"]), int(row["n1"]), int(row["e2"]), int(row["n2"]), math.exp(yi_all[i]), math.exp(yi_all[i] - z * math.sqrt(vi_all[i])), math.exp(yi_all[i] + z * math.sqrt(vi_all[i])), float(yi_all[i]), float(math.sqrt(vi_all[i])), float(wfe[j]), float(wre[j]), float(cc[i]), "yes"])
            j += 1
        else:
            rows.append([row["study"], int(row["e1"]), int(row["n1"]), int(row["e2"]), int(row["n2"]), None, None, None, None, None, None, None, 0.0, "no (not estimable)"])
    r["tables"].append(_table("Study estimates", ["Study", "Events (exp)", "N (exp)", "Events (ctrl)", "N (ctrl)", label, f"{label} lower", f"{label} upper", f"log {label}", "SE", "Weight common %", "Weight random %", "Continuity correction", "Pooled"], rows))
    pooled_rows = [["Common effect (inverse variance)", k, _exp(fe["estimate"]), _exp(fe["lower"]), _exp(fe["upper"]), fe["estimate"], fe["se"], fe["statistic"], fe["p"], "z"],
                   [f"Random effects (inverse variance, {o['tau2_method']})", k, _exp(re["estimate"]), _exp(re["lower"]), _exp(re["upper"]), re["estimate"], re["se"], re["statistic"], re["p"], "z"]]
    if re_hk is not None:
        pooled_rows.append([f"Random effects, Hartung–Knapp CI ({o['tau2_method']})", k, _exp(re_hk["estimate"]), _exp(re_hk["lower"]), _exp(re_hk["upper"]), re_hk["estimate"], re_hk["se"], re_hk["statistic"], re_hk["p"], f"t({k-1})"])
    if measure == "OR":
        peto = _peto(data, conf)
        if peto:
            pooled_rows.append(["Peto common-effect OR (no continuity correction)", peto["k"], _exp(peto["estimate"]), _exp(peto["lower"]), _exp(peto["upper"]), peto["estimate"], peto["se"], peto["statistic"], peto["p"], "z"])
        mh = _mantel_haenszel(data, conf)
        if mh:
            pooled_rows.append(["Mantel–Haenszel common-effect OR (no continuity correction)", mh["k"], _exp(mh["estimate"]), _exp(mh["lower"]), _exp(mh["upper"]), mh["estimate"], mh["se"], mh["statistic"], mh["p"], "z"])
    r["tables"].append(_table("Pooled estimates", ["Model", "k", label, f"{label} lower", f"{label} upper", f"log {label}", "SE", "Test statistic", "p", "Reference distribution"], pooled_rows))
    r["tables"].append(_table("Heterogeneity", ["tau²", "tau² lower (Q-profile)", "tau² upper (Q-profile)", "tau", "I² %", "H", "Q", "df", "p (Q)", f"Prediction interval lower ({label})", f"Prediction interval upper ({label})"],
                              [[tau2, t2_lo, t2_hi, math.sqrt(tau2), i2, h, q, dfq, p_q, _exp(pred[0]), _exp(pred[1])]]))
    egg = _egger(yi, vi)
    if egg:
        note = "k < 10：Egger 檢定效力不足，僅供參考" if k < 10 else ""
        r["tables"].append(_table("Small-study effects (Egger regression)", ["k", "Intercept", "SE", "t", "df", "p", "Note"], [[k, egg["intercept"], egg["se"], egg["t"], egg["df"], egg["p"], note]]))
    # totals
    r["tables"].append(_table("Event totals", ["Arm", "Events", "N", "Proportion"], [["Experimental", int(data["e1"].sum()), int(data["n1"].sum()), float(data["e1"].sum() / data["n1"].sum())], ["Control", int(data["e2"].sum()), int(data["n2"].sum()), float(data["e2"].sum() / data["n2"].sum())]]))
    # subgroups
    if o.get("subgroup"):
        sub = df.loc[data["_orig_index"], o["subgroup"]].reset_index(drop=True)
        if sub.isna().any():
            r["warnings"].append("子群欄位含缺失值的研究不納入子群分析。")
        levels = [lv for lv in pd.unique(sub.dropna())]
        try:
            levels = sorted(levels)
        except TypeError:
            pass
        srows, group_est, group_se = [], [], []
        for lv in levels:
            mask = (sub == lv).to_numpy() & usable
            kk = int(mask.sum())
            if kk == 0:
                continue
            ys, vs = yi_all[mask], vi_all[mask]
            t2s, qs, dfs = _tau2(ys, vs, o["tau2_method"])
            ps = _pool(ys, vs, t2s, conf)
            i2s = float(max(0.0, (qs - dfs) / qs) * 100) if qs > 0 and dfs > 0 else (0.0 if dfs > 0 else None)
            srows.append([str(lv), kk, _exp(ps["estimate"]), _exp(ps["lower"]), _exp(ps["upper"]), t2s, i2s, qs, dfs, float(stats.chi2.sf(qs, dfs)) if dfs > 0 else None])
            group_est.append(ps["estimate"]); group_se.append(ps["se"])
        if len(group_est) >= 2:
            ge, gs = np.array(group_est), np.array(group_se)
            wg = 1 / gs ** 2
            tb = np.sum(wg * ge) / np.sum(wg)
            qb = float(np.sum(wg * (ge - tb) ** 2))
            dfb = len(ge) - 1
            srows.append(["Test for subgroup differences (random effects)", None, None, None, None, None, None, qb, dfb, float(stats.chi2.sf(qb, dfb))])
        r["tables"].append(_table("Subgroups", ["Subgroup", "k", label, f"{label} lower", f"{label} upper", "tau²", "I² %", "Q", "df", "p"], srows))
        if any(row[1] == 1 for row in srows if row[1] is not None):
            r["warnings"].append("至少一個子群只有 1 篇研究；子群差異檢定不具參考價值。")
    r["charts"].append({"kind": "scatter", "title": "Funnel plot data (log effect vs standard error)", "x": [float(x) for x in yi], "y": [float(math.sqrt(v)) for v in vi], "x_label": f"log {label}", "y_label": "Standard error"})
    r["details"].update(k_pooled=k, k_input=len(data), measure=measure, tau2_method=o["tau2_method"], continuity_correction=incr, double_zero_excluded=[s for s, u in zip(data["study"], usable) if not u])
    r["warnings"].append("統合分析為獨立實作；參照值以 R meta 8.5 / metafor 5.0 於固定資料集比對（見 validation/meta）。I² 與 Q 在研究數少時不穩定；子群與 Egger 檢定為探索性。")


# ----------------------------------------------------------------------------
# 2. meta_regression (univariable, mixed effects)
# ----------------------------------------------------------------------------

def meta_regression(df, o, r):
    data = _binary_frame(df, o, r)
    mod_name = o["moderator"]
    if mod_name in (o["event_exp"], o["n_exp"], o["event_ctrl"], o["n_ctrl"], o["study"]):
        raise ValueError("調節變數不可與計數欄位相同。")
    if not pd.api.types.is_numeric_dtype(df[mod_name]):
        raise ValueError("調節變數必須為數值欄位（類別請先編碼為 0/1）。")
    mod_all = df.loc[data["_orig_index"], mod_name].to_numpy(float)
    yi_all, vi_all, usable, cc = _effects(data, o["measure"], float(o["cc"]))
    keep = usable & np.isfinite(mod_all)
    dropped = int((~keep).sum())
    if dropped:
        r["warnings"].append(f"{dropped} 篇研究因效應不可估計或調節變數缺失而未納入迴歸。")
    yi, vi, x = yi_all[keep], vi_all[keep], mod_all[keep]
    k = len(yi)
    if k < 4:
        raise ValueError("單變量統合迴歸至少需要 4 篇可用研究；研究數少於 10 時結果僅供探索。")
    if np.std(x) == 0:
        raise ValueError("調節變數為常數。")
    X = np.column_stack([np.ones(k), x])
    p = 2

    def fit(t2):
        w = 1 / (vi + t2)
        W = np.diag(w)
        xtwx_inv = np.linalg.inv(X.T @ W @ X)
        beta = xtwx_inv @ X.T @ W @ yi
        return beta, xtwx_inv, w
    # tau² estimation
    method = o["tau2_method"]
    if method == "DL":
        beta0, inv0, w0 = fit(0.0)
        qe = float(np.sum(w0 * (yi - X @ beta0) ** 2))
        W0 = np.diag(w0)
        P = W0 - W0 @ X @ inv0 @ X.T @ W0
        tau2 = float(max(0.0, (qe - (k - p)) / np.trace(P)))
    else:  # REML
        def negll(t2):
            beta, inv, w = fit(t2)
            resid = yi - X @ beta
            return 0.5 * (np.sum(np.log(vi + t2)) + math.log(np.linalg.det(np.linalg.inv(inv))) + np.sum(w * resid ** 2))
        upper = max(10.0, 50 * float(np.var(yi)) + 10 * float(np.max(vi)))
        res = optimize.minimize_scalar(negll, bounds=(0.0, upper), method="bounded", options={"xatol": 1e-10})
        tau2 = float(res.x) if negll(res.x) < negll(0.0) else 0.0
    beta, inv, w = fit(tau2)
    resid = yi - X @ beta
    conf = o["confidence"]
    if o["knapp_hartung"] == "yes":
        s2 = float(np.sum(w * resid ** 2) / (k - p))
        cov = inv * s2
        dist, dfree = "t", k - p
        crit = stats.t.ppf((1 + conf) / 2, dfree)
    else:
        cov = inv
        dist, dfree = "z", None
        crit = stats.norm.ppf((1 + conf) / 2)
    se = np.sqrt(np.diag(cov))
    stat = beta / se
    pvals = 2 * (stats.t.sf(np.abs(stat), dfree) if dist == "t" else stats.norm.sf(np.abs(stat)))
    # residual heterogeneity with FE weights
    beta_fe, _, w_fe = fit(0.0)
    qe = float(np.sum(w_fe * (yi - X @ beta_fe) ** 2))
    p_qe = float(stats.chi2.sf(qe, k - p))
    tau2_0, _, _ = _tau2(yi, vi, method)
    r2 = float(max(0.0, 1 - tau2 / tau2_0) * 100) if tau2_0 > 0 else None
    qm = float(stat[1] ** 2)
    p_qm = float(pvals[1])
    r["tables"].append(_table("Meta-regression coefficients", ["Term", "Estimate (log scale)", "SE", f"Lower {int(conf*100)}% CI", f"Upper {int(conf*100)}% CI", "Statistic", "Reference distribution", "p", "exp(estimate)"],
                              [["Intercept", float(beta[0]), float(se[0]), float(beta[0] - crit * se[0]), float(beta[0] + crit * se[0]), float(stat[0]), dist if dfree is None else f"t({dfree})", float(pvals[0]), float(math.exp(beta[0]))],
                               [mod_name, float(beta[1]), float(se[1]), float(beta[1] - crit * se[1]), float(beta[1] + crit * se[1]), float(stat[1]), dist if dfree is None else f"t({dfree})", float(pvals[1]), float(math.exp(beta[1]))]]))
    r["tables"].append(_table("Meta-regression heterogeneity", ["k", "tau² residual", "tau² (no moderator)", "R² %", "Q_E (residual)", "df", "p (Q_E)", "Test of moderator", "p (moderator)"],
                              [[k, tau2, tau2_0, r2, qe, k - p, p_qe, qm, p_qm]]))
    r["tables"].append(_table("Studies in regression", ["Study", "Moderator", "log effect", "SE", "Weight %"], [[s, float(m), float(y), float(math.sqrt(v)), float(ww / w.sum() * 100)] for s, m, y, v, ww in zip(data.loc[keep, "study"], x, yi, vi, w)]))
    r["charts"].append({"kind": "scatter", "title": f"Bubble data: {mod_name} vs log effect", "x": [float(v) for v in x], "y": [float(v) for v in yi], "x_label": mod_name, "y_label": "log effect"})
    r["details"].update(k_used=k, tau2_method=method, knapp_hartung=o["knapp_hartung"])
    if k < 10:
        r["warnings"].append(f"僅 {k} 篇研究：統合迴歸為探索性（Cochrane 建議每個共變量至少 10 篇），切勿據此宣稱顯著調節效應。")


# ----------------------------------------------------------------------------
# 3. bayes_meta_binary
# ----------------------------------------------------------------------------

def _rhat_ess(chains):
    """Split-R̂ and a simple bulk ESS from initial positive sequence of autocorrelations."""
    m, n = chains.shape
    half = n // 2
    split = np.concatenate([chains[:, :half], chains[:, half:2 * half]], axis=0)
    mm, nn = split.shape
    means = split.mean(axis=1)
    b = nn * np.var(means, ddof=1)
    wv = np.mean(np.var(split, axis=1, ddof=1))
    var_hat = (nn - 1) / nn * wv + b / nn
    rhat = float(math.sqrt(var_hat / wv)) if wv > 0 else float("nan")
    # ESS via autocorrelation (Geyer initial positive sequence, averaged over chains)
    rho_sum = 0.0
    maxlag = min(nn - 2, 2000)
    acov = np.zeros(maxlag + 1)
    for c in split:
        cc = c - c.mean()
        f = np.fft.rfft(cc, n=2 * nn)
        ac = np.fft.irfft(f * np.conj(f))[: maxlag + 1] / nn
        acov += ac
    acov /= mm
    rho = 1 - (wv - acov) / var_hat
    # Geyer: sum pairs while positive
    t = 1
    tot = rho[0]
    while t + 1 <= maxlag:
        pair = rho[t] + rho[t + 1]
        if pair < 0:
            break
        tot += pair
        t += 2
    tau_int = -1 + 2 * tot
    ess = float(mm * nn / max(tau_int, 1e-12))
    return rhat, min(ess, float(m * n))


def _expit(x):
    return 1 / (1 + np.exp(-x))


def _binom_loglik(e, n, logit_p):
    """Binomial log-likelihood up to a constant, numerically stable."""
    return e * logit_p - n * np.logaddexp(0.0, logit_p)


def bayes_meta_binary(df, o, r):
    data = _binary_frame(df, o, r)
    e1 = data["e1"].to_numpy(float); n1 = data["n1"].to_numpy(float)
    e2 = data["e2"].to_numpy(float); n2 = data["n2"].to_numpy(float)
    k = len(data)
    if k < 2:
        raise ValueError("貝氏統合分析至少需要 2 篇研究。")
    chains, iters, burn = int(o["chains"]), int(o["iterations"]), int(o["burnin"])
    if chains < 2 or iters < 1000 or burn < 200:
        raise ValueError("chains ≥ 2、iterations ≥ 1000、burnin ≥ 200。")
    seed = int(o["seed"])
    model = o["model"]
    sd_d = float(o["prior_effect_sd"]); hn_tau = float(o["prior_tau_scale"]); sd_mu = float(o["prior_baseline_sd"])
    if min(sd_d, hn_tau, sd_mu) <= 0:
        raise ValueError("先驗尺度必須為正數。")
    rng = np.random.default_rng(seed)
    # initial values from observed log odds (with 0.5 correction)
    lo0 = np.log((e2 + 0.5) / (n2 - e2 + 0.5)); lo1 = np.log((e1 + 0.5) / (n1 - e1 + 0.5))
    mu = np.tile(lo0, (chains, 1)) + rng.normal(0, 0.1, (chains, k))
    delta = np.tile(lo1 - lo0, (chains, 1)) + rng.normal(0, 0.1, (chains, k))
    d = delta.mean(axis=1) + rng.normal(0, 0.1, chains)
    tau = np.full(chains, 0.3) * np.exp(rng.normal(0, 0.2, chains))
    if model == "fixed":
        delta = np.tile(d[:, None], (1, k)); tau = np.zeros(chains)
    step_mu = np.full((chains, k), 0.5); step_delta = np.full((chains, k), 0.5); step_tau = np.full(chains, 0.5); step_d = np.full(chains, 0.3)
    acc_mu = np.zeros((chains, k)); acc_delta = np.zeros((chains, k)); acc_tau = np.zeros(chains); acc_d = np.zeros(chains)
    total = burn + iters
    keep_d = np.empty((chains, iters)); keep_tau = np.empty((chains, iters)); keep_dev = np.empty((chains, iters))
    keep_delta_mean = np.zeros((chains, k)); keep_mu_mean = np.zeros((chains, k)); keep_delta_sq = np.zeros((chains, k))
    keep_delta_lo = []
    E1, N1, E2, N2 = (np.tile(x, (chains, 1)) for x in (e1, n1, e2, n2))

    def loglik(mu_, delta_):
        return _binom_loglik(E2, N2, mu_) + _binom_loglik(E1, N1, mu_ + delta_)

    ll = loglik(mu, delta)
    for it in range(total):
        # --- update mu_i (all studies at once; conditionally independent)
        prop = mu + rng.normal(0, 1, (chains, k)) * step_mu
        ll_prop = loglik(prop, delta)
        logr = (ll_prop - ll) + (-(prop ** 2) + mu ** 2) / (2 * sd_mu ** 2)
        acc = np.log(rng.uniform(size=(chains, k))) < logr
        mu = np.where(acc, prop, mu); ll = np.where(acc, ll_prop, ll); acc_mu += acc
        if model == "random":
            # --- update delta_i
            prop = delta + rng.normal(0, 1, (chains, k)) * step_delta
            ll_prop = loglik(mu, prop)
            t2 = (tau ** 2)[:, None]
            logr = (ll_prop - ll) + (-(prop - d[:, None]) ** 2 + (delta - d[:, None]) ** 2) / (2 * t2)
            acc = np.log(rng.uniform(size=(chains, k))) < logr
            delta = np.where(acc, prop, delta); ll = np.where(acc, ll_prop, ll); acc_delta += acc
            # --- Gibbs for d
            prec = 1 / sd_d ** 2 + k / tau ** 2
            mean = (delta.sum(axis=1) / tau ** 2) / prec
            d = mean + rng.normal(0, 1, chains) / np.sqrt(prec)
            # --- RW-MH on log tau with half-normal prior
            ltau = np.log(tau)
            prop_l = ltau + rng.normal(0, 1, chains) * step_tau
            prop_t = np.exp(prop_l)
            def logpost_tau(t):
                return -k * np.log(t) - np.sum((delta - d[:, None]) ** 2, axis=1) / (2 * t ** 2) - t ** 2 / (2 * hn_tau ** 2) + np.log(t)  # + Jacobian
            logr = logpost_tau(prop_t) - logpost_tau(tau)
            acc = np.log(rng.uniform(size=chains)) < logr
            tau = np.where(acc, prop_t, tau); acc_tau += acc
        else:
            # fixed effect: RW-MH on common d (delta_i = d)
            prop_d = d + rng.normal(0, 1, chains) * step_d
            prop_delta = np.tile(prop_d[:, None], (1, k))
            ll_prop = loglik(mu, prop_delta)
            logr = (ll_prop.sum(axis=1) - ll.sum(axis=1)) + (-(prop_d ** 2) + d ** 2) / (2 * sd_d ** 2)
            acc = np.log(rng.uniform(size=chains)) < logr
            d = np.where(acc, prop_d, d); delta = np.where(acc[:, None], prop_delta, delta); ll = np.where(acc[:, None], ll_prop, ll); acc_d += acc
        # --- adaptation during burn-in (Roberts–Rosenthal style, batches of 50)
        if it < burn and (it + 1) % 50 == 0:
            adj = min(0.1, 1 / math.sqrt((it + 1) / 50))
            step_mu *= np.exp(np.where(acc_mu / 50 > 0.44, adj, -adj)); acc_mu[:] = 0
            step_delta *= np.exp(np.where(acc_delta / 50 > 0.44, adj, -adj)); acc_delta[:] = 0
            step_tau *= np.exp(np.where(acc_tau / 50 > 0.44, adj, -adj)); acc_tau[:] = 0
            step_d *= np.exp(np.where(acc_d / 50 > 0.44, adj, -adj)); acc_d[:] = 0
        if it >= burn:
            j = it - burn
            keep_d[:, j] = d; keep_tau[:, j] = tau
            # deviance: -2 * full binomial log-likelihood (with constants)
            p0 = _expit(mu); p1 = _expit(mu + delta)
            dev = -2 * (stats.binom.logpmf(E2, N2, p0).sum(axis=1) + stats.binom.logpmf(E1, N1, p1).sum(axis=1))
            keep_dev[:, j] = dev
            keep_delta_mean += delta; keep_mu_mean += mu; keep_delta_sq += delta ** 2
    draws_d = keep_d.reshape(-1); draws_tau = keep_tau.reshape(-1)
    ors = np.exp(draws_d)
    conf = o["confidence"]
    lo_q, hi_q = (1 - conf) / 2 * 100, (1 + conf) / 2 * 100

    def summ(x):
        return [float(np.median(x)), float(np.mean(x)), float(np.std(x, ddof=1)), float(np.percentile(x, lo_q)), float(np.percentile(x, hi_q))]
    rh_d, ess_d = _rhat_ess(keep_d)
    rows = [["log OR (d)"] + summ(draws_d) + [rh_d, ess_d], ["OR = exp(d)"] + summ(ors) + [rh_d, ess_d]]
    if model == "random":
        rh_t, ess_t = _rhat_ess(keep_tau)
        rows.append(["tau (between-study SD, log OR)"] + summ(draws_tau) + [rh_t, ess_t])
        pred = np.exp(draws_d + rng.normal(0, 1, draws_d.size) * draws_tau)
        rows.append(["Predicted OR in a new study"] + summ(pred) + [None, None])
    r["tables"].append(_table("Posterior summary", ["Parameter", "Median", "Mean", "SD", f"{lo_q:g}%", f"{hi_q:g}%", "R-hat (split)", "ESS (Geyer IPS)"], rows))
    thresholds = [1.0, 0.9, 0.8, 0.75]
    r["tables"].append(_table("Posterior probabilities", ["Statement", "Probability"],
                              [[f"OR < {t:g}", float(np.mean(ors < t))] for t in thresholds] + [["OR > 1 (harm)", float(np.mean(ors > 1))], ["OR > 1.1", float(np.mean(ors > 1.1))]]))
    # DIC
    dbar = float(keep_dev.mean())
    mu_hat = keep_mu_mean.sum(axis=0) / (chains * iters); delta_hat = keep_delta_mean.sum(axis=0) / (chains * iters)
    dev_hat = float(-2 * (stats.binom.logpmf(e2, n2, _expit(mu_hat)).sum() + stats.binom.logpmf(e1, n1, _expit(mu_hat + delta_hat)).sum()))
    pd_ = dbar - dev_hat
    r["tables"].append(_table("Model fit", ["Model", "Dbar", "D(theta-bar)", "pD", "DIC"], [[model, dbar, dev_hat, pd_, dbar + pd_]]))
    # shrunken study effects
    dm = keep_delta_mean.sum(axis=0) / (chains * iters); dsq = keep_delta_sq.sum(axis=0) / (chains * iters)
    dsd = np.sqrt(np.maximum(dsq - dm ** 2, 0))
    r["tables"].append(_table("Study-specific (shrunken) log OR", ["Study", "Posterior mean", "Posterior SD", "OR"], [[s, float(m), float(sd), float(math.exp(m))] for s, m, sd in zip(data["study"], dm, dsd)]))
    r["charts"].append({"kind": "histogram", "title": "Posterior of OR", "values": [float(v) for v in ors[:: max(1, ors.size // 20000)]], "bins": 60, "x_label": "OR", "y_label": "Posterior density"})
    r["details"].update(model=model, chains=chains, iterations_per_chain=iters, burnin=burn, seed=seed, priors={"d": f"normal(0, sd={sd_d})", "tau": f"half-normal(scale={hn_tau})", "mu_i": f"normal(0, sd={sd_mu})"},
                        likelihood="binomial (logit link), study-specific baseline, exchangeable log OR", sampler="adaptive Metropolis-within-Gibbs (vectorised over chains)", k=k,
                        posterior_draws_d=[float(v) for v in draws_d[:: max(1, draws_d.size // 4000)]])
    if rh_d > 1.05 or (model == "random" and rows[2][6] is not None and rows[2][6] > 1.05):
        r["warnings"].append("R-hat > 1.05：鏈未充分收斂，請增加 iterations 或 burnin。")
    r["warnings"].append("貝氏模型：事件數以二項分布建模，不需連續性校正；兩組皆零事件的研究仍納入。先驗為弱資訊性，請以敏感度分析檢查。參照值以 rjags 相同模型比對。")


# ----------------------------------------------------------------------------
# 4. tsa_binary (trial sequential analysis)
# ----------------------------------------------------------------------------

def _obf_spending(t, alpha):
    """Total two-sided alpha spent by information fraction t.

    Lan–DeMets O'Brien–Fleming-type function applied to each side with alpha/2
    (the ldbounds / TSA convention): alpha_side*(t) = 2 - 2*Phi(z_{1-alpha/4}/sqrt(t)).
    """
    t = np.clip(t, 1e-9, 1.0)
    # survival function keeps precision for very small information fractions (1 - cdf underflows to 0 for t < ~0.05)
    return 4 * stats.norm.sf(stats.norm.ppf(1 - alpha / 4) / np.sqrt(t))


def lan_demets_boundaries(info_fractions, alpha=0.05, grid=0.005, zmax=12.0):
    """Two-sided symmetric Lan–DeMets boundaries with O'Brien–Fleming-type spending.

    Works on the Brownian-motion scale S(t)=Z(t)*sqrt(t); increments independent.
    Returns Z-scale boundaries for each information fraction (values > 1 spend all alpha at 1).
    When the alpha increment at a look is below 1e-8 (information fraction roughly < 0.05) the
    numerical grid cannot resolve the tail, so the closed-form first-look expression
    z = Phi^-1(1 - inc/2) is used; the rejection mass of earlier looks is negligible there.
    Boundaries are returned unclamped (they can exceed 8 at very small fractions).
    """
    t = np.asarray(info_fractions, float)
    bounds = []
    s = np.arange(-zmax, zmax + grid, grid)
    g = None
    prev_t, prev_c, prev_spent = 0.0, None, 0.0
    for tj in t:
        tj_eff = min(float(tj), 1.0)
        spent = float(_obf_spending(tj_eff, alpha))
        inc = max(spent - prev_spent, 0.0)
        if prev_c is None:
            # first look: S ~ N(0, t)
            sd = math.sqrt(tj_eff)
            g = stats.norm.pdf(s, 0, sd)
            c = sd * (stats.norm.isf(inc / 2) if inc > 0 else 38.0)
        else:
            dt = tj_eff - prev_t
            if dt <= 1e-12:
                # no new information: boundary unchanged, nothing to spend
                bounds.append(prev_c / math.sqrt(tj_eff) if tj_eff > 0 else None)
                continue
            inside = np.abs(s) <= prev_c
            # convolve surviving density with N(0, dt)
            kern = stats.norm.pdf(s[:, None] - s[None, :][:, inside], 0, math.sqrt(dt))
            g = (kern * g[inside][None, :]).sum(axis=1) * grid
            cum = np.cumsum(g) * grid
            total = cum[-1]
            if inc < 1e-8 or total <= 0:
                c = math.sqrt(tj_eff) * (stats.norm.isf(inc / 2) if inc > 0 else 38.0)
            else:
                # find c with mass outside |s|>c equal to inc (symmetric density → use upper tail inc/2)
                tail = total - cum  # mass above s
                idx = np.searchsorted(-tail, -inc / 2)
                idx = min(max(idx, 1), len(s) - 1)
                # linear interpolation between grid points
                t_hi, t_lo = tail[idx - 1], tail[idx]
                frac = (t_hi - inc / 2) / (t_hi - t_lo) if t_hi != t_lo else 0.0
                c = float(s[idx - 1] + frac * grid)
                c = max(c, 0.0)
        bounds.append(c / math.sqrt(tj_eff))
        prev_t, prev_c, prev_spent = tj_eff, c, spent
    return [float(b) if b is not None else None for b in bounds]


def tsa_binary(df, o, r):
    data = _binary_frame(df, o, r)
    order_col = o.get("order")
    if order_col:
        order_vals = df.loc[data["_orig_index"], order_col].to_numpy()
        if pd.isna(order_vals).any():
            raise ValueError("排序欄位含缺失值。")
        idx = np.argsort(order_vals, kind="stable")
        data = data.iloc[idx].reset_index(drop=True)
    alpha, power = float(o["alpha"]), float(o["power"])
    if not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("alpha 與 power 必須介於 0 與 1。")
    yi, vi, usable, cc = _effects(data, "OR", float(o["cc"]))
    if usable.sum() < 2:
        raise ValueError("至少需要 2 篇可估計的研究。")
    yi_u, vi_u = yi[usable], vi[usable]
    tau2, q, dfq = _tau2(yi_u, vi_u, o["tau2_method"])
    fe = _pool(yi_u, vi_u, 0.0, 0.95); re = _pool(yi_u, vi_u, tau2, 0.95)
    d2 = float(max(0.0, 1 - fe["se"] ** 2 / re["se"] ** 2)) if re["se"] > 0 else 0.0
    pc = float(data["e2"].sum() / data["n2"].sum()) if o["control_risk"] == 0 else float(o["control_risk"])
    if not 0 < pc < 1:
        raise ValueError("對照組事件比例必須介於 0 與 1。")
    if o["rrr"] == 0:
        # anticipated RRR from pooled RE odds ratio converted to risk at the control risk
        or_ = math.exp(re["estimate"])
        pe = or_ * pc / (1 - pc + or_ * pc)
        rrr = 1 - pe / pc
        rrr_source = "pooled random-effects estimate (converted from OR at the control event proportion)"
    else:
        rrr = float(o["rrr"]); rrr_source = "user-specified"
    if not 0 < rrr < 1:
        raise ValueError("相對風險下降 (RRR) 必須介於 0 與 1（有效益方向）。")
    pe = pc * (1 - rrr)
    pbar = (pc + pe) / 2
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    ris_fixed = 4 * (za + zb) ** 2 * pbar * (1 - pbar) / (pc - pe) ** 2
    ris = ris_fixed / (1 - d2) if d2 < 1 else float("inf")
    # cumulative meta-analysis
    # Studies without an estimable log OR (no events, or all events, in both arms) are excluded from the
    # sequential analysis altogether -- they add neither to the Z curve nor to the accrued information.
    # This is the convention of the TSA software / RTSA (zero-event trials are dropped).
    rows, fracs, excluded = [], [], []
    cum_n = 0
    cum_idx = []
    for i in range(len(data)):
        if not usable[i]:
            excluded.append(str(data.loc[i, "study"]))
            continue
        cum_n += int(data.loc[i, "n1"] + data.loc[i, "n2"])
        cum_idx.append(i)
        ys, vs = yi[cum_idx], vi[cum_idx]
        if len(cum_idx) >= 2:
            t2c, _, _ = _tau2(ys, vs, o["tau2_method"])
        else:
            t2c = 0.0
        pc_ = _pool(ys, vs, t2c, 0.95)
        z = pc_["estimate"] / pc_["se"]
        est = (math.exp(pc_["estimate"]), math.exp(pc_["lower"]), math.exp(pc_["upper"]))
        frac = cum_n / ris if math.isfinite(ris) else 0.0
        fracs.append(frac)
        rows.append([data.loc[i, "study"], cum_n, frac, est[0], est[1], est[2], z])
    bounds = lan_demets_boundaries([max(f, 1e-6) for f in fracs], alpha)
    out = []
    for row, b in zip(rows, bounds):
        z = row[6]
        crossed = (z is not None and b is not None and abs(z) >= b)
        out.append(row + [b, "yes" if crossed else "no", "yes" if (z is not None and abs(z) >= za) else "no"])
    r["tables"].append(_table("Required information size", ["Control event proportion", "Anticipated RRR", "RRR source", "Intervention event proportion", "alpha (two-sided)", "power", "RIS (no heterogeneity adjustment)", "D² (diversity)", "Diversity-adjusted RIS", "Accrued participants", "Accrued / RIS", "tau²", "I² %"],
                              [[pc, rrr, rrr_source, pe, alpha, power, ris_fixed, d2, ris, cum_n, cum_n / ris if math.isfinite(ris) else None, tau2, float(max(0.0, (q - dfq) / q) * 100) if q > 0 and dfq > 0 else 0.0]]))
    r["tables"].append(_table("Cumulative Z-curve", ["Study added", "Cumulative N", "Information fraction", "Cumulative OR", "Lower 95% CI", "Upper 95% CI", "Cumulative Z", "O'Brien–Fleming boundary (Lan–DeMets)", "Crossed monitoring boundary", "Conventional |Z| ≥ z(alpha/2)"], out))
    r["details"].update(k=len(data), k_analysed=len(cum_idx), excluded_studies=excluded, boundary="Lan–DeMets alpha-spending, O'Brien–Fleming-type, two-sided, efficacy/harm only (no futility boundaries)", ris=ris, d2=d2)
    if excluded:
        r["warnings"].append("TSA 排除兩組皆零（或皆全）事件的研究：" + "、".join(excluded) + "（與 TSA 軟體／RTSA 慣例一致，不計入累積資訊量）。")
    r["warnings"].append("TSA 只計算效益／危害監測邊界，未計算無效邊界；RRR 若取自合併估計屬事後假設，請同時報告預設 RRR 的結果。")
