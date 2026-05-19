"""
catas_ml.py — ML scoring layer for the CATAS orchestrator.

Wires the three offline-trained models into the live pipeline so they
genuinely *ground* the agent decisions instead of sitting unused:

  - anomaly_detector.pkl   Isolation Forest — per-transaction anomaly score.
  - approval_classifier.pkl  Logistic Regression — P(approve) for the txn.
  - forecast_model.pkl     30-day cash-balance forecast — liquidity risk.

Each .pkl is the dict-bundle format produced by scripts/agent{1,2,3}_*.py
(model + feature schema + metrics). Bare-estimator pickles are NOT supported;
re-run the agent scripts if you see a schema error.

The whole layer degrades gracefully: if numpy/pandas/scikit-learn or the
.pkl files are missing, `ML_AVAILABLE` is False and `compute_ml_signals()`
returns neutral zeros so the orchestrator still runs (stdlib-only fallback).
"""
from __future__ import annotations

import csv
import math
import os
import pickle
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODELS_DIR = _REPO_ROOT / "models"

# --- optional heavy deps ------------------------------------------------------
try:
    import numpy as np  # noqa: F401
    import pandas as pd
    ML_DEPS = True
except ImportError:
    ML_DEPS = False

_BUNDLES: dict[str, Any] = {}
_LOAD_ERROR: str | None = None


def _load_bundles() -> bool:
    """Load the three .pkl bundles once. Returns True if all three loaded."""
    global _LOAD_ERROR
    if _BUNDLES:
        return True
    if not ML_DEPS:
        _LOAD_ERROR = "numpy/pandas/scikit-learn not installed"
        return False
    try:
        for key, fname in (
            ("anomaly", "anomaly_detector.pkl"),
            ("approval", "approval_classifier.pkl"),
            ("forecast", "forecast_model.pkl"),
        ):
            path = _MODELS_DIR / fname
            with path.open("rb") as f:
                bundle = pickle.load(f)
            if not isinstance(bundle, dict) or "model" not in bundle:
                raise ValueError(
                    f"{fname} is not the expected dict-bundle format — "
                    f"re-run scripts/agent*.py to regenerate it."
                )
            _BUNDLES[key] = bundle
        return True
    except Exception as e:  # noqa: BLE001 — never raise to the orchestrator
        _LOAD_ERROR = f"{type(e).__name__}: {e}"
        _BUNDLES.clear()
        return False


ML_AVAILABLE = _load_bundles()


def status() -> str:
    """One-line human-readable status for the orchestrator banner."""
    if ML_AVAILABLE:
        a = _BUNDLES["anomaly"]
        c = _BUNDLES["approval"]
        return (
            f"ML models active — anomaly AUC={a.get('test_roc_auc', 0):.3f}, "
            f"approval CV-AUC={c.get('cv_roc_auc', 0):.3f}, "
            f"forecast={_BUNDLES['forecast'].get('method', '?')}"
        )
    return f"ML models inactive ({_LOAD_ERROR}) — running rule-only fallback"


# --- historical-data helpers (cached) ----------------------------------------
_CP_MEDIAN: dict[str, float] | None = None
_OVERALL_MEDIAN: float = 1.0
_DAILY_LIMIT_DEFAULT: float = 25_000.0


def _resolve_data_dir() -> Path:
    env = os.environ.get("CATAS_DATA_DIR")
    if env:
        return Path(env)
    for c in (_REPO_ROOT / "data", Path("data")):
        if c.exists():
            return c
    return _REPO_ROOT / "data"


def _load_historical_stats() -> None:
    """Build per-counterparty median amount + median daily_limit from history."""
    global _CP_MEDIAN, _OVERALL_MEDIAN, _DAILY_LIMIT_DEFAULT
    if _CP_MEDIAN is not None:
        return
    _CP_MEDIAN = {}
    path = _resolve_data_dir() / "historical_transactions_v2.csv"
    if not path.exists():
        path = _resolve_data_dir() / "historical_transactions.csv"
    if not path.exists():
        return
    by_cp: dict[str, list[float]] = {}
    all_amounts: list[float] = []
    limits: list[float] = []
    with path.open() as f:
        for row in csv.DictReader(f):
            try:
                amt = float(row.get("amount", "") or "nan")
            except ValueError:
                amt = float("nan")
            if amt == amt:  # not NaN
                by_cp.setdefault(row.get("counterparty_name", ""), []).append(amt)
                all_amounts.append(amt)
            try:
                lim = float(row.get("daily_limit", "") or "nan")
                if lim == lim:
                    limits.append(lim)
            except ValueError:
                pass
    _CP_MEDIAN = {cp: statistics.median(v) for cp, v in by_cp.items() if v}
    if all_amounts:
        _OVERALL_MEDIAN = statistics.median(all_amounts)
    if limits:
        _DAILY_LIMIT_DEFAULT = statistics.median(limits)


def _cp_typical(counterparty_name: str) -> float:
    _load_historical_stats()
    assert _CP_MEDIAN is not None
    return _CP_MEDIAN.get(counterparty_name, _OVERALL_MEDIAN) or 1.0


# --- per-transaction scoring --------------------------------------------------

def _parse_hour_dow(txn: dict[str, Any]) -> tuple[int, int]:
    """Return (hour, day_of_week) from a transaction timestamp; (12, 2) default."""
    ts = txn.get("timestamp") or ""
    for raw in (ts, txn.get("bank_date") or ""):
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt.hour, dt.weekday()
        except ValueError:
            continue
    return 12, 2


def _score_anomaly(txn: dict[str, Any]) -> dict[str, Any]:
    """Isolation Forest anomaly score for one bank transaction."""
    bundle = _BUNDLES["anomaly"]
    feat_names: list[str] = bundle["feature_names"]
    threshold: float = bundle["alert_threshold"]

    amount = float(txn.get("amount") or 0.0)
    hour, dow = _parse_hour_dow(txn)
    cp_typical = _cp_typical(txn.get("counterparty_name", "") or "")
    txn_type = txn.get("transaction_type", "") or ""
    ccy = txn.get("currency", "") or ""

    base = {
        "log_amount": math.log1p(max(amount, 0.0)),
        "amount_vs_cp_typical": amount / max(cp_typical, 1.0),
        "hour": float(hour),
        "day_of_week": float(dow),
        "is_offhours": 0.0 if 8 <= hour <= 18 else 1.0,
    }
    # One-hot the categoricals exactly as the training feature schema expects.
    row = []
    for name in feat_names:
        if name in base:
            row.append(base[name])
        elif name.startswith("type_"):
            row.append(1.0 if name == f"type_{txn_type}" else 0.0)
        elif name.startswith("ccy_"):
            row.append(1.0 if name == f"ccy_{ccy}" else 0.0)
        else:
            row.append(0.0)

    X = pd.DataFrame([row], columns=feat_names)
    # Higher score = more anomalous (negated score_samples, matches training).
    score = float(-bundle["model"].score_samples(X)[0])
    return {
        "anomaly_score": round(score, 4),
        "anomaly_threshold": round(float(threshold), 4),
        "anomaly_flag": bool(score >= threshold),
    }


def _score_approval(txn: dict[str, Any], counterparty_risk_score: float) -> float:
    """Logistic-regression P(approve) for one bank transaction."""
    _load_historical_stats()
    bundle = _BUNDLES["approval"]
    amount = float(txn.get("amount") or 0.0)

    if counterparty_risk_score >= 0.85:
        risk_band = "high"
    elif counterparty_risk_score >= 0.50:
        risk_band = "medium"
    else:
        risk_band = "low"

    # daily_limit / user_role are not on the bank feed — synthesise sensibly.
    # 'unknown' user_role hits OneHotEncoder(handle_unknown='ignore') => neutral.
    features = {
        "amount_ratio": amount / max(_DAILY_LIMIT_DEFAULT, 1.0),
        "log_amount": math.log1p(max(amount, 0.0)),
        "days_since_last_txn": 0.0,
        "transaction_type": txn.get("transaction_type", "") or "unknown",
        "counterparty_risk": risk_band,
        "user_role": "unknown",
    }
    cols = bundle["numeric_features"] + bundle["categorical_features"]
    X = pd.DataFrame([{c: features[c] for c in cols}])
    proba = bundle["model"].predict_proba(X)[0]
    classes = list(bundle["model"].classes_)
    idx = classes.index(1) if 1 in classes else len(classes) - 1
    return round(float(proba[idx]), 4)


# --- liquidity forecast (computed once, cached) ------------------------------
_FORECAST_SUMMARY: dict[str, Any] | None = None


def _forecast_summary() -> dict[str, Any]:
    """30-day projected balance stats from the forecast model (cached)."""
    global _FORECAST_SUMMARY
    if _FORECAST_SUMMARY is not None:
        return _FORECAST_SUMMARY
    bundle = _BUNDLES["forecast"]
    horizon = int(bundle.get("backtest_horizon", 30))
    method = bundle.get("method", "")

    if method == "seasonal_naive" and bundle.get("last_week"):
        week = [float(x) for x in bundle["last_week"]]
        forecast = [week[i % 7] for i in range(horizon)]
    elif bundle.get("model") is not None:
        forecast = [float(x) for x in
                    bundle["model"].get_forecast(steps=horizon).predicted_mean]
    else:
        forecast = []

    _FORECAST_SUMMARY = {
        "method": method,
        "horizon_days": horizon,
        "currency": bundle.get("currency", "USD"),
        "projected_min_balance": round(min(forecast), 2) if forecast else 0.0,
        "projected_mean_balance": round(sum(forecast) / len(forecast), 2) if forecast else 0.0,
    }
    return _FORECAST_SUMMARY


def _assess_liquidity(txn_eur_equivalent: float, usd_to_eur: float) -> dict[str, Any]:
    """Flag liquidity risk when a transaction is material vs projected balance.

    A transaction whose EUR value exceeds 25% of the lowest projected
    30-day balance is treated as a treasury-level liquidity concern.
    """
    fc = _forecast_summary()
    min_bal = fc["projected_min_balance"]
    # Forecast series is in USD; convert to EUR for an apples-to-apples check.
    rate = usd_to_eur if usd_to_eur and usd_to_eur > 0 else 0.92
    min_bal_eur = min_bal * rate if fc["currency"] == "USD" else min_bal
    flag = bool(min_bal_eur > 0 and txn_eur_equivalent > 0.25 * min_bal_eur)
    return {
        "liquidity_risk_flag": flag,
        "projected_min_balance_eur": round(min_bal_eur, 2),
        "forecast_horizon_days": fc["horizon_days"],
        "forecast_method": fc["method"],
    }


# --- public entry point -------------------------------------------------------

def compute_ml_signals(
    txn: dict[str, Any],
    counterparty_risk_score: float,
    usd_to_eur: float,
) -> dict[str, Any]:
    """Score one bank transaction with all three models.

    Returns a flat dict consumed by both the mock agents and the live
    prompts. When ML is unavailable, returns neutral zeros + ml_available=False
    so the orchestrator keeps running on rules alone.
    """
    if not ML_AVAILABLE:
        return {
            "ml_available": False,
            "anomaly_score": 0.0,
            "anomaly_threshold": 0.0,
            "anomaly_flag": False,
            "ml_approval_probability": 1.0,
            "liquidity_risk_flag": False,
            "projected_min_balance_eur": 0.0,
            "forecast_horizon_days": 0,
            "forecast_method": "",
        }
    eur_eq = float(txn.get("eur_equivalent") or 0.0)
    out: dict[str, Any] = {"ml_available": True}
    try:
        out.update(_score_anomaly(txn))
        out["ml_approval_probability"] = _score_approval(txn, counterparty_risk_score)
        out.update(_assess_liquidity(eur_eq, usd_to_eur))
    except Exception as e:  # noqa: BLE001 — degrade, never crash a run
        return {
            "ml_available": False,
            "ml_error": f"{type(e).__name__}: {e}",
            "anomaly_score": 0.0,
            "anomaly_threshold": 0.0,
            "anomaly_flag": False,
            "ml_approval_probability": 1.0,
            "liquidity_risk_flag": False,
            "projected_min_balance_eur": 0.0,
            "forecast_horizon_days": 0,
            "forecast_method": "",
        }
    return out


if __name__ == "__main__":
    # Smoke test against a couple of synthetic transactions.
    print(status())
    demo = [
        {"transaction_id": "T1", "amount": 245000.0, "currency": "EUR",
         "eur_equivalent": 245000.0, "counterparty_name": "BoreasTrade Holdings LLP",
         "transaction_type": "wire_payment", "timestamp": "2026-05-19T03:00:00Z"},
        {"transaction_id": "T2", "amount": 8900000.0, "currency": "EUR",
         "eur_equivalent": 8900000.0, "counterparty_name": "Wayne Enterprises",
         "transaction_type": "wire_payment", "timestamp": "2026-05-19T10:00:00Z"},
    ]
    for t in demo:
        print(t["transaction_id"], compute_ml_signals(t, 0.2, 0.92))
