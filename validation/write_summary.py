"""Rebuild src/statstudio/resources/validation-summary.json from validation/parity-report.json.

Keeps the measured SPSS comparison scope untouched; only refreshes the engine hash,
timestamp, library versions and counts that the parity report records, and lists
the separate, limited SPSS meta-analysis checks and the remaining R-based methods.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / "validation" / "parity-report.json").read_text(encoding="utf-8"))
target = ROOT / "src" / "statstudio" / "resources" / "validation-summary.json"
summary = json.loads(target.read_text(encoding="utf-8"))
summary.update({k: report[k] for k in ("generated_at_utc", "engine_sha256", "numeric_libraries", "policy", "counts")})
summary["methods"] = sorted({case["method"] for case in report["cases"]})
summary["fixtures"] = sorted({case["fixture"] for case in report["cases"]})
summary["tested_options"] = {case["method"]: case["options"] for case in report["cases"]}
summary["non_spss_methods"] = {
    "meta_regression": "R metafor 5.0.1 rma(test='knha') oracle (tests/test_meta.py)",
    "bayes_meta_binary": "rjags 4.17 / JAGS 4.3.1 same-model comparison on project data; MCMC tolerance",
    "tsa_binary": "Lan–DeMets O'Brien–Fleming boundaries checked against published table values only",
}
meta_path = ROOT / 'validation/meta/spss-parity-report.json'
if meta_path.is_file():
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    summary['meta_binary_validation'] = {
        'source_report': 'validation/meta/spss-parity-report.json',
        'counts': meta['counts'], 'scope': meta['scope'], 'policies': meta['policies'],
        'engine_sha256': meta['engine_sha256'], 'meta_sha256': meta['meta_sha256'],
        'tested_options': {case['case']: case['options'] for case in meta['cases']},
        'legacy_r_reference': 'validation/meta/synthetic_oracle.json; prediction_df=k-1, heterogeneity_method=q',
        'limitations': 'No claim for untested estimators, HK/truncated-HK prediction intervals, subgroup/bias defaults, all missing/zero rules, or whole SPSS factory defaults.',
    }
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
print("engine_sha256", summary["engine_sha256"], "counts", summary["counts"])
