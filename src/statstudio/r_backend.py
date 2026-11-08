"""R backend for the meta-analysis procedures (methods ending in ``_r``).

The computation is done by R packages that are standard references in the field and can be cited
in a manuscript: meta / metafor (frequentist pooling, subgroups, meta-regression), rjags with JAGS
(Bayesian binomial–normal hierarchical model) and RTSA (the R implementation of the Copenhagen Trial
Unit TSA software). Python only validates the input, writes a JSON request, runs ``Rscript`` on
``statstudio/r/meta_backend.R`` and merges the JSON result. The result tables use the same schema as
the Python implementation in :mod:`statstudio.meta`, so the web UI, HTML report and MCP clients render
them unchanged; ``details.software`` records the R and package versions that produced the numbers.

R is optional: when it is missing the ``_r`` methods raise an explicit error with install instructions
instead of silently falling back to the Python engine.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from . import meta as _meta

R_DIR = Path(__file__).resolve().parent / "r"
REQUIRED = ("meta", "metafor", "rjags", "RTSA", "jsonlite", "coda")
INSTALL_HINT = ("安裝 R 4.x（https://cloud.r-project.org）與 JAGS 4.x（https://mcmc-jags.sourceforge.io），"
                "再執行 python -m statstudio install-r-packages；Rscript 不在 PATH 時可設環境變數 STATSTUDIO_RSCRIPT。")
_ENV_CACHE: dict = {}


def find_rscript() -> str | None:
    """Rscript from STATSTUDIO_RSCRIPT, PATH, or the usual Windows install folders (newest version)."""
    env = os.environ.get("STATSTUDIO_RSCRIPT")
    if env and Path(env).is_file():
        return env
    found = shutil.which("Rscript") or shutil.which("Rscript.exe")
    if found:
        return found
    if sys.platform == "win32":
        roots = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "R", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "R"]
        candidates = sorted(p for root in roots if root.is_dir() for p in root.glob("R-*/bin/Rscript.exe"))
        if candidates:
            return str(candidates[-1])
    return None


def environment(refresh: bool = False) -> dict:
    """R version, package versions and JAGS availability (cached per process)."""
    if _ENV_CACHE and not refresh:
        return dict(_ENV_CACHE)
    rscript = find_rscript()
    info = {"rscript": rscript, "available": False, "missing": list(REQUIRED), "jags": None, "install_hint": INSTALL_HINT}
    if rscript:
        try:
            proc = subprocess.run([rscript, str(R_DIR / "check_env.R")], capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
            lines = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip().startswith("{")]
            if proc.returncode == 0 and lines:
                data = json.loads(lines[-1])
                packages = data.get("packages") or {}
                info.update({"r_version": data.get("r_version"), "r_home": data.get("r_home"), "packages": packages, "jags": data.get("jags")})
                info["missing"] = [p for p in REQUIRED if not packages.get(p)]
                info["available"] = not info["missing"] and bool(info["jags"])
            else:
                info["error"] = (proc.stderr or proc.stdout or "").strip()[-800:]
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            info["error"] = str(exc)
    _ENV_CACHE.clear()
    _ENV_CACHE.update(info)
    return dict(info)


def available() -> bool:
    return bool(environment().get("available"))


def _run(method: str, records: list, options: dict, timeout: int) -> dict:
    env = environment()
    if not env.get("rscript"):
        raise ValueError("找不到 Rscript，無法執行 R 後端方法。" + INSTALL_HINT)
    if not env.get("available"):
        missing = ", ".join(env.get("missing", [])) or "（套件齊全）"
        jags = "" if env.get("jags") else "；JAGS 未安裝或 rjags 無法載入"
        raise ValueError(f"R 套件不完整，缺少：{missing}{jags}。" + INSTALL_HINT)
    with tempfile.TemporaryDirectory(prefix="statstudio-r-") as tmp:
        req, res = Path(tmp) / "request.json", Path(tmp) / "result.json"
        req.write_text(json.dumps({"method": method, "options": options, "data": records}, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        try:
            proc = subprocess.run([env["rscript"], str(R_DIR / "meta_backend.R"), str(req), str(res)], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"R 執行超過 {timeout} 秒；請減少迭代數或研究數。") from exc
        if proc.returncode != 0 or not res.is_file():
            tail = "\n".join((proc.stderr or proc.stdout or "").strip().splitlines()[-8:])
            raise ValueError("R 執行失敗：" + tail)
        return json.loads(res.read_text(encoding="utf-8"))


def _records(df: pd.DataFrame, o: dict, r: dict, extra_roles: tuple[str, ...]) -> tuple[list, pd.DataFrame]:
    """Validate the 2×2 counts with the same rules as the Python engine and attach optional role columns."""
    data = _meta._binary_frame(df, o, r)
    out = data[["study", "e1", "n1", "e2", "n2"]].copy()
    for role in extra_roles:
        col = o.get(role)
        if col:
            out[role] = df.loc[data["_orig_index"], col].to_numpy()
    records = json.loads(out.to_json(orient="records", force_ascii=False))  # NaN -> null
    return records, data


def _merge(r: dict, res: dict) -> None:
    r["tables"].extend(res.get("tables", []))
    r["charts"].extend(res.get("charts", []))
    r["details"].update(res.get("details", {}))
    r["details"]["backend"] = "R"
    r["details"]["software"] = res.get("software", {})
    sw = ", ".join(f"{k} {v}" for k, v in res.get("software", {}).items())
    disclaimer = next((w for w in r["warnings"] if w.startswith("獨立實作")), None)
    note = f"計算由 R 套件執行（{sw}）；本方法以這些公認套件為計算引擎，不以 SPSS 為基準。"
    if disclaimer is not None:
        r["warnings"][r["warnings"].index(disclaimer)] = note
    else:
        r["warnings"].insert(0, note)
    r["warnings"].extend(res.get("warnings", []))


def meta_binary(df, o, r):
    records, _ = _records(df, o, r, ("subgroup",))
    opts = {k: o[k] for k in ("measure", "tau2_method", "cc", "confidence", "prediction_df")}
    _merge(r, _run("meta_binary", records, opts, timeout=600))


def meta_regression(df, o, r):
    mod = o["moderator"]
    if mod in (o["event_exp"], o["n_exp"], o["event_ctrl"], o["n_ctrl"], o["study"]):
        raise ValueError("調節變數不可與計數欄位相同。")
    if not pd.api.types.is_numeric_dtype(df[mod]):
        raise ValueError("調節變數必須為數值欄位（類別請先編碼為 0/1）。")
    records, _ = _records(df, o, r, ("moderator",))
    opts = {k: o[k] for k in ("measure", "tau2_method", "knapp_hartung", "cc", "confidence")} | {"moderator_name": mod}
    _merge(r, _run("meta_regression", records, opts, timeout=600))


def bayes_meta_binary(df, o, r):
    records, _ = _records(df, o, r, ())
    opts = {k: o[k] for k in ("model", "prior_effect_sd", "prior_tau_scale", "prior_baseline_sd", "chains", "iterations", "burnin", "seed", "confidence")}
    if min(float(opts["prior_effect_sd"]), float(opts["prior_tau_scale"]), float(opts["prior_baseline_sd"])) <= 0:
        raise ValueError("先驗尺度必須為正數。")
    if int(opts["chains"]) < 1 or int(opts["iterations"]) < 1000 or int(opts["burnin"]) < 200:
        raise ValueError("chains ≥ 1、iterations ≥ 1000、burnin ≥ 200。")
    _merge(r, _run("bayes_meta_binary", records, opts, timeout=7200))


def tsa_binary(df, o, r):
    records, _ = _records(df, o, r, ("order",))
    opts = {k: o[k] for k in ("alpha", "power", "rrr", "control_risk", "tau2_method", "cc")}
    if not 0 < float(opts["alpha"]) < 1 or not 0 < float(opts["power"]) < 1:
        raise ValueError("alpha 與 power 必須介於 0 與 1。")
    _merge(r, _run("tsa_binary", records, opts, timeout=900))
