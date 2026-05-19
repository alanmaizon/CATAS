#!/usr/bin/env python3
"""
CATAS multi-agent orchestrator.

Drives the full Treasury -> Compliance pipeline over the bank-transactions feed.
Two execution modes:

  MOCK (default when no Lyzr creds present)
    Deterministic Python implementations of both agents. Calls the three local
    skills directly. Writes the local audit chain. Useful for demoing without
    a Lyzr deployment, and for validating the orchestration end-to-end.

  LIVE (auto when LYZR_API_KEY + agent IDs are set)
    Calls the Lyzr Agent API (POST {base}/v3/inference/chat/) for both agents.
    The agents call their skills internally (uploaded as ZIPs to Lyzr Studio).
    The orchestrator parses the JSON the agents return.

CLI:
  python orchestration/run_catas.py                              # auto-pick mode
  python orchestration/run_catas.py --mode mock                  # force mock
  python orchestration/run_catas.py --mode live                  # force live
  python orchestration/run_catas.py --transaction-id TXN-2026-SEED-001
  python orchestration/run_catas.py --limit 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

# --- Skills path setup --------------------------------------------------------
# The three skills live as standalone modules under skills/<name>/<name>.py.
# Prepend each skill dir to sys.path so we can import the functions directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_ROOT = _REPO_ROOT / "skills"
for _skill_dir in ("parse_ledger_data", "trigger_mlro_alert", "write_audit_log"):
    sys.path.insert(0, str(_SKILLS_ROOT / _skill_dir))

from parse_ledger_data import parse_ledger_data  # noqa: E402
from trigger_mlro_alert import trigger_mlro_alert  # noqa: E402
from write_audit_log import write_audit_log  # noqa: E402

# --- Config -------------------------------------------------------------------
LYZR_BASE_URL = os.environ.get("LYZR_BASE_URL", "https://agent-prod.studio.lyzr.ai")
LYZR_API_KEY = os.environ.get("LYZR_API_KEY", "")
LYZR_USER_ID = os.environ.get("LYZR_USER_ID", "catas-orchestrator")
LYZR_TREASURY_AGENT_ID = os.environ.get("LYZR_TREASURY_AGENT_ID", "")
LYZR_COMPLIANCE_AGENT_ID = os.environ.get("LYZR_COMPLIANCE_AGENT_ID", "")

# Sanctioned counterparties — mirror of the active match keys in §5 of
# data/compliance/EU_Sanctions_and_CBI_Watchlist_Mock.md. Used in MOCK mode
# to simulate the Compliance Agent's RAG-grounded lookup.
SANCTIONED_COUNTERPARTIES: dict[str, dict[str, str]] = {
    "CP-9471": {"entity_id": "SANCT-ENT-00471", "name": "BoreasTrade Holdings LLP",         "eu_reference": "EU.CFSP.2025.0991"},
    "CP-9488": {"entity_id": "SANCT-ENT-00488", "name": "Volkov Maritime Services AG",      "eu_reference": "EU.CFSP.2025.1107"},
    "CP-9502": {"entity_id": "SANCT-ENT-00502", "name": "Crescent Star Petrochemicals FZE", "eu_reference": "EU.CFSP.2026.0044"},
    "CP-9519": {"entity_id": "SANCT-ENT-00519", "name": "Atlas Northern Commodities OÜ",    "eu_reference": "EU.CFSP.2026.0118"},
    "CP-9211": {"entity_id": "SANCT-IND-00211", "name": "Dmitri A. Ostrovsky",              "eu_reference": "EU.CFSP.2025.1042"},
    "CP-9238": {"entity_id": "SANCT-IND-00238", "name": "Layla H. Mansoor",                 "eu_reference": "EU.CFSP.2026.0091"},
    "CP-9247": {"entity_id": "SANCT-IND-00247", "name": "Sergei V. Pavlenko",               "eu_reference": "EU.CFSP.2026.0133"},
}


# --- Lyzr API client (LIVE mode) ---------------------------------------------

def call_lyzr_agent(agent_id: str, session_id: str, message: str, timeout: int = 120) -> str:
    """POST a message to a Lyzr agent and return the agent's text reply.

    Endpoint: POST {LYZR_BASE_URL}/v3/inference/chat/
    Auth:     x-api-key header

    If your Lyzr tenant uses a different inference version (v1/v2) or a
    different base URL, override via LYZR_BASE_URL and adjust the path here.
    """
    try:
        import requests  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError(
            "requests not installed — run `pip install -r orchestration/requirements.txt`"
        ) from e

    if not LYZR_API_KEY:
        raise RuntimeError("LYZR_API_KEY env var is not set.")
    if not agent_id:
        raise RuntimeError("agent_id is empty — set LYZR_TREASURY_AGENT_ID / LYZR_COMPLIANCE_AGENT_ID.")

    url = f"{LYZR_BASE_URL.rstrip('/')}/v3/inference/chat/"
    headers = {"x-api-key": LYZR_API_KEY, "Content-Type": "application/json"}
    body = {
        "user_id": LYZR_USER_ID,
        "agent_id": agent_id,
        "session_id": session_id,
        "message": message,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # Lyzr response shape: typically {"response": "..."} — fall back to whole body.
    return data.get("response") or data.get("message") or json.dumps(data)


def extract_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from an LLM response.

    Tries a ```json``` fenced block first, then any {...} substring. Returns
    None if nothing parseable is found.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    bare = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if bare:
        try:
            return json.loads(bare.group(0))
        except json.JSONDecodeError:
            pass
    return None


# --- LIVE-mode agent calls ----------------------------------------------------

def call_treasury_agent_live(transaction: dict[str, Any], session_id: str) -> dict[str, Any]:
    message = (
        "You are the CATAS Treasury Agent. Reconcile this bank transaction.\n\n"
        "Transaction:\n"
        f"  ID:           {transaction.get('transaction_id', '')}\n"
        f"  Amount:       {transaction.get('amount', 0)} {transaction.get('currency', '')}\n"
        f"  EUR equiv:    {transaction.get('eur_equivalent') or 0:.2f}\n"
        f"  Counterparty: {transaction.get('counterparty_name', '')} ({transaction.get('counterparty_id', '')})\n"
        f"  Type:         {transaction.get('transaction_type', '')}\n"
        f"  Reference:    {transaction.get('reference', '')}\n"
        f"  Bank date:    {transaction.get('bank_date', '')}\n\n"
        "Steps:\n"
        "1. Call your parse_ledger_data skill to load the snapshot.\n"
        "2. Look for this transaction in candidate_reconciliation_matches.\n"
        "3. Return JSON in a fenced ```json``` block with keys:\n"
        "   reconciled (bool), gl_id (string|null), match_basis (list[string]), notes (string)\n"
    )
    raw = call_lyzr_agent(LYZR_TREASURY_AGENT_ID, session_id, message)
    parsed = extract_json_from_response(raw)
    if parsed is None:
        return {"reconciled": False, "gl_id": None, "match_basis": [], "notes": raw[:300]}
    return parsed


def call_compliance_agent_live(
    transaction: dict[str, Any], treasury_result: dict[str, Any], session_id: str
) -> dict[str, Any]:
    message = (
        "You are the CATAS Compliance Agent. Evaluate this transaction against "
        "Rules 1-4 of the Internal AML Treasury Policy (Republic of Ireland).\n\n"
        "Transaction:\n"
        f"{json.dumps(transaction, indent=2, default=str)}\n\n"
        "Treasury reconciliation:\n"
        f"{json.dumps(treasury_result, indent=2, default=str)}\n\n"
        "Steps:\n"
        "1. Call parse_ledger_data for FX rates, risk index, baseline index.\n"
        "2. Check Rule 2 (sanctions) FIRST. If matched, call trigger_mlro_alert\n"
        "   with priority='P1-URGENT'. Rule 2 supersedes all others — decision=BLOCK.\n"
        "3. If Rule 2 passes, evaluate Rule 1 (>€50K EUR-equivalent),\n"
        "   Rule 3 (variance vs rolling baseline), Rule 4 (counterparty_risk_score).\n"
        "4. ALWAYS call write_audit_log last with the final decision and per-rule outcomes.\n\n"
        "Use the EU_Sanctions_and_CBI_Watchlist_Mock and Internal_AML_Treasury_Policy_Ireland\n"
        "documents from your RAG knowledge base to ground your reasoning.\n\n"
        "Return JSON in a fenced ```json``` block with keys:\n"
        "  decision (\"APPROVE\"|\"HOLD\"|\"BLOCK\"),\n"
        "  rules_evaluated (list of {rule, outcome, evidence}),\n"
        "  case_ticket_id (string, empty if no MLRO alert),\n"
        "  audit_entry_id (string from write_audit_log),\n"
        "  notes (string)\n"
    )
    raw = call_lyzr_agent(LYZR_COMPLIANCE_AGENT_ID, session_id, message)
    parsed = extract_json_from_response(raw)
    if parsed is None:
        return {
            "decision": "HOLD",
            "rules_evaluated": [],
            "case_ticket_id": "",
            "audit_entry_id": "",
            "notes": f"Could not parse JSON from agent response: {raw[:300]}",
        }
    return parsed


# --- MOCK-mode agents (deterministic policy in Python) -----------------------

def call_treasury_agent_mock(
    transaction: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Treasury reconciliation against pre-computed candidate matches."""
    txn_id = transaction.get("transaction_id")
    candidates = [
        m for m in snapshot["candidate_reconciliation_matches"]
        if m["bank_transaction_id"] == txn_id
    ]
    if candidates:
        best = candidates[0]
        if {"reference", "amount", "currency"}.issubset(best["match_basis"]):
            return {
                "reconciled": True,
                "gl_id": best["gl_id"],
                "match_basis": best["match_basis"],
                "notes": "Strong match on reference + amount + currency.",
            }
        return {
            "reconciled": False,
            "gl_id": best["gl_id"],
            "match_basis": best["match_basis"],
            "notes": "Reference matched but secondary fields disagree — manual review.",
        }
    return {
        "reconciled": False,
        "gl_id": None,
        "match_basis": [],
        "notes": "No GL entry matched by reference — first-time-payee or external transfer.",
    }


def call_compliance_agent_mock(
    transaction: dict[str, Any], snapshot: dict[str, Any], treasury_result: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate Rules 1-4 deterministically. Mirrors Internal_AML_Treasury_Policy_Ireland."""
    rules: list[dict[str, Any]] = []
    decision = "APPROVE"
    case_ticket_id = ""

    cp_id = transaction.get("counterparty_id", "") or ""
    cp_name = transaction.get("counterparty_name", "") or ""
    eur_eq = transaction.get("eur_equivalent") or 0.0
    currency = transaction.get("currency", "") or ""
    amount = transaction.get("amount", 0.0) or 0.0
    fx_rate = transaction.get("fx_rate_used") or 0.0
    txn_type = transaction.get("transaction_type", "") or ""

    # Rule 2 — sanctions screening (supersedes everything)
    sanc = SANCTIONED_COUNTERPARTIES.get(cp_id)
    if sanc:
        evidence = (
            f"Exact match counterparty_id={cp_id} -> {sanc['entity_id']} "
            f"({sanc['name']}). EU ref {sanc['eu_reference']}."
        )
        rules.append({"rule": "Rule 2", "outcome": "BLOCK", "evidence": evidence})

        alert = trigger_mlro_alert(
            transaction_id=transaction.get("transaction_id", ""),
            counterparty_id=cp_id,
            counterparty_name=cp_name,
            matched_rule="Rule 2 — Sanctions Screening and Automatic Block",
            matched_entity_id=sanc["entity_id"],
            eu_reference=sanc["eu_reference"],
            amount=amount,
            currency=currency,
            eur_equivalent=eur_eq,
            evidence=[evidence],
        )
        case_ticket_id = alert.get("case_ticket_id", "")

        for r in ("Rule 1", "Rule 3", "Rule 4"):
            rules.append({"rule": r, "outcome": "SKIP", "evidence": "Rule 2 supersedes."})
        decision = "BLOCK"

    else:
        # Rule 1 — €50K EUR-equivalent threshold
        if eur_eq > 50_000:
            rules.append({
                "rule": "Rule 1",
                "outcome": "HOLD",
                "evidence": (
                    f"EUR-equivalent {eur_eq:,.2f} > 50,000 threshold "
                    f"(orig {amount:,.2f} {currency} @ rate {fx_rate}). "
                    f"Level 2 ACE-V required."
                ),
            })
            decision = "HOLD"
        else:
            rules.append({
                "rule": "Rule 1",
                "outcome": "PASS",
                "evidence": f"EUR-equivalent {eur_eq:,.2f} within €50,000 threshold.",
            })

        # Rule 3 — variance vs rolling baseline
        baseline = snapshot["counterparty_baseline_index"].get(f"{cp_id}|{txn_type}")
        if baseline and baseline.get("count", 0) >= 5 and baseline.get("mean_eur"):
            mean = float(baseline["mean_eur"])
            variance_pct = abs(eur_eq - mean) / mean * 100
            window = baseline.get("window_days_used")
            n = baseline.get("count")
            if variance_pct > 5:
                rules.append({
                    "rule": "Rule 3",
                    "outcome": "HOLD",
                    "evidence": (
                        f"Variance {variance_pct:.1f}% > 5% band "
                        f"(baseline EUR {mean:,.2f}, n={n}, window={window}d). "
                        f"Treasury Manager + duplicate-check required."
                    ),
                })
                if decision == "APPROVE":
                    decision = "HOLD"
            elif variance_pct > 2:
                rules.append({
                    "rule": "Rule 3",
                    "outcome": "HOLD",
                    "evidence": (
                        f"Variance {variance_pct:.1f}% in 2-5% band "
                        f"(baseline EUR {mean:,.2f}, n={n}). AP Lead sign-off."
                    ),
                })
                if decision == "APPROVE":
                    decision = "HOLD"
            else:
                rules.append({
                    "rule": "Rule 3",
                    "outcome": "PASS",
                    "evidence": f"Variance {variance_pct:.1f}% within 2% band (baseline EUR {mean:,.2f}).",
                })
        else:
            rules.append({
                "rule": "Rule 3",
                "outcome": "SKIP",
                "evidence": "Insufficient baseline (< 5 prior txns) — first-time-payee path.",
            })

        # Rule 4 — counterparty_risk_score
        risk = snapshot["counterparty_risk_index"].get(cp_id, 0.0)
        if risk >= 0.95:
            evidence = f"counterparty_risk_score {risk:.2f} >= 0.95 — auto-escalate to MLRO."
            rules.append({"rule": "Rule 4", "outcome": "HOLD", "evidence": evidence})
            if not case_ticket_id:
                alert = trigger_mlro_alert(
                    transaction_id=transaction.get("transaction_id", ""),
                    counterparty_id=cp_id,
                    counterparty_name=cp_name,
                    matched_rule="Rule 4 — Counterparty Risk Score >= 0.95",
                    matched_entity_id=f"RISK-{cp_id}",
                    eu_reference="CJA-2010-S30A",
                    amount=amount,
                    currency=currency,
                    eur_equivalent=eur_eq,
                    evidence=[evidence],
                )
                case_ticket_id = alert.get("case_ticket_id", "")
            decision = "HOLD"
        elif risk >= 0.85:
            rules.append({
                "rule": "Rule 4",
                "outcome": "HOLD",
                "evidence": f"counterparty_risk_score {risk:.2f} in 0.85-0.95 — EDD required.",
            })
            if decision == "APPROVE":
                decision = "HOLD"
        elif risk >= 0.50:
            rules.append({
                "rule": "Rule 4",
                "outcome": "PASS",
                "evidence": f"counterparty_risk_score {risk:.2f} in 0.50-0.85 soft-flag band.",
            })
        else:
            rules.append({
                "rule": "Rule 4",
                "outcome": "PASS",
                "evidence": f"counterparty_risk_score {risk:.2f} < 0.50 — standard processing.",
            })

    # Final immutable audit-trail entry
    audit = write_audit_log(
        transaction_id=transaction.get("transaction_id", ""),
        decision=decision,
        rules_evaluated=rules,
        counterparty_id=cp_id,
        counterparty_name=cp_name,
        amount=amount,
        currency=currency,
        eur_equivalent=eur_eq,
        fx_rate_used=fx_rate,
        case_ticket_id=case_ticket_id,
    )

    return {
        "decision": decision,
        "rules_evaluated": rules,
        "case_ticket_id": case_ticket_id,
        "audit_entry_id": audit.get("entry_id", ""),
        "notes": "Mock-mode deterministic evaluation.",
    }


# --- Orchestrator -------------------------------------------------------------

def orchestrate(
    mode: str,
    snapshot: dict[str, Any],
    transactions: list[dict[str, Any]],
    verbose: bool = False,
) -> dict[str, Any]:
    """Run Treasury -> Compliance over each transaction. Returns aggregate stats."""
    session_id = f"catas-{int(time.time())}"
    counts: dict[str, int] = {"APPROVE": 0, "HOLD": 0, "BLOCK": 0, "ERROR": 0}
    per_txn: list[dict[str, Any]] = []

    print(f"\n[Run] mode={mode}  session={session_id}  txns={len(transactions)}")
    header = f"  {'TXN ID':<25} {'COUNTERPARTY':<35} {'EUR EQ':>14}  {'DECISION':<8}  RULE OUTCOMES"
    print(header)
    print("  " + "-" * (len(header) + 10))

    for txn in transactions:
        try:
            if mode == "live":
                treasury = call_treasury_agent_live(txn, session_id)
                compliance = call_compliance_agent_live(txn, treasury, session_id)
            else:
                treasury = call_treasury_agent_mock(txn, snapshot)
                compliance = call_compliance_agent_mock(txn, snapshot, treasury)

            decision = compliance.get("decision", "ERROR")
            counts[decision] = counts.get(decision, 0) + 1
            per_txn.append({
                "transaction_id": txn.get("transaction_id"),
                "treasury": treasury,
                "compliance": compliance,
            })

            rules = compliance.get("rules_evaluated", [])
            rule_summary = " ".join(
                f"{r.get('rule', '?').split()[-1]}={r.get('outcome', '?')[:4]}"
                for r in rules
            )
            eur_str = f"EUR {(txn.get('eur_equivalent') or 0):>10,.0f}"
            cp_name = (txn.get("counterparty_name") or "")[:35]
            print(
                f"  {txn.get('transaction_id', ''):<25} {cp_name:<35} "
                f"{eur_str:>14}  {decision:<8}  {rule_summary}"
            )
            if verbose:
                for r in rules:
                    print(f"      - {r.get('rule')}: {r.get('outcome')} — {r.get('evidence')}")
                if compliance.get("case_ticket_id"):
                    print(f"      MLRO case: {compliance['case_ticket_id']}")
                if compliance.get("audit_entry_id"):
                    print(f"      Audit entry: {compliance['audit_entry_id']}")

        except Exception as e:  # noqa: BLE001 — keep the run going on per-txn failures
            counts["ERROR"] += 1
            print(f"  ERROR processing {txn.get('transaction_id')}: {type(e).__name__}: {e}")
            per_txn.append({
                "transaction_id": txn.get("transaction_id"),
                "error": f"{type(e).__name__}: {e}",
            })

    return {"counts": counts, "per_transaction": per_txn, "session_id": session_id}


def _load_dotenv_if_present() -> None:
    """Best-effort .env loader. Tries python-dotenv, falls back to manual parse."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    # Manual fallback — no python-dotenv installed
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _refresh_config_from_env() -> None:
    """Re-read module-level config after .env has been loaded."""
    global LYZR_BASE_URL, LYZR_API_KEY, LYZR_USER_ID, LYZR_TREASURY_AGENT_ID, LYZR_COMPLIANCE_AGENT_ID
    LYZR_BASE_URL = os.environ.get("LYZR_BASE_URL", LYZR_BASE_URL)
    LYZR_API_KEY = os.environ.get("LYZR_API_KEY", LYZR_API_KEY)
    LYZR_USER_ID = os.environ.get("LYZR_USER_ID", LYZR_USER_ID)
    LYZR_TREASURY_AGENT_ID = os.environ.get("LYZR_TREASURY_AGENT_ID", LYZR_TREASURY_AGENT_ID)
    LYZR_COMPLIANCE_AGENT_ID = os.environ.get("LYZR_COMPLIANCE_AGENT_ID", LYZR_COMPLIANCE_AGENT_ID)


def main() -> int:
    parser = argparse.ArgumentParser(description="CATAS multi-agent orchestrator")
    parser.add_argument("--mode", choices=["auto", "live", "mock"], default="auto",
                        help="auto (default) picks live when Lyzr creds are set, else mock")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only the first N transactions (0 = all)")
    parser.add_argument("--transaction-id", default="",
                        help="Process only this transaction ID")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-rule evidence and MLRO/audit IDs")
    args = parser.parse_args()

    _load_dotenv_if_present()
    _refresh_config_from_env()

    if args.mode == "auto":
        live_ready = bool(LYZR_API_KEY and LYZR_TREASURY_AGENT_ID and LYZR_COMPLIANCE_AGENT_ID)
        mode = "live" if live_ready else "mock"
    else:
        mode = args.mode

    print(f"\nCATAS orchestrator — {mode.upper()} mode")
    print("=" * 80)
    if mode == "live":
        print(f"  Lyzr base URL:        {LYZR_BASE_URL}")
        print(f"  Treasury agent:       {LYZR_TREASURY_AGENT_ID}")
        print(f"  Compliance agent:     {LYZR_COMPLIANCE_AGENT_ID}")
        print(f"  User ID:              {LYZR_USER_ID}")
    else:
        print("  (no Lyzr credentials detected — running deterministic local agents)")

    print("\n[1/2] Loading data snapshot via parse_ledger_data ...")
    snapshot = parse_ledger_data()
    s = snapshot["summary"]
    print(f"      Bank txns:        {s['bank_txn_count']}")
    print(f"      GL entries:       {s['gl_entry_count']}")
    print(f"      Historical rows:  {s['historical_count']}")
    print(f"      Currencies:       {', '.join(s['currencies_seen'])}")
    print(f"      Risk index:       {len(snapshot['counterparty_risk_index'])} counterparties")
    print(f"      Baseline index:   {len(snapshot['counterparty_baseline_index'])} (cp, type) groups")

    txns = snapshot["bank_transactions"]
    if args.transaction_id:
        txns = [t for t in txns if t.get("transaction_id") == args.transaction_id]
        if not txns:
            print(f"\nNo transaction matched id '{args.transaction_id}'.")
            return 1
    if args.limit > 0:
        txns = txns[: args.limit]

    print(f"\n[2/2] Orchestrating {len(txns)} transaction(s) ...")
    result = orchestrate(mode, snapshot, txns, verbose=args.verbose)

    c = result["counts"]
    print("\n" + "=" * 80)
    print(
        f"Final tally:  APPROVE={c.get('APPROVE', 0)}  "
        f"HOLD={c.get('HOLD', 0)}  BLOCK={c.get('BLOCK', 0)}  ERROR={c.get('ERROR', 0)}"
    )
    print(f"Audit trail:  {_REPO_ROOT / 'logs' / 'audit_trail.jsonl'}")
    print(f"MLRO alerts:  {_REPO_ROOT / 'logs' / 'mlro_alerts.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
