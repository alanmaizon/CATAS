"""
CATAS Skill: trigger_mlro_alert

Fires a P1-URGENT alert to the Money Laundering Reporting Officer (MLRO) when
the Compliance Agent identifies a sanctions match or other high-severity
incident under Internal_AML_Treasury_Policy_Ireland Rule 2.

Delivery channels (controlled by the `channel` arg):
  - "ses"     Amazon SES email. Requires AWS credentials (configured in the
              Lyzr Studio UI), env vars ALERT_SENDER (verified sender) and
              ALERT_RECIPIENT.
  - "webhook" POST JSON to env var ALERT_WEBHOOK_URL (Slack, Teams,
              PagerDuty, AWS Lambda function URL, etc.).
  - "local"   Append to logs/mlro_alerts.jsonl only.
  - "auto"    Try SES, then webhook, then local. Always succeeds because the
              local audit copy is the unconditional fall-back.

The local audit copy is ALWAYS written regardless of remote-channel outcome —
this is the immutable record the auditor sees.

Log-directory resolution order:
  1. CATAS_LOG_DIR environment variable
  2. ./logs relative to CWD
  3. ../logs / ../../logs / ../../../logs relative to this file
  4. ./logs (created on first write)
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCAL_LOG_FILENAME = "mlro_alerts.jsonl"


def trigger_mlro_alert(
    transaction_id: str,
    counterparty_id: str,
    counterparty_name: str,
    matched_rule: str,
    matched_entity_id: str,
    eu_reference: str,
    amount: float,
    currency: str,
    eur_equivalent: float = 0.0,
    evidence: list[str] | None = None,
    priority: str = "P1-URGENT",
    channel: str = "auto",
) -> dict[str, Any]:
    """
    Fire an MLRO alert for a blocked transaction and persist an audit copy.

    Args:
        transaction_id: ID of the transaction being escalated.
        counterparty_id: Counterparty ID at time of block (e.g. "CP-9471").
        counterparty_name: Counterparty name as seen in the bank feed.
        matched_rule: Rule that triggered the alert (e.g. "Rule 2 — Sanctions").
        matched_entity_id: Sanctions-register entity ID (e.g. "SANCT-ENT-00471").
        eu_reference: EU sanctions reference (e.g. "EU.CFSP.2025.0991").
        amount: Original transaction amount.
        currency: Original transaction currency (ISO 4217).
        eur_equivalent: EUR-converted amount (0.0 if not computed).
        evidence: List of supporting evidence strings (rule citations, match
            patterns, fuzzy scores, etc.). Optional.
        priority: Alert priority code. Default "P1-URGENT".
        channel: "auto" | "ses" | "webhook" | "local".

    Returns:
        dict with:
          ok (bool):              true if at least one delivery channel succeeded.
          case_ticket_id (str):   newly-allocated MLRO case ID (UUID4-derived).
          channels_attempted:     list[str].
          channels_succeeded:     list[str].
          timestamp_utc (str):    ISO-8601 timestamp.
          local_log_path (str):   path the local audit copy was appended to.
          error (str|None):       reasons remote channels failed, if any.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    required_fields = {
        "transaction_id": transaction_id,
        "counterparty_id": counterparty_id,
        "counterparty_name": counterparty_name,
        "matched_rule": matched_rule,
        "matched_entity_id": matched_entity_id,
        "eu_reference": eu_reference,
        "currency": currency,
    }
    missing = [k for k, v in required_fields.items() if not (isinstance(v, str) and v.strip())]
    if missing:
        return {
            "ok": False,
            "case_ticket_id": "",
            "channels_attempted": [],
            "channels_succeeded": [],
            "timestamp_utc": timestamp_utc,
            "local_log_path": "",
            "error": f"Missing or empty required field(s): {', '.join(missing)}",
        }

    case_ticket_id = f"MLRO-{uuid.uuid4().hex[:12].upper()}"

    payload = {
        "case_ticket_id": case_ticket_id,
        "priority": priority,
        "timestamp_utc": timestamp_utc,
        "transaction": {
            "transaction_id": transaction_id,
            "counterparty_id": counterparty_id,
            "counterparty_name": counterparty_name,
            "amount": amount,
            "currency": currency,
            "eur_equivalent": eur_equivalent,
        },
        "match": {
            "rule": matched_rule,
            "entity_id": matched_entity_id,
            "eu_reference": eu_reference,
        },
        "evidence": evidence or [],
        "source": "CATAS-Compliance-Agent",
    }

    attempted: list[str] = []
    succeeded: list[str] = []
    errors: list[str] = []

    if channel == "auto":
        channels_to_try = ["ses", "webhook"]
    elif channel in ("ses", "webhook"):
        channels_to_try = [channel]
    elif channel == "local":
        channels_to_try = []
    else:
        return {
            "ok": False,
            "case_ticket_id": case_ticket_id,
            "channels_attempted": [],
            "channels_succeeded": [],
            "timestamp_utc": timestamp_utc,
            "local_log_path": "",
            "error": f"Unknown channel '{channel}' — expected auto|ses|webhook|local.",
        }

    for ch in channels_to_try:
        attempted.append(ch)
        try:
            if ch == "ses":
                _send_via_ses(payload)
            elif ch == "webhook":
                _send_via_webhook(payload)
            succeeded.append(ch)
        except Exception as e:  # noqa: BLE001 — skill must never raise to caller
            errors.append(f"{ch}: {type(e).__name__}: {e}")

    local_path = _append_local_log(payload)
    attempted.append("local")
    succeeded.append("local")

    return {
        "ok": True,
        "case_ticket_id": case_ticket_id,
        "channels_attempted": attempted,
        "channels_succeeded": succeeded,
        "timestamp_utc": timestamp_utc,
        "local_log_path": str(local_path),
        "error": "; ".join(errors) if errors else None,
    }


def _resolve_log_dir() -> Path:
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


def _send_via_ses(payload: dict[str, Any]) -> None:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("boto3 not installed; cannot send via SES") from e

    sender = os.environ.get("ALERT_SENDER")
    recipient = os.environ.get("ALERT_RECIPIENT")
    region = os.environ.get("AWS_REGION", "eu-west-1")
    if not sender or not recipient:
        raise RuntimeError("ALERT_SENDER / ALERT_RECIPIENT env vars not configured.")

    subject = (
        f"[{payload['priority']}] CATAS MLRO Alert — {payload['match']['rule']} — "
        f"{payload['transaction']['counterparty_name']}"
    )
    body = json.dumps(payload, indent=2)

    client = boto3.client("ses", region_name=region)
    client.send_email(
        Source=sender,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )


def _send_via_webhook(payload: dict[str, Any]) -> None:
    import urllib.request

    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        raise RuntimeError("ALERT_WEBHOOK_URL env var not configured.")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"webhook returned HTTP {resp.status}")


def _append_local_log(payload: dict[str, Any]) -> Path:
    log_dir = _resolve_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOCAL_LOG_FILENAME
    with log_path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    return log_path


if __name__ == "__main__":
    out = trigger_mlro_alert(
        transaction_id="TXN-2026-SEED-001",
        counterparty_id="CP-9471",
        counterparty_name="BoreasTrade Holdings LLP",
        matched_rule="Rule 2 — Sanctions Screening and Automatic Block",
        matched_entity_id="SANCT-ENT-00471",
        eu_reference="EU.CFSP.2025.0991",
        amount=245000.00,
        currency="EUR",
        eur_equivalent=245000.00,
        evidence=[
            "Exact match on counterparty_id 'CP-9471' against sanctions register §2.1",
            "Counterparty registered in Cyprus (front company)",
            "Listing reason: Funnelling proceeds linked to dual-use export evasion",
        ],
        channel="auto",
    )
    print(json.dumps(out, indent=2))
