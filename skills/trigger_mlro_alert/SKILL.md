---
name: trigger-mlro-alert
display_name: Trigger MLRO Alert
description: Fires a P1-URGENT alert to the Money Laundering Reporting Officer when the Compliance Agent identifies a sanctions match or other high-severity incident. Supports AWS SES email, HTTP webhook (Slack/Teams/PagerDuty/Lambda), and an unconditional local audit copy. Returns a case-ticket ID for downstream tracking. The local audit copy is always written — remote channels are best-effort.
version: 1.2.0
author: CATAS Compliance Team
license: Apache-2.0
language: python
entrypoint: trigger_mlro_alert.py
function: trigger_mlro_alert
requires_python: ">=3.10"
permissions:
  - filesystem:write
  - network:egress
  - aws:ses:SendEmail
tags:
  - compliance
  - alerting
  - mlro
  - aws-ses
---

# Trigger MLRO Alert

The Compliance Agent's escalation tool. When Rule 2 (or any other rule the
agent classes as P1) fires, the agent calls this skill to:

1. Validate required parameters and allocate an MLRO case-ticket ID
   (UUID-derived).
2. Send the structured alert via the configured remote channel.
3. Append an unconditional local audit copy to `logs/mlro_alerts.jsonl`.

**Scope of the "no free-text" rule:** For MLRO escalations specifically, the
agent never emits free-text alerts — it always invokes this skill so the
alert is structured, auditable, and replayable. Other agent outputs
(reconciliation summaries, status updates, non-escalation messages) are
unaffected.

## When to invoke

Invoke for **any** of the following — these are the only P1-URGENT cases:

- **Rule 2 sanctions match** — any amount, any direction, any currency.
- **Rule 4 with `counterparty_risk_score ≥ 0.95`** — auto-escalation band.
- **Rule 4 (0.85 ≤ score < 0.95) firing on the same transaction as Rule 1
  (> €50,000 EUR-equivalent)** — combined risk exceeds the EDD-only
  threshold.

Do NOT invoke for: Rule 1 alone, Rule 3 alone, Rule 4 in the 0.50–0.85 soft-flag
band, or any "PASS" outcome. Those use `write_audit_log` only.

## Delivery channels

| Channel | Behaviour |
|---|---|
| `auto` (default) | Try SES, then webhook, then local. Always succeeds — the local audit copy is the unconditional fall-back even if every remote channel fails. |
| `ses` | AWS SES email only. Fails if boto3 / AWS creds / env vars missing. Local copy still written. |
| `webhook` | HTTP POST only. Fails if `ALERT_WEBHOOK_URL` missing. Local copy still written. |
| `local` | Local audit copy only. Skip remote channels. |

Any other value passed as `channel` causes an **immediate** return with
`ok=false`, `case_ticket_id=""`, no channels attempted, and `error`:
`"Unknown channel '<value>' — expected auto|ses|webhook|local."` No alert
is sent and no local copy is written.

## What happens when every remote channel fails

The local audit copy is the unconditional fall-back. Even if SES and the
webhook both fail (or are unconfigured), the call returns `ok=true` with
`channels_succeeded: ["local"]` and a populated `error` field naming every
remote failure. The case-ticket ID, payload, and timestamp are persisted to
`logs/mlro_alerts.jsonl` regardless. Recovery path: an operator (or a
scheduled cron) replays unsent alerts from the local log to a remote channel
once connectivity is restored.

## Environment variables

| Variable | Purpose | Required for channel |
|---|---|---|
| `AWS_REGION` | SES region (default `eu-west-1`). | ses |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | Configured via Lyzr Studio UI as a managed credential. | ses |
| `ALERT_SENDER` | Verified SES sender address. | ses |
| `ALERT_RECIPIENT` | MLRO email address. | ses |
| `ALERT_WEBHOOK_URL` | Webhook endpoint (Slack/Teams/PagerDuty/Lambda function URL). | webhook |
| `CATAS_LOG_DIR` | Override default `./logs/` directory. | local audit copy (any channel) |

## Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `transaction_id` | str | (required) | Bank-feed transaction ID being escalated. |
| `counterparty_id` | str | (required) | Counterparty ID at time of block (`CP-xxxx`). |
| `counterparty_name` | str | (required) | Counterparty name as observed. |
| `matched_rule` | str | (required) | Rule that triggered the alert (free-text or rule citation). |
| `matched_entity_id` | str | (required) | Sanctions-register entity ID (e.g. `SANCT-ENT-00471`). |
| `eu_reference` | str | (required) | EU sanctions reference (e.g. `EU.CFSP.2025.0991`). |
| `amount` | float | (required) | Original transaction amount. |
| `currency` | str | (required) | Original ISO 4217 currency code. |
| `eur_equivalent` | float | `0.0` | EUR-converted amount, if known. |
| `evidence` | list[str] | `None` | Supporting-evidence strings the agent cites. |
| `priority` | str | `"P1-URGENT"` | Alert priority code. |
| `channel` | str | `"auto"` | `auto` \| `ses` \| `webhook` \| `local`. |

**Required-field validation:** Every required string parameter is checked
for empty/whitespace content **before** the case-ticket ID is allocated.
If any required field is missing or empty, the skill returns immediately:

```jsonc
{
  "ok": false,
  "case_ticket_id": "",
  "channels_attempted": [],
  "channels_succeeded": [],
  "timestamp_utc": "...",
  "local_log_path": "",
  "error": "Missing or empty required field(s): transaction_id, counterparty_id"
}
```

No remote alert is attempted and no local copy is written when validation
fails.

## Return shape (success)

```jsonc
{
  "ok": true,
  "case_ticket_id": "MLRO-A1B2C3D4E5F6",
  "channels_attempted": ["ses", "webhook", "local"],
  "channels_succeeded": ["local"],
  "timestamp_utc": "2026-05-19T11:45:31+00:00",
  "local_log_path": "/path/to/logs/mlro_alerts.jsonl",
  "error": "ses: RuntimeError: ALERT_SENDER not configured; webhook: RuntimeError: ALERT_WEBHOOK_URL not configured"
}
```

The `case_ticket_id` is the value the agent passes to `write_audit_log` as
`case_ticket_id` so the audit entry and the MLRO case are linked.

## Dependencies

Optional: `boto3>=1.34` if you want SES delivery. The webhook and local
channels need no extra packages — only Python's standard library.

## Local smoke-test

```bash
python skills/trigger_mlro_alert/trigger_mlro_alert.py
```

Without AWS / webhook env vars configured, returns `ok=true`, channel
`["local"]` succeeded, and writes one entry to `logs/mlro_alerts.jsonl`.
