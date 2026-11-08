"""Rebuild src/statstudio/resources/validation-summary.json from validation/parity-report.json.

Keeps the measured SPSS comparison scope untouched; only refreshes the engine hash,
timestamp, library versions and counts that the parity report records, and lists
the meta-analysis methods whose oracle is R meta/metafor/rjags rather than SPSS.
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
    "meta_binary": "R meta 8.5.0 / metafor 5.0.1 oracle on validation/meta/synthetic_oracle.json (tests/test_meta.py)",
    "meta_regression": "R metafor 5.0.1 rma(test='knha') oracle (tests/test_meta.py)",
    "bayes_meta_binary": "rjags 4.17 / JAGS 4.3.1 same-model comparison on project data; MCMC tolerance",
    "tsa_binary": "Lan–DeMets O'Brien–Fleming boundaries checked against published table values only",
}
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
print("engine_sha256", summary["engine_sha256"], "counts", summary["counts"])
