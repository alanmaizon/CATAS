"""
CATAS Skill: parse_ledger_data

Loads and parses the canonical financial-data files for the CATAS Treasury Agent
and returns a structured, pre-indexed snapshot. The agent calls this skill once
at the start of an incident loop instead of ingesting raw JSON/CSV into its
LLM context window.

Source files (defaults assume CATAS v2 mock dataset):
  - bank_transactions_input_v2.json   inbound bank feed
  - gl_ledger_v2.json                 general-ledger entries
  - historical_transactions_v2.csv    historical record with counterparty_risk_score
  - fx_rates.csv                      ECB EUR reference rates

Output is one dict containing:
  - bank_transactions (each row enriched with eur_equivalent)
  - gl_entries (each row enriched with eur_equivalent)
  - fx_rates (nested by date)
  - counterparty_risk_index (latest counterparty_risk_score per counterparty_id)
  - counterparty_baseline_index (rolling-window mean EUR amount per
    (counterparty_id, transaction_type); window auto-widens if 90-day window
    has fewer than 5 rows)
  - candidate_reconciliation_matches (naive joins on reference + amount)
  - summary stats

Data-directory resolution order:
  1. `data_dir` argument (if non-empty)
  2. CATAS_DATA_DIR environment variable
  3. ./data relative to CWD
  4. ../data relative to this file (skill subdirectory layout)
  5. ../../data relative to this file (repo layout)
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def parse_ledger_data(
    bank_feed_filename: str = "bank_transactions_input_v2.json",
    gl_ledger_filename: str = "gl_ledger_v2.json",
    historical_filename: str = "historical_transactions_v2.csv",
    fx_rates_filename: str = "fx_rates.csv",
    data_dir: str = "",
    baseline_window_days: int = 90,
    baseline_fallback_windows: list[int] | None = None,
) -> dict[str, Any]:
    """
    Load the four canonical CATAS data files and return a pre-indexed snapshot.

    Args:
        bank_feed_filename: filename (in data_dir) of the bank-feed JSON.
        gl_ledger_filename: filename (in data_dir) of the GL JSON.
        historical_filename: filename (in data_dir) of the historical-txn CSV.
        fx_rates_filename: filename (in data_dir) of the FX-rates CSV.
        data_dir: directory containing the four files. Empty string triggers
            the resolution order documented at the top of this module.
        baseline_window_days: primary lookback window (in days) for the
            rolling-mean baseline used by Rule 3. Default 90 (policy-aligned).
        baseline_fallback_windows: widened windows to try if the primary
            window has fewer than 5 rows for a (counterparty, type) pair.
            Default [365, 730]. Set to [] to disable auto-widening.

    Returns:
        A dict with keys:
          bank_transactions: list[dict] — each bank-feed row, plus
              `eur_equivalent` (float|None) and `fx_rate_used` (float|None).
          gl_entries: list[dict] — each GL row, plus `eur_equivalent`.
          fx_rates: dict[date_str, dict[currency, rate_to_eur]].
          counterparty_risk_index: dict[counterparty_id, float] —
              latest counterparty_risk_score observed in the historical CSV.
          counterparty_baseline_index: dict[
              "<counterparty_id>|<transaction_type>",
              {"mean_eur": float, "stdev_eur": float, "count": int,
               "window_days_used": int}
          ].
          candidate_reconciliation_matches: list[
              {"bank_transaction_id": str, "gl_id": str, "match_basis": list[str]}
          ].
          summary: dict with bank_txn_count, gl_entry_count, historical_count,
              currencies_seen, anchor_date, baseline_window_days_default.
    """
    if baseline_fallback_windows is None:
        baseline_fallback_windows = [365, 730]

    base = _resolve_data_dir(data_dir)

    bank_txns = _load_json_list(base / bank_feed_filename)
    gl_entries = _load_json_list(base / gl_ledger_filename)
    fx_rates_flat, fx_rates_nested = _load_fx_rates(base / fx_rates_filename)

    anchor = _max_date(bank_txns, "bank_date") or date.today().isoformat()

    for row in bank_txns:
        eur, rate = _convert_to_eur(
            row.get("amount"), row.get("currency"), row.get("bank_date"), fx_rates_flat
        )
        row["eur_equivalent"] = eur
        row["fx_rate_used"] = rate

    for row in gl_entries:
        eur, rate = _convert_to_eur(
            row.get("amount"), row.get("currency"), row.get("gl_date"), fx_rates_flat
        )
        row["eur_equivalent"] = eur
        row["fx_rate_used"] = rate

    risk_index, baseline_index, historical_count, currencies_in_hist = _build_historical_indices(
        base / historical_filename,
        fx_rates_flat,
        anchor_date=anchor,
        primary_window_days=baseline_window_days,
        fallback_windows=baseline_fallback_windows,
    )

    candidate_matches = _naive_reconciliation_matches(bank_txns, gl_entries)

    currencies_seen = sorted(
        {row.get("currency") for row in bank_txns if row.get("currency")}
        | {row.get("currency") for row in gl_entries if row.get("currency")}
        | currencies_in_hist
    )

    return {
        "bank_transactions": bank_txns,
        "gl_entries": gl_entries,
        "fx_rates": fx_rates_nested,
        "counterparty_risk_index": risk_index,
        "counterparty_baseline_index": baseline_index,
        "candidate_reconciliation_matches": candidate_matches,
        "summary": {
            "bank_txn_count": len(bank_txns),
            "gl_entry_count": len(gl_entries),
            "historical_count": historical_count,
            "currencies_seen": currencies_seen,
            "anchor_date": anchor,
            "baseline_window_days_default": baseline_window_days,
        },
    }


def _resolve_data_dir(data_dir: str) -> Path:
    if data_dir:
        return Path(data_dir)
    env = os.environ.get("CATAS_DATA_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    candidates = [
        Path("data"),
        here.parent / "data",
        here.parent.parent / "data",
        here.parent.parent.parent / "data",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("data")


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CATAS data file not found: {path}")
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list at {path}; got {type(data).__name__}")
    return data


def _load_fx_rates(path: Path) -> tuple[dict[tuple[str, str], float], dict[str, dict[str, float]]]:
    if not path.exists():
        raise FileNotFoundError(f"FX rates file not found: {path}")
    flat: dict[tuple[str, str], float] = {}
    nested: dict[str, dict[str, float]] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            d, c, r = row["date"], row["currency"], float(row["rate_to_eur"])
            flat[(d, c)] = r
            nested.setdefault(d, {})[c] = r
    return flat, nested


def _convert_to_eur(
    amount: Any, currency: Any, date_str: Any, fx_rates: dict[tuple[str, str], float]
) -> tuple[float | None, float | None]:
    if amount is None or currency is None:
        return None, None
    if currency == "EUR":
        return float(amount), 1.0
    if not date_str:
        return None, None
    rate = fx_rates.get((date_str, currency))
    if rate is None:
        prior = sorted(d for (d, c) in fx_rates if c == currency and d <= date_str)
        if prior:
            rate = fx_rates[(prior[-1], currency)]
    if rate is None:
        return None, None
    return float(amount) * rate, rate


def _max_date(rows: list[dict[str, Any]], date_field: str) -> str | None:
    vals = [r.get(date_field) for r in rows if r.get(date_field)]
    return max(vals) if vals else None


def _build_historical_indices(
    path: Path,
    fx_rates: dict[tuple[str, str], float],
    anchor_date: str,
    primary_window_days: int,
    fallback_windows: list[int],
) -> tuple[dict[str, float], dict[str, dict[str, Any]], int, set[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Historical file not found: {path}")

    anchor_dt = datetime.fromisoformat(anchor_date).date()
    risk_latest: dict[str, tuple[str, float]] = {}
    grouped: dict[tuple[str, str], list[tuple[str, float]]] = {}
    currencies: set[str] = set()
    count = 0

    with path.open() as f:
        for row in csv.DictReader(f):
            count += 1
            cp_id = row.get("counterparty_id")
            if not cp_id:
                continue

            try:
                score = float(row.get("counterparty_risk_score", "") or "nan")
            except ValueError:
                score = float("nan")
            row_date = row.get("date", "")
            if score == score:
                existing = risk_latest.get(cp_id)
                if existing is None or row_date > existing[0]:
                    risk_latest[cp_id] = (row_date, score)

            txn_type = row.get("transaction_type")
            ccy = row.get("currency")
            if ccy:
                currencies.add(ccy)
            if txn_type and ccy and row_date:
                try:
                    amt = float(row.get("amount", "") or "nan")
                except ValueError:
                    amt = float("nan")
                eur, _ = _convert_to_eur(amt, ccy, row_date, fx_rates)
                if eur is not None and eur == eur:
                    grouped.setdefault((cp_id, txn_type), []).append((row_date, eur))

    risk_index = {cp: score for cp, (_, score) in risk_latest.items()}

    windows_to_try = [primary_window_days, *fallback_windows]
    baseline_index: dict[str, dict[str, Any]] = {}

    for (cp_id, txn_type), entries in grouped.items():
        chosen = None
        for w in windows_to_try:
            start = (anchor_dt - timedelta(days=w)).isoformat()
            filtered = [eur for (d, eur) in entries if start <= d <= anchor_date]
            if len(filtered) >= 5:
                chosen = (filtered, w)
                break
        if chosen is None:
            # All windows had < 5 rows — use the widest window's data even if sparse.
            widest = windows_to_try[-1]
            start = (anchor_dt - timedelta(days=widest)).isoformat()
            filtered = [eur for (d, eur) in entries if start <= d <= anchor_date]
            chosen = (filtered, widest)

        values, window_used = chosen
        if not values:
            continue
        mean_eur = sum(values) / len(values)
        stdev_eur = statistics.pstdev(values) if len(values) > 1 else 0.0
        baseline_index[f"{cp_id}|{txn_type}"] = {
            "mean_eur": round(mean_eur, 2),
            "stdev_eur": round(stdev_eur, 2),
            "count": len(values),
            "window_days_used": window_used,
        }

    return risk_index, baseline_index, count, currencies


def _naive_reconciliation_matches(
    bank_txns: list[dict[str, Any]], gl_entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    gl_by_ref: dict[str, list[dict[str, Any]]] = {}
    for g in gl_entries:
        ref = g.get("reference")
        if ref:
            gl_by_ref.setdefault(ref, []).append(g)

    candidates: list[dict[str, Any]] = []
    for b in bank_txns:
        ref = b.get("reference")
        if not ref or ref not in gl_by_ref:
            continue
        for g in gl_by_ref[ref]:
            basis = ["reference"]
            if b.get("amount") == g.get("amount"):
                basis.append("amount")
            if b.get("currency") == g.get("currency"):
                basis.append("currency")
            if b.get("counterparty_name") == g.get("counterparty_name"):
                basis.append("counterparty_name")
            candidates.append({
                "bank_transaction_id": b.get("transaction_id"),
                "gl_id": g.get("gl_id"),
                "match_basis": basis,
            })
    return candidates


if __name__ == "__main__":
    result = parse_ledger_data()
    summary = result["summary"]
    print(f"Bank transactions loaded:      {summary['bank_txn_count']}")
    print(f"GL entries loaded:             {summary['gl_entry_count']}")
    print(f"Historical rows scanned:       {summary['historical_count']}")
    print(f"Currencies observed:           {summary['currencies_seen']}")
    print(f"Anchor date (latest bank_date):{summary['anchor_date']}")
    print(f"Risk index entries:            {len(result['counterparty_risk_index'])}")
    print(f"Baseline index entries:        {len(result['counterparty_baseline_index'])}")
    print(f"Candidate reconciliation hits: {len(result['candidate_reconciliation_matches'])}")
    high_risk = {cp: s for cp, s in result["counterparty_risk_index"].items() if s >= 0.85}
    print(f"Counterparties with risk >= 0.85: {high_risk}")
    print("Sample baseline entries (first 3):")
    for k, v in list(result["counterparty_baseline_index"].items())[:3]:
        print(f"  {k}: {v}")
