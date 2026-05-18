"""
CATAS Skill: write_audit_log

Appends a structured, tamper-evident audit entry to logs/audit_trail.jsonl
each time the Compliance Agent reaches a final disposition on a transaction.

Each entry includes a SHA-256 chain hash computed from the previous entry's
hash concatenated with the current entry's canonical JSON bytes — making the
log a verifiable hash chain. Any retro-active edit of a prior entry breaks
every chain hash thereafter.

This satisfies the "explainable, immutable audit trail" requirement of
Internal_AML_Treasury_Policy_Ireland §5, retained for 5 years under
CJA 2010 §55.

Log-directory resolution order:
  1. `log_dir` argument
  2. CATAS_LOG_DIR environment variable
  3. ./logs relative to CWD
  4. ../logs / ../../logs / ../../../logs relative to this file
  5. ./logs (created on first write)
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_FILENAME = "audit_trail.jsonl"
_GENESIS_BYTES = b"CATAS-AUDIT-CHAIN-GENESIS-v1"


def write_audit_log(
    transaction_id: str,
    decision: str,
    rules_evaluated: list[dict[str, Any]],
    counterparty_id: str,
    counterparty_name: str,
    amount: float,
    currency: str,
    eur_equivalent: float = 0.0,
    fx_rate_used: float = 0.0,
    approver: str = "",
    case_ticket_id: str = "",
    log_dir: str = "",
) -> dict[str, Any]:
    """
    Append a tamper-evident audit-log entry for a transaction decision.

    Args:
        transaction_id: Bank-feed transaction ID being decided.
        decision: Final disposition — one of "APPROVE", "BLOCK", "HOLD".
        rules_evaluated: List of per-rule outcomes, each shaped like:
            {"rule": "Rule 1", "outcome": "PASS"|"HOLD"|"BLOCK"|"SKIP",
             "evidence": "free-text or rule citation"}.
        counterparty_id: Counterparty ID (e.g. "CP-1011").
        counterparty_name: Counterparty name as observed.
        amount: Original transaction amount.
        currency: Original transaction currency (ISO 4217).
        eur_equivalent: FX-converted amount (0.0 if not computed).
        fx_rate_used: FX rate applied (0.0 if not applicable).
        approver: Identity of the human approver (empty for auto-decisions).
        case_ticket_id: MLRO case-ticket reference (empty if not applicable).
        log_dir: Override path for the logs/ directory.

    Returns:
        dict with:
          ok (bool):              True if write succeeded.
          entry_id (str):         UUID-derived ID of this entry.
          audit_chain_hash (str): SHA-256 hex digest after appending this entry.
          previous_chain_hash:    hex digest of the chain prior to this entry.
          log_path (str):         absolute path to the audit log file.
          entry_count_after:      total entry count after the append.
          error (str|None):       error string if write failed, else None.
    """
    required_fields = {
        "transaction_id": transaction_id,
        "counterparty_id": counterparty_id,
        "counterparty_name": counterparty_name,
        "currency": currency,
    }
    missing = [k for k, v in required_fields.items() if not (isinstance(v, str) and v.strip())]
    if missing:
        return {
            "ok": False,
            "entry_id": "",
            "audit_chain_hash": "",
            "previous_chain_hash": "",
            "log_path": "",
            "entry_count_after": 0,
            "error": f"Missing or empty required field(s): {', '.join(missing)}",
        }

    if not rules_evaluated:
        return {
            "ok": False,
            "entry_id": "",
            "audit_chain_hash": "",
            "previous_chain_hash": "",
            "log_path": "",
            "entry_count_after": 0,
            "error": "rules_evaluated must be a non-empty list of rule outcomes.",
        }

    if decision not in ("APPROVE", "BLOCK", "HOLD"):
        return {
            "ok": False,
            "entry_id": "",
            "audit_chain_hash": "",
            "previous_chain_hash": "",
            "log_path": "",
            "entry_count_after": 0,
            "error": f"Invalid decision '{decision}'. Must be APPROVE | BLOCK | HOLD.",
        }

    log_directory = _resolve_log_dir(log_dir)
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {
            "ok": False,
            "entry_id": "",
            "audit_chain_hash": "",
            "previous_chain_hash": "",
            "log_path": "",
            "entry_count_after": 0,
            "error": f"Failed to create log dir: {e}",
        }

    log_path = log_directory / _LOG_FILENAME
    previous_hash, current_count = _load_chain_state(log_path)

    entry_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"
    entry_body = {
        "entry_id": entry_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "transaction_id": transaction_id,
        "decision": decision,
        "counterparty": {
            "counterparty_id": counterparty_id,
            "counterparty_name": counterparty_name,
        },
        "amount": {
            "original": amount,
            "currency": currency,
            "eur_equivalent": eur_equivalent,
            "fx_rate_used": fx_rate_used,
        },
        "rules_evaluated": rules_evaluated,
        "approver": approver or None,
        "case_ticket_id": case_ticket_id or None,
        "previous_chain_hash": previous_hash,
    }

    canonical = json.dumps(entry_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    chain_hash = hashlib.sha256(bytes.fromhex(previous_hash) + canonical).hexdigest()
    entry_body["audit_chain_hash"] = chain_hash

    try:
        with log_path.open("a") as f:
            f.write(json.dumps(entry_body) + "\n")
    except OSError as e:
        return {
            "ok": False,
            "entry_id": entry_id,
            "audit_chain_hash": "",
            "previous_chain_hash": previous_hash,
            "log_path": str(log_path),
            "entry_count_after": current_count,
            "error": f"Failed to append: {e}",
        }

    return {
        "ok": True,
        "entry_id": entry_id,
        "audit_chain_hash": chain_hash,
        "previous_chain_hash": previous_hash,
        "log_path": str(log_path),
        "entry_count_after": current_count + 1,
        "error": None,
    }


def verify_audit_chain(log_path: str = "") -> dict[str, Any]:
    """
    Re-walk the audit chain and verify each entry's hash.

    Args:
        log_path: Path to the audit-trail file. Empty = resolved default.

    Returns:
        dict with:
          ok (bool):                  True if every entry's chain hash verifies.
          entries_checked (int):      Number of entries successfully verified.
          first_broken_entry (str|None): entry_id of the first mismatch, if any.
          log_path (str):             The path that was checked.
          reason (str, optional):     Failure reason when ok=False.
    """
    path = Path(log_path) if log_path else _resolve_log_dir("") / _LOG_FILENAME
    if not path.exists():
        return {"ok": True, "entries_checked": 0, "first_broken_entry": None, "log_path": str(path)}

    prev = hashlib.sha256(_GENESIS_BYTES).hexdigest()
    checked = 0
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            stored_hash = entry.pop("audit_chain_hash")
            stored_prev = entry.get("previous_chain_hash")
            if stored_prev != prev:
                return {
                    "ok": False,
                    "entries_checked": checked,
                    "first_broken_entry": entry.get("entry_id"),
                    "log_path": str(path),
                    "reason": "previous_chain_hash mismatch",
                }
            recomputed = hashlib.sha256(
                bytes.fromhex(prev)
                + json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if recomputed != stored_hash:
                return {
                    "ok": False,
                    "entries_checked": checked,
                    "first_broken_entry": entry.get("entry_id"),
                    "log_path": str(path),
                    "reason": "audit_chain_hash mismatch",
                }
            prev = stored_hash
            checked += 1

    return {"ok": True, "entries_checked": checked, "first_broken_entry": None, "log_path": str(path)}


def _resolve_log_dir(log_dir: str) -> Path:
    if log_dir:
        return Path(log_dir)
    env = os.environ.get("CATAS_LOG_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    candidates = [
        Path("logs"),
        here.parent / "logs",
        here.parent.parent / "logs",
        here.parent.parent.parent / "logs",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("logs")


def _load_chain_state(log_path: Path) -> tuple[str, int]:
    if not log_path.exists():
        return hashlib.sha256(_GENESIS_BYTES).hexdigest(), 0
    count = 0
    last_hash: str | None = None
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                last_hash = json.loads(line).get("audit_chain_hash")
            except json.JSONDecodeError:
                continue
    if last_hash is None:
        return hashlib.sha256(_GENESIS_BYTES).hexdigest(), count
    return last_hash, count


if __name__ == "__main__":
    out1 = write_audit_log(
        transaction_id="TXN-2026-SEED-001",
        decision="BLOCK",
        rules_evaluated=[
            {"rule": "Rule 1", "outcome": "SKIP", "evidence": "Rule 2 supersedes."},
            {
                "rule": "Rule 2",
                "outcome": "BLOCK",
                "evidence": "Exact match counterparty_id=CP-9471 -> SANCT-ENT-00471 (BoreasTrade).",
            },
            {"rule": "Rule 3", "outcome": "SKIP", "evidence": "Rule 2 supersedes."},
            {"rule": "Rule 4", "outcome": "SKIP", "evidence": "Rule 2 supersedes."},
        ],
        counterparty_id="CP-9471",
        counterparty_name="BoreasTrade Holdings LLP",
        amount=245000.00,
        currency="EUR",
        eur_equivalent=245000.00,
        fx_rate_used=1.0,
        approver="",
        case_ticket_id="MLRO-ABC123456789",
    )
    print(json.dumps(out1, indent=2))

    out2 = write_audit_log(
        transaction_id="TXN-2026-0042",
        decision="APPROVE",
        rules_evaluated=[
            {"rule": "Rule 1", "outcome": "PASS", "evidence": "EUR-equivalent 12,345 < 50,000."},
            {"rule": "Rule 2", "outcome": "PASS", "evidence": "No sanctions match."},
            {"rule": "Rule 3", "outcome": "PASS", "evidence": "Variance 1.2% within band."},
            {"rule": "Rule 4", "outcome": "PASS", "evidence": "counterparty_risk_score=0.18 < 0.85."},
        ],
        counterparty_id="CP-1002",
        counterparty_name="Globex",
        amount=12345.0,
        currency="USD",
        eur_equivalent=11414.65,
        fx_rate_used=0.9244,
    )
    print(json.dumps(out2, indent=2))

    verdict = verify_audit_chain()
    print(json.dumps(verdict, indent=2))
