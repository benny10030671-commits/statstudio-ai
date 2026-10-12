"""Analytic invariants and failures that could otherwise mislead users."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from statstudio.engine import METHODS, analyze


def table(result, title):
    return next(t for t in result["tables"] if t["title"] == title)


def test_descriptive_sample_variance_and_actual_missing():
    df = pd.DataFrame({"x": [1., 2., 3., 4., 5., np.nan], "all_missing": [np.nan]*6})
    result = analyze(df, "descriptive", {"variables": ["x", "all_missing"]})
    tab = result["tables"][0]
    row = dict(zip(tab["columns"], tab["rows"][0]))
    assert row["N"] == 5
    assert row["Missing / excluded"] == 1
    assert row["Mean"] == 3
    assert row["Variance"] == pytest.approx(2.5)
    assert row["Skewness"] == pytest.approx(0)
    assert row["Excess kurtosis"] == pytest.approx(-1.2)
    assert len(tab["rows"][1]) == len(tab["columns"])
    assert tab["rows"][1][3] is None
    json.dumps(result, allow_nan=False)


def test_frequency_valid_denominator():
    df = pd.DataFrame({"x": ["a", "a", "b", None]})
    tab = analyze(df, "frequencies", {"variables": ["x"]})["tables"][0]
    assert tab["rows"][0] == ["a", 2, 50.0, 100*2/3, 100*2/3]
    assert tab["rows"][-1] == ["<missing>", 1, 25.0, None, None]


def test_unknown_weights_and_user_missing_rejected():
    df = pd.DataFrame({"x": [1., 2., 3.]})
    for invalid in [{"weights": "x"}, {"user_missing": [99]}, {"confidence": 95}, {"variables": []}]:
        opts = {"variables": ["x"], **invalid}
        with pytest.raises(ValueError):
            analyze(df, "descriptive", opts)


def test_numeric_text_and_infinity_are_not_silently_dropped():
    for values in [["1", "2", "broken"], [1., np.inf, 3.]]:
        with pytest.raises(ValueError):
            analyze(pd.DataFrame({"x": values}), "ttest_one", {"variables": ["x"]})


def test_t_test_manual_value_and_constant_errors():
    result = analyze(pd.DataFrame({"x": [1., 2., 3., 4., 5.]}), "ttest_one", {"variables": ["x"]})
    row = dict(zip(result["tables"][0]["columns"], result["tables"][0]["rows"][0]))
    assert row["t"] == pytest.approx(3/math.sqrt(.5))
    assert row["df"] == 4
    assert row["Mean difference"] == 3
    with pytest.raises(ValueError, match="標準誤"):
        analyze(pd.DataFrame({"x": [4., 4., 4.]}), "ttest_one", {"variables": ["x"]})


def test_independent_uses_numeric_group_order_and_both_variance_models():
    df = pd.DataFrame({"x": [2., 3., 5., 1., 4., 7.], "g": [10, 10, 10, 2, 2, 2]})
    result = analyze(df, "ttest_independent", {"variables": ["x"], "group": "g"})
    assert result["details"]["group_order"] == [2, 10]
    tab = table(result, "獨立樣本 t 檢定")
    assert len(tab["rows"]) == 2
    assert tab["rows"][0][5] == pytest.approx(4-10/3)
    assert tab["rows"][0][3] == 4
    assert tab["rows"][1][3] < 4


def test_paired_uses_joint_missing_mask():
    df = pd.DataFrame({"x": [2., 4., 7., np.nan, 100.], "y": [1., 2., 3., 99., np.nan]})
    result = analyze(df, "ttest_paired", {"x": "x", "y": "y"})
    assert result["details"]["n_used"] == 3
    assert result["details"]["dropped"] == 2
    assert result["tables"][0]["rows"][0][6] == pytest.approx(7/3)


def test_correlation_pairwise_and_listwise_n_differ():
    df = pd.DataFrame({"x": [1., 2., 3., 4., 5.], "y": [1., 3., 2., 6., 4.], "z": [np.nan, 2., 1., 3., 5.]})
    pair = analyze(df, "correlation", {"variables": ["x", "y", "z"]})
    complete = analyze(df, "correlation", {"variables": ["x", "y", "z"], "missing": "listwise"})
    assert pair["tables"][1]["rows"][0][2] == 5
    assert complete["tables"][1]["rows"][0][2] == 4
    constant = analyze(df.assign(z=1), "correlation", {"variables": ["x", "z"]})
    assert constant["tables"][0]["rows"][0][2] is None
    json.dumps(constant, allow_nan=False)


def test_ols_known_projection_and_rejects_singular_design():
    x = np.array([-2., -1., 0., 1., 2.])
    residual = np.array([1., -2., 2., -2., 1.])
    df = pd.DataFrame({"x": x, "duplicate": 2*x, "y": 2+3*x+residual})
    result = analyze(df, "linear_regression", {"target": "y", "predictors": ["x"]})
    assert result["details"]["coefficients"]["(Intercept)"] == pytest.approx(2.)
    assert result["details"]["coefficients"]["x"] == pytest.approx(3.)
    assert result["tables"][2]["rows"][1][1] == pytest.approx(14.)
    with pytest.raises(ValueError, match="秩不足"):
        analyze(df, "linear_regression", {"target": "y", "predictors": ["x", "duplicate"]})


def test_binary_event_coding_reverses_logit_coefficients():
    df = pd.DataFrame({"x": [-1.]*8+[0.]*8+[1.]*8, "y": ["yes"]*2+["no"]*6+["yes"]*4+["no"]*4+["yes"]*6+["no"]*2})
    positive = analyze(df, "logistic_regression", {"target": "y", "predictors": ["x"]})
    negative = analyze(df, "logistic_regression", {"target": "y", "predictors": ["x"], "event": "first"})
    assert positive["details"]["event_level"] == "yes"
    assert positive["details"]["coefficients"]["x"] == pytest.approx(math.log(3))
    assert negative["details"]["coefficients"]["x"] == pytest.approx(-math.log(3))
    with pytest.raises(ValueError):
        analyze(df.assign(y=(df.x > 0).astype(int)), "logistic_regression", {"target": "y", "predictors": ["x"]})


def test_pca_trace_and_reliability_identical_items():
    df = pd.DataFrame({"a": [1., 2., 3., 4., 5.], "b": [2., 1., 4., 5., 3.]})
    result = analyze(df, "pca", {"variables": ["a", "b"], "components": 2})
    assert sum(result["details"]["eigenvalues"]) == pytest.approx(2)
    assert all(row[2] == pytest.approx(1) for row in result["tables"][2]["rows"])
    alpha = analyze(df.assign(b=df.a), "reliability", {"variables": ["a", "b"]})
    assert alpha["details"]["alpha"] == pytest.approx(1.)
    assert all(row[-1] is None for row in alpha["tables"][1]["rows"])


def test_rank_tests_all_equal_and_zero_difference_rejected():
    df = pd.DataFrame({"x": [1., 1., 1., 1.], "y": [1., 1., 1., 1.], "g": [1, 1, 2, 2]})
    for method, options in [("wilcoxon", {"x": "x", "y": "y"}), ("mann_whitney", {"x": "x", "group": "g"}), ("kruskal", {"x": "x", "group": "g"})]:
        with pytest.raises(ValueError):
            analyze(df, method, options)


def test_hierarchical_squared_distance_is_averaged_before_not_after_linkage():
    # First merge is 0/2; the final average squared distance is (100+64)/2,
    # not the squared average distance ((10+8)/2)^2.
    df = pd.DataFrame({"x": [0., 2., 10.]})
    base = {"variables": ["x"], "clusters": 2, "standardize": "no", "linkage": "average"}
    squared = analyze(df, "hierarchical", {**base, "distance": "sqeuclidean"})
    euclidean = analyze(df, "hierarchical", {**base, "distance": "euclidean"})
    assert [row[3] for row in squared["tables"][0]["rows"]] == pytest.approx([4., 82.])
    assert [row[3] for row in euclidean["tables"][0]["rows"]] == pytest.approx([2., 9.])
    assert squared["details"]["cluster_labels"] == [1, 1, 2]
    with pytest.raises(ValueError, match="Ward"):
        analyze(df, "hierarchical", {**base, "linkage": "ward", "distance": "sqeuclidean"})


def test_kmeans_first_initializes_from_complete_rows_and_rejects_duplicate_centers():
    df = pd.DataFrame({"x": [0., np.nan, 10., 1., 11.]})
    opts = {"variables": ["x"], "clusters": 2, "standardize": "no", "initialization": "first"}
    result = analyze(df, "kmeans", opts)
    assert result["details"]["n_init"] == 1
    assert result["details"]["initial_data_rows"] == [1, 3]
    assert result["details"]["initial_centers_original_units"] == [[0.], [10.]]
    assert result["details"]["cluster_labels"] == [1, 2, 1, 2]
    assert result["details"]["inertia"] == pytest.approx(1.)
    assert result["tables"][0]["rows"] == [[1, 2, .5], [2, 2, 10.5]]
    different_seed = analyze(df, "kmeans", {**opts, "seed": 305})
    assert different_seed["details"]["cluster_labels"] == result["details"]["cluster_labels"]
    with pytest.raises(ValueError, match="重複初始中心"):
        analyze(pd.DataFrame({"x": [0., 0., 10., 11.]}), "kmeans", opts)


def test_kmeans_early_stop_reports_actual_centers_consistent_with_inertia():
    df = pd.DataFrame({"x": [0., 1., 2., 10.]})
    result = analyze(df, "kmeans", {"variables": ["x"], "clusters": 2, "standardize": "no", "initialization": "first", "max_iter": 1})
    centers = {row[0]: row[2] for row in result["tables"][0]["rows"]}
    labels = result["details"]["cluster_labels"]
    computed_inertia = sum((x-centers[label])**2 for x, label in zip(df.x, labels))
    assert computed_inertia == pytest.approx(result["details"]["inertia"])
    assert result["details"]["final_centers_are_assignment_means"] is False
    assert centers[2] == pytest.approx(13/3)


@pytest.mark.parametrize("method", ["kmeans", "hierarchical"])
def test_cluster_label_policy_is_explicit_and_does_not_change_partition(method):
    df = pd.DataFrame({"x": [10., 0., 11., 1.]})
    options = {"variables": ["x"], "clusters": 2, "standardize": "no"}
    if method == "kmeans":
        options["initialization"] = "first"
    else:
        options.update(linkage="average", distance="sqeuclidean")
    centroid = analyze(df, method, {**options, "label_order": "centroid"})
    native = analyze(df, method, {**options, "label_order": "native"})
    a, b = centroid["details"]["cluster_labels"], native["details"]["cluster_labels"]
    assert a == [2, 1, 2, 1]
    assert b == [1, 2, 1, 2]
    assert np.array_equal(np.equal.outer(a, a), np.equal.outer(b, b))
    assert native["details"]["options"]["label_order"] == "native"


def test_all_methods_have_rectangular_json_tables_and_do_not_mutate_input():
    rng = np.random.default_rng(105)
    n = 90
    latent = rng.normal(size=n)
    df = pd.DataFrame({f"v{i}": latent+rng.normal(scale=.7, size=n) for i in range(5)})
    df["g"] = np.tile([1, 2], n//2)
    df["bin"] = rng.binomial(1, 1/(1+np.exp(-.2*df.v0)))
    saved = df.copy(deep=True)
    configs = {
        "descriptive": {"variables": ["v0", "v1"]}, "frequencies": {"variables": ["g"]},
        "crosstabs": {"x": "g", "y": "bin"}, "ttest_one": {"variables": ["v0"]},
        "ttest_independent": {"variables": ["v0"], "group": "g"}, "ttest_paired": {"x": "v0", "y": "v1"},
        "anova": {"variables": ["v0"], "group": "g"}, "correlation": {"variables": ["v0", "v1"]},
        "linear_regression": {"target": "v0", "predictors": ["v1", "v2"]},
        "logistic_regression": {"target": "bin", "predictors": ["v1", "v2"]},
        "pca": {"variables": ["v0", "v1", "v2"], "rotation": "varimax"},
        "factor": {"variables": [f"v{i}" for i in range(5)], "rotation": "varimax"},
        "kmeans": {"variables": ["v0", "v1"]}, "hierarchical": {"variables": ["v0", "v1"]},
        "reliability": {"variables": ["v0", "v1", "v2"]}, "mann_whitney": {"x": "v0", "group": "g"},
        "wilcoxon": {"x": "v0", "y": "v1"}, "kruskal": {"x": "v0", "group": "g"},
    }
    assert set(configs) == {m["id"] for m in METHODS}
    for method, options in configs.items():
        result = analyze(df, method, options)
        assert result["tables"], method
        assert result["details"]["parity_status"] == "unverified"
        for tab in result["tables"]:
            assert all(len(row) == len(tab["columns"]) for row in tab["rows"]), (method, tab["title"])
        json.dumps(result, allow_nan=False)
    pd.testing.assert_frame_equal(df, saved)
