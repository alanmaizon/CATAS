---
name: write-audit-log
display_name: Write Audit Log
description: Appends a tamper-evident audit-log entry to logs/audit_trail.jsonl for every transaction decision. Each entry carries a SHA-256 chain hash computed from the previous entry's hash plus this entry's canonical JSON, turning the log into a verifiable hash chain. Includes a companion verify_audit_chain function for replaying the chain and detecting any retro-active edits. Satisfies the "explainable, immutable audit trail" requirement of CJA 2010 §55.
version: 1.1.0
author: CATAS Compliance Team
license: Apache-2.0
language: python
entrypoint: write_audit_log.py
function: write_audit_log
extra_functions:
  - verify_audit_chain
requires_python: ">=3.10"
permissions:
  - filesystem:write
tags:
  - compliance
  - audit
  - immutable
  - hash-chain
---

# Write Audit Log

Every Compliance Agent decision — APPROVE, BLOCK, or HOLD — terminates with a
call to this skill. The log it builds is what an auditor or the Central Bank
of Ireland would read to reconstruct what happened and why.

## When to invoke

- Final step of every transaction loop, regardless of outcome.
- Once per transaction decision. Idempotent retries are not safe: each call
  appends a new entry.

## What it writes

`logs/audit_trail.jsonl` — one JSON object per line, like:

```jsonc
{
  "entry_id": "AUD-13B50435A3D4",
  "timestamp_utc": "2026-05-19T11:45:31+00:00",
  "transaction_id": "TXN-2026-SEED-001",
  "decision": "BLOCK",
  "counterparty": {
    "counterparty_id": "CP-9471",
    "counterparty_name": "BoreasTrade Holdings LLP"
  },
  "amount": {
    "original": 245000.00,
    "currency": "EUR",
    "eur_equivalent": 245000.00,
    "fx_rate_used": 1.0
  },
  "rules_evaluated": [
    {"rule": "Rule 1", "outcome": "SKIP", "evidence": "Rule 2 supersedes."},
    {"rule": "Rule 2", "outcome": "BLOCK",
     "evidence": "counterparty_id=CP-9471 -> SANCT-ENT-00471 (BoreasTrade)."},
    {"rule": "Rule 3", "outcome": "SKIP", "evidence": "Rule 2 supersedes."},
    {"rule": "Rule 4", "outcome": "SKIP", "evidence": "Rule 2 supersedes."}
  ],
  "approver": null,
  "case_ticket_id": "MLRO-ABC123456789",
  "previous_chain_hash": "13309d94...",
  "audit_chain_hash":    "2071854c..."
}
```

## Tamper-evidence

The chain seed is the fixed bytes `b"CATAS-AUDIT-CHAIN-GENESIS-v1"`. Each
entry's hash is:

```
audit_chain_hash = sha256(
    bytes.fromhex(previous_chain_hash)
    + canonical_json(entry_without_chain_hash)
)
```

Canonical JSON uses sorted keys and tight separators so the hash is
reproducible across implementations.

To verify the log later, the companion function `verify_audit_chain(log_path="")`
re-walks the file, recomputes each entry's hash from its predecessor, and
reports the first mismatch (if any). Anyone with the file alone can run it.

## Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `transaction_id` | str | (required) | Bank-feed transaction ID being decided. |
| `decision` | str | (required) | `"APPROVE"` \| `"BLOCK"` \| `"HOLD"`. |
| `rules_evaluated` | list[dict] | (required) | Per-rule outcomes; each dict has `rule`, `outcome`, `evidence`. |
| `counterparty_id` | str | (required) | Counterparty ID at time of decision. |
| `counterparty_name` | str | (required) | Counterparty name. |
| `amount` | float | (required) | Original amount. |
| `currency` | str | (required) | ISO 4217 currency code. |
| `eur_equivalent` | float | `0.0` | EUR-converted amount, if known. |
| `fx_rate_used` | float | `0.0` | FX rate applied. |
| `approver` | str | `""` | Human approver identity. Empty = auto-decision. |
| `case_ticket_id` | str | `""` | Linked MLRO case ID from `trigger_mlro_alert`. |
| `log_dir` | str | `""` | Override log directory. Empty triggers the resolution order. |

## Log-directory resolution

1. `log_dir` arg
2. `CATAS_LOG_DIR` environment variable
3. `./logs` relative to CWD
4. `../logs`, `../../logs`, `../../../logs` relative to this file
5. `./logs` (created on first write)

## Return shape

```jsonc
{
  "ok": true,
  "entry_id": "AUD-13B50435A3D4",
  "audit_chain_hash": "2071854c...",
  "previous_chain_hash": "13309d94...",
  "log_path": "/abs/path/to/logs/audit_trail.jsonl",
  "entry_count_after": 1,
  "error": null
}
```

## Verifying the chain

```python
from skills.write_audit_log.write_audit_log import verify_audit_chain
print(verify_audit_chain())
# -> {"ok": true, "entries_checked": 42, "first_broken_entry": null, "log_path": "..."}
```

## Local smoke-test

```bash
python skills/write_audit_log/write_audit_log.py
```

Appends two demo entries (one BLOCK, one APPROVE), then re-walks the chain
and prints the verification verdict.
