"""Independent statistical procedures. No IBM code or runtime is used.

The public contract is METHODS + analyze(DataFrame, method, options). Results
retain floating-point precision; display rounding belongs to the client.
"""
from __future__ import annotations

import math
import warnings as pywarnings
from datetime import date, datetime
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster import hierarchy
from sklearn.cluster import KMeans
import statsmodels.api as sm


def _select(key, label, default, choices):
    return {"key": key, "label": label, "type": "select", "default": default, "choices": choices}


def _number(key, label, default):
    return {"key": key, "label": label, "type": "number", "default": default}


_CI = _number("confidence", "信賴水準 (0–1)", 0.95)
_STANDARD = _select("standardize", "以樣本標準差標準化", "yes", ["yes", "no"])
_ROTATION = _select("rotation", "旋轉", "none", ["none", "varimax"])
_LABEL_ORDER = _select("label_order", "群編號（centroid: 中心排序；native: 原生順序）", "centroid", ["centroid", "native"])


def _method(id_, label, description, roles, parameters=()):
    return {"id": id_, "label": label, "description": description, "roles": roles, "parameters": list(parameters)}


METHODS = [
    _method("descriptive", "描述統計", "平均數、樣本標準差、分位數、偏態與峰度。", {"variables": "multi"}, [_CI, _select("missing", "缺失處理", "available", ["available", "listwise"]), _select("quantile", "分位數插值法", "weibull", ["weibull", "linear", "hazen"])]),
    _method("frequencies", "次數分配", "次數、總百分比、有效百分比及累積有效百分比。", {"variables": "multi"}),
    _method("crosstabs", "交叉表與卡方", "Pearson 卡方、期望次數、Cramér's V；2×2 額外提供 Fisher。", {"x": "single", "y": "single"}),
    _method("ttest_one", "單一樣本 t 檢定", "以樣本變異數估計標準誤，雙尾檢定。", {"variables": "multi"}, [_number("test_value", "虛無假設平均數", 0), _CI]),
    _method("ttest_independent", "獨立樣本 t 檢定", "兩個組別，提供合併變異數及 Welch–Satterthwaite 檢定。", {"variables": "multi", "group": "single"}, [_CI, _select("variance", "變異數假設", "both", ["both", "pooled", "welch"])]),
    _method("ttest_paired", "成對樣本 t 檢定", "以 x−y 的完整配對差值進行雙尾 t 檢定。", {"x": "single", "y": "single"}, [_CI]),
    _method("anova", "單因子變異數分析", "固定效果單因子 ANOVA、Levene、η² 及 ω²；未含事後比較。", {"variables": "multi", "group": "single"}),
    _method("correlation", "相關分析", "Pearson、Spearman 或 Kendall τ-b，雙尾檢定。", {"variables": "multi"}, [_select("coefficient", "相關係數", "pearson", ["pearson", "spearman", "kendall"]), _select("missing", "缺失處理", "pairwise", ["pairwise", "listwise"]), _CI]),
    _method("linear_regression", "線性迴歸", "普通最小平方法，Enter 同時輸入數值預測變數。", {"target": "single", "predictors": "multi"}, [_CI, _select("intercept", "截距", "yes", ["yes", "no"])]),
    _method("logistic_regression", "二元邏輯斯迴歸", "Newton 最大概似估計；明列事件類別及編碼。", {"target": "single", "predictors": "multi"}, [_CI, _select("event", "事件類別排序", "last", ["last", "first"]), _number("max_iter", "最大迭代次數", 100)]),
    _method("pca", "主成分分析", "相關或共變異矩陣的對稱特徵分解；可用 Kaiser-normalized varimax。", {"variables": "multi"}, [_number("components", "成分數", 2), _select("matrix", "矩陣", "correlation", ["correlation", "covariance"]), _ROTATION]),
    _method("factor", "主軸因素分析", "SMC 初始共同性與迭代主軸抽取；可用 Kaiser-normalized varimax。", {"variables": "multi"}, [_number("factors", "因素數", 1), _ROTATION, _number("max_iter", "最大迭代次數", 100), _number("tolerance", "共同性收斂容許值", 0.000001)]),
    _method("kmeans", "K-means 分群", "Lloyd；可選 k-means++ 或前 k 個完整個案起始中心。停止規則尚未對齊 SPSS。", {"variables": "multi"}, [_number("clusters", "群數", 3), _STANDARD, _number("seed", "亂數種子", 42), _number("max_iter", "最大迭代次數", 300), _select("initialization", "初始中心", "kmeans++", ["kmeans++", "first"]), _LABEL_ORDER]),
    _method("hierarchical", "階層式分群", "可選歐氏或平方歐氏距離；Ward 僅允許歐氏距離。", {"variables": "multi"}, [_number("clusters", "群數", 3), _STANDARD, _select("linkage", "連結法", "ward", ["ward", "average", "complete", "single"]), _select("distance", "距離", "euclidean", ["euclidean", "sqeuclidean"]), _LABEL_ORDER]),
    _method("reliability", "信度分析", "Cronbach α、標準化 α、校正項目總分相關及刪題 α。", {"variables": "multi"}),
    _method("mann_whitney", "Mann–Whitney U", "兩個獨立組別；漸近法含同分校正，可選連續性校正。", {"x": "single", "group": "single"}, [_select("continuity", "連續性校正", "yes", ["yes", "no"])]),
    _method("wilcoxon", "Wilcoxon 符號等級", "成對 x−y；移除零差值，雙尾常態近似及同分校正。", {"x": "single", "y": "single"}, [_select("continuity", "連續性校正", "no", ["yes", "no"])]),
    _method("kruskal", "Kruskal–Wallis", "獨立組別的秩和檢定，含同分校正，漸近卡方 p 值。", {"x": "single", "group": "single"}),
]
_METHOD_MAP = {m["id"]: m for m in METHODS}


def _table(title, columns, rows):
    return {"title": title, "columns": columns, "rows": rows}


def _clean(value):
    """Strict JSON values; undefined numeric statistics are null, never NaN."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _validate(df, method, options):
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("資料必須為至少一列的 DataFrame。")
    if not df.columns.is_unique or any(not isinstance(c, str) for c in df.columns):
        raise ValueError("欄位名稱必須是互不重複的文字。")
    if method not in _METHOD_MAP:
        raise ValueError(f"不支援的分析方法：{method}")
    if not isinstance(options, dict):
        raise ValueError("options 必須為 JSON 物件。")
    spec = _METHOD_MAP[method]
    valid = set(spec["roles"]) | {p["key"] for p in spec["parameters"]}
    unknown = set(options) - valid
    if unknown:
        raise ValueError("未支援的選項（不會默默忽略）：" + ", ".join(sorted(map(str, unknown))))
    opts = dict(options)
    for role, mode in spec["roles"].items():
        val = opts.get(role)
        if mode == "multi":
            if not isinstance(val, list) or not val or any(not isinstance(v, str) for v in val):
                raise ValueError(f"{role} 必須是非空欄位名稱清單。")
            if len(set(val)) != len(val):
                raise ValueError(f"{role} 不可包含重複欄位。")
            if len(val) > 50:
                raise ValueError("單次分析最多選擇 50 個欄位。")
            names = val
        else:
            if not isinstance(val, str):
                raise ValueError(f"{role} 必須指定一個欄位名稱。")
            names = [val]
        absent = [n for n in names if n not in df.columns]
        if absent:
            raise ValueError(f"不存在的欄位：{', '.join(absent)}")
    for param in spec["parameters"]:
        key = param["key"]
        opts.setdefault(key, param["default"])
        if param["type"] == "select" and opts[key] not in param["choices"]:
            raise ValueError(f"{key} 必須是 {param['choices']} 之一。")
        if param["type"] == "number":
            val = opts[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"{key} 必須是有限數值。")
    if "confidence" in opts and not 0 < opts["confidence"] < 1:
        raise ValueError("confidence 必須大於 0 且小於 1。")
    for key in ("components", "factors", "clusters", "max_iter", "seed"):
        if key in opts:
            val = opts[key]
            if val != int(val) or val < (0 if key == "seed" else 1):
                raise ValueError(f"{key} 必須為{'非負' if key == 'seed' else '正'}整數。")
            opts[key] = int(val)
    if opts.get("seed", 0) >= 2**32:
        raise ValueError("seed 必須小於 2^32。")
    if opts.get("max_iter", 1) > 10000:
        raise ValueError("max_iter 不可超過 10000。")
    if "tolerance" in opts and not 0 < opts["tolerance"] < 1:
        raise ValueError("tolerance 必須介於 0 和 1。")
    if "x" in opts and "y" in opts and opts["x"] == opts["y"]:
        raise ValueError("x 與 y 必須是不同欄位。")
    if opts.get("target") in opts.get("predictors", []):
        raise ValueError("應變數不可同時作為預測變數。")
    if opts.get("group") in opts.get("variables", []) or ("group" in opts and opts.get("x") == opts["group"]):
        raise ValueError("分組欄位不可同時作為受測數值欄位。")
    return spec, opts


def _numeric(df, names):
    for name in names:
        if not pd.api.types.is_numeric_dtype(df[name]) or pd.api.types.is_complex_dtype(df[name]):
            raise ValueError(f"「{name}」必須為數值欄位；不會自動把文字或類別編碼成數字。")
        values = df[name].to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(values).any():
            raise ValueError(f"「{name}」包含無限值，請先修正資料。")


def _complete(df, names, result, minimum=2):
    data = df.loc[:, names].dropna()
    if len(data) < minimum:
        raise ValueError(f"移除缺失值後至少需要 {minimum} 筆完整資料。")
    result["details"].update(n_used=len(data), dropped=len(df)-len(data), missing_policy="listwise")
    if len(data) < len(df):
        result["warnings"].append(f"本分析以完整個案排除 {len(df)-len(data)} 列缺失資料。")
    return data


def _levels(values):
    result = list(pd.unique(values.dropna()))
    if len(result) > 100:
        raise ValueError("類別欄位超過 100 個不同值；請先確認欄位角色或重新分組。")
    if any(isinstance(v, (float, np.floating)) and not np.isfinite(v) for v in result):
        raise ValueError("類別欄位含無限值。")
    try:
        return sorted(result)
    except TypeError as exc:
        raise ValueError("同一類別欄位不可混合數字與文字類型。") from exc


def _nonconstant(array, names):
    arr = np.asarray(array, dtype=float)
    sd = np.std(arr, axis=0, ddof=1)
    bad = np.asarray(names)[np.atleast_1d(sd == 0)]
    if len(bad):
        raise ValueError("常數欄位無法進行此分析：" + ", ".join(bad))


def _t_values(diff, se, dfree, confidence):
    if se <= 0 or not np.isfinite(se):
        raise ValueError("標準誤為零或無法估计；不產生無定義的 t 檢定。")
    t = diff / se
    critical = stats.t.ppf((1 + confidence) / 2, dfree)
    return [t, dfree, 2 * stats.t.sf(abs(t), dfree), diff, se, diff-critical*se, diff+critical*se]


def _levene(samples):
    # SPSS's ordinary Levene uses absolute deviations from group means.
    with pywarnings.catch_warnings():
        pywarnings.simplefilter("ignore", RuntimeWarning)
        test = stats.levene(*samples, center="mean")
    return test.statistic, test.pvalue


def _descriptive(df, o, r):
    names = o["variables"]
    _numeric(df, names)
    data = df[names].dropna() if o["missing"] == "listwise" else df[names]
    rows = []
    used = {}
    for name in names:
        x = data[name].dropna().to_numpy(dtype=float)
        n = len(x)
        used[name] = n
        if not n:
            rows.append([name, 0, len(df)] + [None]*14)
            r["warnings"].append(f"「{name}」沒有有效值。")
            continue
        sd = x.std(ddof=1) if n > 1 else np.nan
        se = sd / np.sqrt(n)
        margin = stats.t.ppf((1+o["confidence"])/2, n-1)*se if n > 1 else np.nan
        skew = stats.skew(x, bias=False) if n > 2 and sd > 0 else np.nan
        kurt = stats.kurtosis(x, fisher=True, bias=False) if n > 3 and sd > 0 else np.nan
        q25, med, q75 = np.quantile(x, [0.25, 0.5, 0.75], method=o["quantile"])
        rows.append([name, n, len(df)-n, x.mean(), sd, sd**2, se, x.min(), x.max(), x.sum(), med, q25, q75, skew, kurt, x.mean()-margin, x.mean()+margin])
        r["charts"].append({"kind": "histogram", "title": f"{name} 分布", "values": x.tolist(), "bins": min(30, max(5, int(np.sqrt(n))))})
    r["tables"].append(_table("描述統計", ["Variable", "N", "Missing / excluded", "Mean", "Std. deviation", "Variance", "Std. error", "Minimum", "Maximum", "Sum", "Median", "Q25", "Q75", "Skewness", "Excess kurtosis", "CI lower", "CI upper"], rows))
    r["details"].update(n_used=used, dropped={name: len(df)-n for name, n in used.items()}, missing_policy=o["missing"], quantile_method=o["quantile"], variance_ddof=1)
    r["warnings"].append("分位數以所選插值法計算：weibull 為 (n+1)p、linear 為 1+(n−1)p、hazen 為 np+0.5；SPSS 各程序定義仍須分別驗證。")


def _frequencies(df, o, r):
    used = {}
    for name in o["variables"]:
        col = df[name]
        levels = _levels(col)
        n = col.notna().sum()
        used[name] = int(n)
        cumulative = 0
        rows, counts = [], []
        for level in levels:
            count = int((col == level).sum())
            counts.append(count)
            cumulative += count
            rows.append([level, count, 100*count/len(df), 100*count/n, 100*cumulative/n])
        if n < len(df):
            rows.append(["<missing>", int(len(df)-n), 100*(len(df)-n)/len(df), None, None])
        r["tables"].append(_table(f"{name} 次數分配", ["Value", "Frequency", "Percent", "Valid percent", "Cumulative valid percent"], rows))
        r["charts"].append({"kind": "bar", "title": f"{name} 次數", "labels": [str(v) for v in levels], "values": counts})
    r["details"].update(n_used=used, dropped={name: len(df)-n for name, n in used.items()}, missing_policy="exclude from valid percent, include in total percent")


def _crosstabs(df, o, r):
    data = _complete(df, [o["x"], o["y"]], r)
    a, b = _levels(data[o["x"]]), _levels(data[o["y"]])
    if min(len(a), len(b)) < 2:
        raise ValueError("交叉表兩個欄位各需至少兩種類別。")
    counts = pd.crosstab(data[o["x"]], data[o["y"]]).reindex(index=a, columns=b, fill_value=0).to_numpy()
    chi, p, dof, expected = stats.chi2_contingency(counts, correction=False)
    rown, coln = counts.sum(axis=1), counts.sum(axis=0)
    for title, values in [("觀察次數", counts), ("期望次數", expected), ("列百分比", counts/rown[:, None]*100), ("欄百分比", counts/coln[None, :]*100)]:
        r["tables"].append(_table(title, [o["x"]+" / "+o["y"]]+[str(v) for v in b], [[v]+list(values[i]) for i, v in enumerate(a)]))
    testrows = [["Pearson chi-square", chi, dof, p], ["Cramér's V", np.sqrt(chi/(counts.sum()*min(len(a)-1, len(b)-1))), None, None]]
    if counts.shape == (2, 2):
        yates = stats.chi2_contingency(counts, correction=True)
        fisher = stats.fisher_exact(counts, alternative="two-sided")
        testrows += [["Yates chi-square", yates.statistic, yates.dof, yates.pvalue], ["Fisher exact (odds ratio)", fisher.statistic, None, fisher.pvalue]]
        if not np.isfinite(fisher.statistic):
            r["warnings"].append("Fisher 的勝算比因零格而為無限值，表中以空值表示；雙尾精確 p 值仍有效。")
    r["tables"].append(_table("關聯檢定", ["Test", "Statistic", "df", "p (two-sided where applicable)"], testrows))
    r["details"].update(min_expected=float(expected.min()), cells_expected_below_5=int((expected < 5).sum()), chi_square=float(chi), df=int(dof), p_value=float(p))
    if (expected < 5).any():
        r["warnings"].append(f"{int((expected<5).sum())}/{expected.size} 格的期望次數小於 5；漸近卡方近似可能不佳。")


def _ttest_one(df, o, r):
    _numeric(df, o["variables"])
    rows, used = [], {}
    for name in o["variables"]:
        x = df[name].dropna().to_numpy(dtype=float)
        if len(x) < 2:
            raise ValueError(f"「{name}」至少需要 2 個有效值。")
        n = len(x)
        used[name] = n
        rows.append([name, n, x.mean(), x.std(ddof=1)] + _t_values(x.mean()-o["test_value"], x.std(ddof=1)/np.sqrt(n), n-1, o["confidence"]))
    r["tables"].append(_table("單一樣本 t 檢定", ["Variable", "N", "Mean", "Std. deviation", "t", "df", "p (two-sided)", "Mean difference", "Std. error difference", "CI lower", "CI upper"], rows))
    r["details"].update(n_used=used, dropped={name: len(df)-n for name, n in used.items()}, missing_policy="per variable", test_value=o["test_value"])


def _groups(df, numeric, group, minimum=2):
    data = df[[numeric, group]].dropna()
    levels = _levels(data[group])
    if len(levels) < 2:
        raise ValueError("至少需要兩個有效組別。")
    samples = [data.loc[data[group] == level, numeric].to_numpy(dtype=float) for level in levels]
    if any(len(x) < minimum for x in samples):
        raise ValueError(f"每個組別至少需要 {minimum} 個有效數值。")
    return levels, samples


def _ttest_independent(df, o, r):
    _numeric(df, o["variables"])
    rows, descriptives, levrows, used = [], [], [], {}
    alllevels = _levels(df[o["group"]])
    if len(alllevels) != 2:
        raise ValueError("獨立樣本 t 檢定需要剛好兩個組別，請先篩選資料。")
    for name in o["variables"]:
        levels, samples = _groups(df, name, o["group"])
        a, b = samples
        used[name] = len(a)+len(b)
        n1, n2, v1, v2 = len(a), len(b), a.var(ddof=1), b.var(ddof=1)
        for level, x in zip(levels, samples):
            descriptives.append([name, level, len(x), x.mean(), x.std(ddof=1), x.std(ddof=1)/np.sqrt(len(x))])
        levstat, levp = _levene(samples)
        levrows.append([name, levstat, levp])
        if not np.isfinite(levstat) or not np.isfinite(levp):
            r["warnings"].append(f"「{name}」Levene 檢定退化，無法得到有限統計量或 p 值；t 檢定另依所選變異數假設計算。")
        if o["variance"] in ("both", "pooled"):
            dof = n1+n2-2
            se = np.sqrt(((n1-1)*v1+(n2-1)*v2)/dof*(1/n1+1/n2))
            rows.append([name, "Equal variances assumed"]+_t_values(a.mean()-b.mean(), se, dof, o["confidence"]))
        if o["variance"] in ("both", "welch"):
            se2 = v1/n1+v2/n2
            if se2 == 0:
                raise ValueError("兩組皆為常數，無法估計 t 檢定。")
            dof = se2**2/((v1/n1)**2/(n1-1)+(v2/n2)**2/(n2-1))
            rows.append([name, "Equal variances not assumed"]+_t_values(a.mean()-b.mean(), np.sqrt(se2), dof, o["confidence"]))
    r["tables"] += [_table("組別統計", ["Variable", "Group", "N", "Mean", "Std. deviation", "Std. error mean"], descriptives), _table("Levene（中心為平均數）", ["Variable", "F", "p"], levrows), _table("獨立樣本 t 檢定", ["Variable", "Assumption", "t", "df", "p (two-sided)", "Mean difference", "Std. error difference", "CI lower", "CI upper"], rows)]
    r["details"].update(n_used=used, dropped={name: len(df)-n for name, n in used.items()}, group_order=alllevels, contrast="first minus second", missing_policy="per variable and group")


def _ttest_paired(df, o, r):
    names = [o["x"], o["y"]]
    _numeric(df, names)
    data = _complete(df, names, r)
    d = (data[o["x"]]-data[o["y"]]).to_numpy(dtype=float)
    r["tables"].append(_table("成對差值 t 檢定", ["Pair", "N", "Std. deviation difference", "t", "df", "p (two-sided)", "Mean difference", "Std. error difference", "CI lower", "CI upper"], [[o["x"]+" − "+o["y"], len(d), d.std(ddof=1)]+_t_values(d.mean(), d.std(ddof=1)/np.sqrt(len(d)), len(d)-1, o["confidence"])]))


def _anova(df, o, r):
    _numeric(df, o["variables"])
    used = {}
    for name in o["variables"]:
        levels, samples = _groups(df, name, o["group"])
        k, n = len(samples), sum(map(len, samples))
        used[name] = n
        grand = np.concatenate(samples).mean()
        between = sum(len(x)*(x.mean()-grand)**2 for x in samples)
        within = sum(((x-x.mean())**2).sum() for x in samples)
        if within <= 0:
            raise ValueError(f"「{name}」組內變異數為零，無法進行 ANOVA。")
        msw, msb = within/(n-k), between/(k-1)
        f = msb/msw
        r["tables"].append(_table(f"{name} ANOVA", ["Source", "Sum of squares", "df", "Mean square", "F", "p"], [["Between groups", between, k-1, msb, f, stats.f.sf(f, k-1, n-k)], ["Within groups", within, n-k, msw, None, None], ["Total", within+between, n-1, None, None, None]]))
        r["tables"].append(_table(f"{name} 效果量與同質性", ["Statistic", "Value", "p"], [["Eta squared", between/(between+within), None], ["Omega squared", (between-(k-1)*msw)/(between+within+msw), None], ["Levene (mean)", *_levene(samples)]]))
        r["tables"].append(_table(f"{name} 各組摘要", ["Group", "N", "Mean", "Std. deviation"], [[level, len(x), x.mean(), x.std(ddof=1)] for level, x in zip(levels, samples)]))
    r["details"].update(n_used=used, dropped={name: len(df)-n for name, n in used.items()}, missing_policy="per variable and group", posthoc="not implemented", model="fixed effects one-way")


def _correlation(df, o, r):
    names = o["variables"]
    if len(names) < 2:
        raise ValueError("相關分析至少需要兩個欄位。")
    _numeric(df, names)
    data = df[names].dropna() if o["missing"] == "listwise" else df[names]
    rows = []
    matrix = np.eye(len(names))
    for i, j in combinations(range(len(names)), 2):
        pair = data[[names[i], names[j]]].dropna()
        n = len(pair)
        a, b = (pair[col].to_numpy(dtype=float) for col in pair)
        lo, hi = None, None
        if n < 2 or a.std() == 0 or b.std() == 0:
            coefficient, p = np.nan, np.nan
            r["warnings"].append(f"{names[i]} / {names[j]}：少於 2 筆完整配對或為常數，相關及 p 值未定義。")
        elif n == 2:
            coefficient, p = float(np.sign((a[1]-a[0])*(b[1]-b[0]))), None
            r["warnings"].append(f"{names[i]} / {names[j]}：只有 2 筆完整配對，僅列相關係數，不列推論 p 值或信賴區間。")
        elif o["coefficient"] == "pearson":
            test = stats.pearsonr(a, b)
            coefficient, p = test.statistic, test.pvalue
            if n > 3:
                interval = test.confidence_interval(confidence_level=o["confidence"])
                lo, hi = interval.low, interval.high
        elif o["coefficient"] == "spearman":
            coefficient, p = stats.spearmanr(a, b)
        else:
            coefficient, p = stats.kendalltau(a, b, variant="b", method="asymptotic")
        matrix[i, j] = matrix[j, i] = coefficient
        rows.append([names[i], names[j], n, coefficient, p, lo, hi])
    for i, name in enumerate(names):
        values = data[name].dropna()
        if len(values) < 2 or values.std() == 0:
            matrix[i, i] = np.nan
    r["tables"] += [_table(o["coefficient"]+" 相關矩陣", ["Variable"]+names, [[name]+list(matrix[i]) for i, name in enumerate(names)]), _table("相關檢定（未做多重比較校正）", ["Variable 1", "Variable 2", "N", "Coefficient", "p (two-sided)", "Pearson CI lower", "Pearson CI upper"], rows)]
    r["details"].update(missing_policy=o["missing"], confidence_interval="Fisher z for Pearson with N > 3 only")
    if o["coefficient"] != "pearson":
        r["warnings"].append("秩相關採雙尾漸近 p 值；精確法與 SPSS 不同程序的同分處理尚未驗證。")


def _design(df, o, r, logistic=False):
    names = [o["target"]]+o["predictors"]
    _numeric(df, o["predictors"] if logistic else names)
    use_constant = logistic or o["intercept"] == "yes"
    data = _complete(df, names, r, minimum=len(o["predictors"])+int(use_constant)+1)
    x = data[o["predictors"]].astype(float)
    _nonconstant(x, o["predictors"])
    X = sm.add_constant(x, has_constant="add").to_numpy() if use_constant else x.to_numpy()
    labels = (["(Intercept)"] if use_constant else [])+o["predictors"]
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("預測矩陣秩不足（線性相依／完全共線性），請移除重複或冗餘變數。")
    condition = np.linalg.cond(X)
    if condition > 1e8:
        r["warnings"].append("預測矩陣條件數很大，估計可能不穩定；請檢查尺度與共線性。")
    r["details"]["condition_number"] = float(condition)
    return data, X, labels


def _linear(df, o, r):
    data, X, labels = _design(df, o, r)
    y = data[o["target"]].to_numpy(dtype=float)
    _nonconstant(y, [o["target"]])
    fit = sm.OLS(y, X).fit()
    ci = fit.conf_int(alpha=1-o["confidence"])
    beta = fit.params[-len(o["predictors"]):]*data[o["predictors"]].std(ddof=1).to_numpy()/y.std(ddof=1)
    betas = ([None] if o["intercept"] == "yes" else [])+beta.tolist()
    r["tables"].append(_table("迴歸係數", ["Term", "B", "Std. error", "Standardized beta", "t", "p (two-sided)", "CI lower", "CI upper"], [[name, fit.params[i], fit.bse[i], betas[i], fit.tvalues[i], fit.pvalues[i], *ci[i]] for i, name in enumerate(labels)]))
    r["tables"].append(_table("模型摘要", ["N", "R squared", "Adjusted R squared", "Residual std. error", "F", "Model df", "Residual df", "F p", "AIC", "BIC"], [[len(y), fit.rsquared, fit.rsquared_adj, np.sqrt(fit.mse_resid), fit.fvalue, fit.df_model, fit.df_resid, fit.f_pvalue, fit.aic, fit.bic]]))
    r["tables"].append(_table("ANOVA", ["Source", "Sum of squares", "df", "Mean square"], [["Regression", fit.ess, fit.df_model, fit.mse_model], ["Residual", fit.ssr, fit.df_resid, fit.mse_resid], ["Total (centered if intercept)", fit.centered_tss if o["intercept"] == "yes" else fit.uncentered_tss, fit.df_model+fit.df_resid, None]]))
    r["charts"].append({"kind": "scatter", "title": "殘差對預測值", "x": fit.fittedvalues.tolist(), "y": fit.resid.tolist(), "x_label": "Predicted", "y_label": "Residual"})
    r["details"].update(coefficients=dict(zip(labels, fit.params.tolist())), r_squared=float(fit.rsquared), solver="statsmodels OLS, nonrobust covariance", intercept=o["intercept"])
    if fit.ssr < np.finfo(float).eps * max(1, fit.centered_tss):
        r["warnings"].append("模型幾乎完全配適；係數標準誤與檢定對浮點誤差敏感。")


def _logistic(df, o, r):
    data, X, labels = _design(df, o, r, logistic=True)
    levels = _levels(data[o["target"]])
    if len(levels) != 2:
        raise ValueError("二元邏輯斯迴歸應變數必須剛好有兩個有效類別。")
    event = levels[-1] if o["event"] == "last" else levels[0]
    y = (data[o["target"]] == event).to_numpy(dtype=float)
    with pywarnings.catch_warnings(record=True) as captured:
        pywarnings.simplefilter("always")
        try:
            fit = sm.Logit(y, X).fit(method="newton", maxiter=o["max_iter"], tol=1e-8, disp=False)
        except (np.linalg.LinAlgError, ValueError) as exc:
            raise ValueError("邏輯斯模型無法估計：請檢查完全分離、共線性與樣本數。") from exc
    if any("separation" in str(w.message).lower() for w in captured):
        raise ValueError("偵測到完全分離；最大概似係數沒有有限解，請改用適合的方法。")
    for warning in captured:
        r["warnings"].append("Logit 計算警告：" + str(warning.message))
    if not fit.mle_retvals.get("converged", False) or not np.isfinite(fit.params).all() or not np.isfinite(fit.bse).all():
        raise ValueError("邏輯斯模型未收斂或資訊矩陣無法估計；不提供誤導性的係數表。")
    ci = fit.conf_int(alpha=1-o["confidence"])
    with np.errstate(over="ignore"):
        odds, odds_ci = np.exp(fit.params), np.exp(ci)
    pred = fit.predict(X)
    ll0 = len(y)*(y.mean()*np.log(y.mean())+(1-y.mean())*np.log(1-y.mean()))
    lr, dof = 2*(fit.llf-ll0), X.shape[1]-1
    cs = 1-np.exp((2/len(y))*(ll0-fit.llf))
    nk = cs/(1-np.exp(2*ll0/len(y)))
    r["tables"].append(_table("邏輯斯係數", ["Term", "B", "Std. error", "Wald chi-square", "df", "p", "Exp(B)", "OR CI lower", "OR CI upper"], [[name, fit.params[i], fit.bse[i], fit.tvalues[i]**2, 1, fit.pvalues[i], odds[i], *odds_ci[i]] for i, name in enumerate(labels)]))
    r["tables"].append(_table("模型摘要", ["N", "−2 Log likelihood", "LR chi-square", "df", "LR p", "Cox–Snell R squared", "Nagelkerke R squared", "McFadden R squared", "Iterations"], [[len(y), -2*fit.llf, lr, dof, stats.chi2.sf(lr, dof), cs, nk, 1-fit.llf/ll0, fit.mle_retvals.get("iterations")]]))
    predicted = pred >= .5
    r["tables"].append(_table("分類表（臨界值 0.5）", ["Observed", "Predicted 0", "Predicted 1"], [[0, int(((y == 0)&~predicted).sum()), int(((y == 0)&predicted).sum())], [1, int(((y == 1)&~predicted).sum()), int(((y == 1)&predicted).sum())]]))
    r["details"].update(event_level=event, coding=[{"level": v, "code": int(v == event)} for v in levels], coefficients=dict(zip(labels, fit.params.tolist())), converged=True, solver="Newton, tol=1e-8", cutoff=0.5)
    if np.any(~np.isfinite(odds_ci)):
        r["warnings"].append("部分勝算比信賴界限溢位，以空值顯示；請檢查估計不穩定或近乎分離。")


def _canonical_sign(loadings):
    signs = np.sign(loadings[np.abs(loadings).argmax(axis=0), np.arange(loadings.shape[1])])
    return loadings * np.where(signs == 0, 1, signs)


def _varimax(loadings, max_iter=1000, tol=1e-8):
    scale = np.sqrt((loadings**2).sum(axis=1))
    if (scale == 0).any():
        raise ValueError("零共同性無法做 Kaiser 正規化旋轉。")
    normalized = loadings/scale[:, None]
    rotation = np.eye(loadings.shape[1])
    last = 0.0
    for step in range(max_iter):
        projected = normalized @ rotation
        u, s, vh = np.linalg.svd(normalized.T @ (projected**3-projected @ np.diag((projected**2).sum(axis=0))/len(loadings)))
        rotation = u @ vh
        criterion = s.sum()
        if step and abs(criterion-last) <= tol*max(1, abs(last)):
            return _canonical_sign(normalized @ rotation*scale[:, None]), step+1
        last = criterion
    raise ValueError("Varimax 旋轉未收斂。")


def _multivariate_data(df, o, r, minimum_variables=2):
    names = o["variables"]
    if len(names) < minimum_variables:
        raise ValueError(f"此分析至少需要 {minimum_variables} 個數值欄位。")
    _numeric(df, names)
    data = _complete(df, names, r, minimum=3)
    array = data.to_numpy(dtype=float)
    _nonconstant(array, names)
    return data, array


def _pca(df, o, r):
    _, array = _multivariate_data(df, o, r)
    names, k = o["variables"], o["components"]
    if k > min(array.shape):
        raise ValueError("成分數不可大於變數數或有效樣本數。")
    matrix = np.corrcoef(array, rowvar=False) if o["matrix"] == "correlation" else np.cov(array, rowvar=False, ddof=1)
    eigen, vectors = np.linalg.eigh(matrix)
    order = np.argsort(eigen)[::-1]
    eigen, vectors = eigen[order], vectors[:, order]
    eigen = np.maximum(eigen, 0)
    loads = _canonical_sign(vectors[:, :k]*np.sqrt(eigen[:k]))
    original = loads.copy()
    if o["rotation"] == "varimax":
        loads, iterations = _varimax(loads)
        r["details"]["rotation_iterations"] = iterations
    explained = eigen/eigen.sum()*100
    r["tables"] += [_table("初始特徵值", ["Component", "Eigenvalue", "% variance", "Cumulative %"], [[i+1, val, explained[i], explained[:i+1].sum()] for i, val in enumerate(eigen)]), _table("成分負荷量"+("（旋轉後）" if o["rotation"] != "none" else ""), ["Variable"]+[f"Component {i+1}" for i in range(k)], [[name]+list(loads[i]) for i, name in enumerate(names)]), _table("共同性", ["Variable", "Initial", "Extraction"], [[name, matrix[i, i], (original[i]**2).sum()] for i, name in enumerate(names)])]
    r["charts"].append({"kind": "bar", "title": "陡坡圖：初始特徵值", "labels": [str(i+1) for i in range(len(eigen))], "values": eigen.tolist()})
    r["details"].update(eigenvalues=eigen.tolist(), loadings=loads.tolist(), sign_convention="largest absolute loading positive", matrix=o["matrix"])
    r["warnings"].append("成分正負號不具識別性；旋轉排序與停止規則尚未與 SPSS 驗證。未提供成分分數。")


def _factor(df, o, r):
    _, array = _multivariate_data(df, o, r)
    names, k = o["variables"], o["factors"]
    p = len(names)
    if not 1 <= k < p or len(array) <= p:
        raise ValueError("因素數需小於變數數，且完整樣本數需大於變數數。")
    if ((p-k)**2-p-k)/2 < 0:
        raise ValueError("指定因素數使因素模型自由度為負；請減少因素數或增加變數。")
    corr = np.corrcoef(array, rowvar=False)
    if np.linalg.matrix_rank(corr) < p:
        raise ValueError("相關矩陣奇異，无法計算 SMC 初始共同性。")
    inverse = np.linalg.inv(corr)
    initial = 1-1/np.diag(inverse)
    communalities = initial.copy()
    converged = False
    for iteration in range(o["max_iter"]):
        reduced = corr.copy()
        np.fill_diagonal(reduced, communalities)
        eigen, vectors = np.linalg.eigh(reduced)
        order = np.argsort(eigen)[::-1][:k]
        if (eigen[order] <= 0).any():
            raise ValueError("指定因素數包含非正特徵值；請减少因素數。")
        loads = vectors[:, order]*np.sqrt(eigen[order])
        updated = (loads**2).sum(axis=1)
        delta = np.max(np.abs(updated-communalities))
        communalities = updated
        if (updated > 1+o["tolerance"]).any():
            raise ValueError("發生 Heywood case（共同性 > 1）；此因素解不適當。")
        if delta < o["tolerance"]:
            converged = True
            break
    if not converged:
        raise ValueError("主軸因素分析未在指定迭代內收斂；請檢查因素數與資料。")
    loads = _canonical_sign(loads)
    if o["rotation"] == "varimax":
        loads, rotation_iterations = _varimax(loads)
        r["details"]["rotation_iterations"] = rotation_iterations
    partial = -inverse/np.sqrt(np.outer(np.diag(inverse), np.diag(inverse)))
    np.fill_diagonal(partial, 0)
    offcorr = corr.copy()
    np.fill_diagonal(offcorr, 0)
    kmo = (offcorr**2).sum()/((offcorr**2).sum()+(partial**2).sum())
    sign, logdet = np.linalg.slogdet(corr)
    bartlett = -(len(array)-1-(2*p+5)/6)*logdet if sign > 0 else np.nan
    r["tables"] += [_table("因素負荷量"+("（旋轉後）" if o["rotation"] != "none" else ""), ["Variable"]+[f"Factor {j+1}" for j in range(k)], [[name]+list(loads[i]) for i, name in enumerate(names)]), _table("共同性", ["Variable", "Initial SMC", "Extraction"], [[name, initial[i], communalities[i]] for i, name in enumerate(names)]), _table("KMO 與 Bartlett 球形檢定", ["Statistic", "Value", "df", "p"], [["KMO", kmo, None, None], ["Bartlett chi-square", bartlett, p*(p-1)/2, stats.chi2.sf(bartlett, p*(p-1)/2)]])]
    r["details"].update(extraction="principal axis factoring", initial_communality="SMC", iterations=iteration+1, converged=True, loadings=loads.tolist(), tolerance=o["tolerance"])
    r["warnings"].append("主軸抽取、旋轉與 Heywood 處理尚未與 SPSS 逐項驗證；不可視為 SPSS 預設 FACTOR（PCA）的等價替代。")


def _cluster(df, o, r, hierarchical=False):
    data, original = _multivariate_data(df, o, r, minimum_variables=1)
    k = o["clusters"]
    if k > len(data):
        raise ValueError("群數不可大於完整樣本數。")
    array = (original-original.mean(axis=0))/original.std(axis=0, ddof=1) if o["standardize"] == "yes" else original
    if len(np.unique(array, axis=0)) < k:
        raise ValueError("群數不可大於不同觀察值的數量。")
    positions = np.flatnonzero(df[o["variables"]].notna().all(axis=1).to_numpy())+1
    if hierarchical:
        if len(data) > 5000:
            raise ValueError("階層分群需平方級記憶體；本版本限制 5000 筆完整資料。")
        if o["linkage"] == "ward" and o["distance"] != "euclidean":
            raise ValueError("Ward 的連結公式必須輸入 euclidean 距離；不允許平方歐氏距離造成重複平方。")
        tree = hierarchy.linkage(array, method=o["linkage"], metric=o["distance"], optimal_ordering=False)
        labels = hierarchy.cut_tree(tree, n_clusters=[k]).ravel()
        r["tables"].append(_table("合併歷程（原始個案節點從 0 開始）", ["Step", "Left node", "Right node", "Distance", "Cases"], [[i+1, int(row[0]), int(row[1]), row[2], int(row[3])] for i, row in enumerate(tree)]))
        r["details"].update(linkage=o["linkage"], distance=o["distance"], linkage_distance_definition="SciPy linkage height; Ward height is not raw increase in within-cluster sum of squares")
    else:
        if o["initialization"] == "first":
            initial = array[:k].copy()
            if len(np.unique(initial, axis=0)) < k:
                raise ValueError("前 k 個完整個案含重複初始中心；請調整個案順序或選 kmeans++，不會自動替換初始中心。")
            n_init = 1
            r["details"].update(initial_data_rows=positions[:k].tolist(), initial_centers_original_units=original[:k].tolist())
            r["warnings"].append("first 使用前 k 個完整個案起始中心與單次初始解；後續 Lloyd 更新及容許誤差仍不等於 SPSS QUICK CLUSTER 的全部規則。")
        else:
            initial, n_init = "k-means++", 20
        fit = KMeans(n_clusters=k, init=initial, n_init=n_init, random_state=o["seed"], max_iter=o["max_iter"], tol=1e-4, algorithm="lloyd").fit(array)
        labels = fit.labels_
        if len(np.unique(labels)) != k:
            raise ValueError("最終非空群數少於指定群數；請調整初始中心、群數或資料尺度。")
        r["details"].update(inertia=float(fit.inertia_), iterations=int(fit.n_iter_), seed=o["seed"], n_init=n_init, tolerance=1e-4, initialization=o["initialization"], convergence_rule="sklearn Lloyd: unchanged assignments or squared center shift <= tol * mean(feature population variance)")
        if fit.n_iter_ >= o["max_iter"]:
            r["warnings"].append("K-means 達最大迭代次數；尚無法確認已收斂。")
    assignment_means = np.array([original[labels == label].mean(axis=0) for label in range(k)])
    if hierarchical:
        centers = assignment_means
    else:
        # A final reassignment after an early stop can change memberships.
        # Preserve the actual fitted centers used by inertia and prediction.
        centers = fit.cluster_centers_.copy()
        if o["standardize"] == "yes":
            centers = centers*original.std(axis=0, ddof=1)+original.mean(axis=0)
        centers_are_means = bool(np.allclose(centers, assignment_means, atol=1e-12, rtol=1e-10))
        r["details"]["final_centers_are_assignment_means"] = centers_are_means
        if not centers_are_means:
            r["warnings"].append("停止後最後一次重新分群改變了群別；表中保留實際模型中心以與 inertia 一致，目前不等於最終群別的算術平均。可提高迭代上限重新估計。")
    # Label display is explicit and never changes the fitted partition.
    if o["label_order"] == "centroid":
        order = sorted(range(k), key=lambda i: tuple(centers[i]))
        label_rule = "centroids in lexicographic order"
    elif hierarchical:
        order = sorted(range(k), key=lambda i: int(positions[labels == i].min()))
        label_rule = "ascending smallest original data row in each cluster"
    else:
        order = list(range(k))
        label_rule = "fitted KMeans label plus one; preserve initialization ordering"
    remap = {old: new+1 for new, old in enumerate(order)}
    final_labels = np.array([remap[v] for v in labels])
    r["tables"].append(_table("群中心（原始單位）", ["Cluster", "N"]+o["variables"], [[remap[i], int((labels == i).sum())]+centers[i].tolist() for i in order]))
    r["tables"].append(_table("個案群別", ["Data row (1-based)", "Cluster"], [[int(row), int(label)] for row, label in zip(positions, final_labels)]))
    if original.shape[1] > 1:
        r["charts"].append({"kind": "scatter", "title": "前兩個變數的原始分布", "x": original[:, 0].tolist(), "y": original[:, 1].tolist(), "x_label": o["variables"][0], "y_label": o["variables"][1]})
    else:
        r["charts"].append({"kind": "histogram", "title": "原始變數分布", "values": original[:, 0].tolist(), "bins": min(30, max(5, int(np.sqrt(len(original)))))})
    r["details"].update(standardize=o["standardize"], cluster_labels=final_labels.tolist(), retained_data_rows=positions.tolist(), cluster_label_rule=label_rule)
    r["warnings"].append("分群的初始中心、同距離解法、標準化與群編號規則不同時，結果可能與 SPSS 不同；尚未驗證。")


def _alpha(array):
    p = array.shape[1]
    total_variance = np.var(array.sum(axis=1), ddof=1)
    if p < 2 or total_variance <= 0:
        return np.nan
    return p/(p-1)*(1-np.var(array, axis=0, ddof=1).sum()/total_variance)


def _reliability(df, o, r):
    _, array = _multivariate_data(df, o, r)
    p = array.shape[1]
    alpha = _alpha(array)
    standardized = _alpha((array-array.mean(axis=0))/array.std(axis=0, ddof=1))
    if not np.isfinite(alpha):
        raise ValueError("總分變異為零，Cronbach α 無法定義。")
    rows = []
    for i, name in enumerate(o["variables"]):
        rest = np.delete(array, i, axis=1)
        score = rest.sum(axis=1)
        corrected = stats.pearsonr(array[:, i], score).statistic if score.std() > 0 else np.nan
        rows.append([name, score.mean(), score.var(ddof=1), corrected, _alpha(rest)])
    r["tables"] += [_table("信度摘要", ["N", "Items", "Cronbach alpha", "Standardized alpha"], [[len(array), p, alpha, standardized]]), _table("項目總分統計", ["Item", "Scale mean if deleted", "Scale variance if deleted", "Corrected item-total correlation", "Alpha if deleted"], rows)]
    r["details"].update(alpha=float(alpha), standardized_alpha=float(standardized), reverse_scoring="none; recode explicitly before analysis")
    if alpha < 0:
        r["warnings"].append("α 為負值；請檢查反向題與項目之間的關係。")


def _rank_tests(df, method, o, r):
    if method == "wilcoxon":
        _numeric(df, [o["x"], o["y"]])
        data = _complete(df, [o["x"], o["y"]], r)
        delta = (data[o["x"]]-data[o["y"]]).to_numpy(dtype=float)
        nonzero = delta[delta != 0]
        if not len(nonzero):
            raise ValueError("所有配對差值均為零，Wilcoxon 近似檢定無法定義。")
        # Explicit asymptotic method prevents scipy's automatic exact-method switch.
        test = stats.wilcoxon(delta, zero_method="wilcox", correction=o["continuity"] == "yes", alternative="two-sided", method="approx")
        ranks = stats.rankdata(np.abs(nonzero), method="average")
        r["tables"].append(_table("Wilcoxon 符號等級", ["N paired", "N nonzero", "Zero differences", "Negative rank sum", "Positive rank sum", "W (min rank sum)", "z", "p (two-sided)"], [[len(delta), len(nonzero), int((delta == 0).sum()), ranks[nonzero < 0].sum(), ranks[nonzero > 0].sum(), test.statistic, test.zstatistic, test.pvalue]]))
        r["details"].update(zero_method="wilcox", difference="x minus y", exact=False)
        r["warnings"].append("差值以原始浮點值計算；理論上相同的差值若有浮點誤差，可能形成不同等級。")
    else:
        _numeric(df, [o["x"]])
        levels, samples = _groups(df, o["x"], o["group"], minimum=1)
        n = sum(map(len, samples))
        joined = np.concatenate(samples)
        if joined.std() == 0:
            raise ValueError("所有有效值相同，秩檢定無法定義。")
        ranks = stats.rankdata(joined)
        offsets = np.cumsum([0]+list(map(len, samples)))
        r["tables"].append(_table("各組等級", ["Group", "N", "Mean rank", "Sum of ranks"], [[level, len(x), ranks[offsets[i]:offsets[i+1]].mean(), ranks[offsets[i]:offsets[i+1]].sum()] for i, (level, x) in enumerate(zip(levels, samples))]))
        if method == "mann_whitney":
            if len(samples) != 2:
                raise ValueError("Mann–Whitney U 需要剛好兩個有效組別。")
            test = stats.mannwhitneyu(*samples, alternative="two-sided", method="asymptotic", use_continuity=o["continuity"] == "yes")
            u2 = len(samples[0])*len(samples[1])-test.statistic
            r["tables"].append(_table("Mann–Whitney U", ["U for first group", "U for second group", "Minimum U", "p (two-sided)"], [[test.statistic, u2, min(test.statistic, u2), test.pvalue]]))
        else:
            test = stats.kruskal(*samples)
            r["tables"].append(_table("Kruskal–Wallis", ["H", "df", "p"], [[test.statistic, len(samples)-1, test.pvalue]]))
        r["details"].update(n_used=n, dropped=len(df)-n, group_order=levels, missing_policy="listwise for selected value and group", exact=False)
    r["warnings"].append("使用漸近檢定及平均等級同分校正；小樣本精確 p 值尚未實作。")


def analyze(df: pd.DataFrame, method: str, options: dict) -> dict:
    """Run one explicitly configured procedure or reject unsupported inputs.

    Only actual NA values are missing. User-defined SPSS missing values,
    WEIGHT/SPLIT FILE, complex sampling and categorical predictor expansion
    are intentionally unsupported and must never be silently assumed.
    """
    spec, opts = _validate(df, method, options)
    result = {"title": spec["label"], "tables": [], "warnings": ["獨立實作：尚未完成本方法所有選項及邊界情況與 SPSS 30 的一致性驗證。"], "details": {"method": method, "options": opts, "n_input": len(df), "parity_status": "unverified", "weights": "unsupported", "user_missing": "unsupported; actual NA only", "p_values": "two-sided unless an omnibus F/chi-square test", "numeric_precision": "float64; not rounded"}, "charts": []}
    dispatch = {"descriptive": _descriptive, "frequencies": _frequencies, "crosstabs": _crosstabs, "ttest_one": _ttest_one, "ttest_independent": _ttest_independent, "ttest_paired": _ttest_paired, "anova": _anova, "correlation": _correlation, "linear_regression": _linear, "logistic_regression": _logistic, "pca": _pca, "factor": _factor, "kmeans": _cluster, "hierarchical": lambda d, o, r: _cluster(d, o, r, hierarchical=True), "reliability": _reliability}
    with pywarnings.catch_warnings(record=True) as caught:
        pywarnings.simplefilter("always")
        if method in dispatch:
            dispatch[method](df, opts, result)
        else:
            _rank_tests(df, method, opts, result)
    for warning in caught:
        if issubclass(warning.category, (RuntimeWarning, UserWarning)):
            message = "計算函式警告：" + str(warning.message)
            if message not in result["warnings"]:
                result["warnings"].append(message)
    return _clean(result)
