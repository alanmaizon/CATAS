# CATAS Skills — Action Layer

Three Python skills the CATAS agents register as tools in Lyzr Studio. Each
skill lives in its own subdirectory with a `SKILL.md` manifest at the root,
ready to be zipped and uploaded.

| Skill | Used by | One-line purpose |
|---|---|---|
| [parse_ledger_data/](parse_ledger_data/) | Treasury Agent | Load + pre-index the canonical financial files (no raw JSON/CSV in LLM context). |
| [trigger_mlro_alert/](trigger_mlro_alert/) | Compliance Agent | Fire a P1-URGENT alert (SES email, webhook, or local audit copy) on a sanctions block. |
| [write_audit_log/](write_audit_log/) | Both agents | Append a tamper-evident audit entry (SHA-256 hash chain) to `logs/audit_trail.jsonl`. |

## Folder layout

```
skills/
├── README.md                       (this file)
├── package.sh                      builds Lyzr-compatible ZIPs
├── parse_ledger_data/
│   ├── SKILL.md                    manifest (Lyzr reads this)
│   └── parse_ledger_data.py
├── trigger_mlro_alert/
│   ├── SKILL.md
│   ├── trigger_mlro_alert.py
│   └── requirements.txt            optional: boto3 for SES delivery
└── write_audit_log/
    ├── SKILL.md
    └── write_audit_log.py
```

## Architectural fit

```
                       ┌──────────────────┐
   bank feed ─────────▶│ parse_ledger_    │──▶ structured snapshot
   GL ledger ─────────▶│ data             │    (no raw rows in LLM ctx)
   historical ────────▶│                  │
   fx_rates ──────────▶│                  │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Treasury Agent   │
                       │  (reconciles)    │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐                ┌──────────────────────┐
                       │ Compliance Agent │───on block────▶│ trigger_mlro_alert   │
                       │  (Rules 1–4)     │                │  (SES / webhook /    │
                       │  + RAG over      │                │   local audit copy)  │
                       │  compliance/*.md │                └──────────────────────┘
                       └──────────────────┘                          │
                                │                                    ▼
                                │                          ┌──────────────────────┐
                                └─────on any decision─────▶│ write_audit_log      │
                                                           │  (SHA-256 hash chain,│
                                                           │   5-yr retention per │
                                                           │   CJA 2010 §55)      │
                                                           └──────────────────────┘
```

## Build the ZIPs

```bash
./skills/package.sh                    # all three
./skills/package.sh parse_ledger_data  # just one
```

Outputs land in `skills/_dist/`. Each ZIP contains `SKILL.md` plus the Python
module(s) and (where present) `requirements.txt`.

## Upload to Lyzr Studio

For each ZIP:

1. **Studio → Agent → Skills → Add Skill → Upload ZIP**.
2. Select `skills/_dist/<skill_name>.zip`.
3. Lyzr reads `SKILL.md` (YAML frontmatter) for the skill's `name`,
   `description`, `function` entrypoint, and tags. The body of `SKILL.md`
   serves as the in-Studio documentation pane.
4. Attach the skill to the correct agent:
   - `parse_ledger_data` → **Treasury Agent**.
   - `trigger_mlro_alert` → **Compliance Agent**.
   - `write_audit_log` → both agents (called at end of each transaction loop).

## Environment variables (set in Lyzr Studio)

| Variable | Used by | Purpose |
|---|---|---|
| `CATAS_DATA_DIR` | `parse_ledger_data` | Override data directory. Defaults search `./data` then `../data` etc. |
| `CATAS_LOG_DIR` | `trigger_mlro_alert`, `write_audit_log` | Override `./logs/` directory. |
| `AWS_REGION` | `trigger_mlro_alert` | SES region. Default `eu-west-1`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | `trigger_mlro_alert` | Configure as a managed credential in Studio. |
| `ALERT_SENDER` | `trigger_mlro_alert` | Verified SES sender address. |
| `ALERT_RECIPIENT` | `trigger_mlro_alert` | MLRO email address. |
| `ALERT_WEBHOOK_URL` | `trigger_mlro_alert` | Slack / Teams / PagerDuty / Lambda URL. |

**AWS credentials are added in the Lyzr Studio UI as a managed credential
bound to the agent — never committed to this repo.**

## Local smoke-tests

From the repo root, each skill is runnable standalone:

```bash
python skills/parse_ledger_data/parse_ledger_data.py
python skills/trigger_mlro_alert/trigger_mlro_alert.py
python skills/write_audit_log/write_audit_log.py
```

- `parse_ledger_data` — prints counts, currencies, high-risk counterparties,
  and a sample of baseline-index entries.
- `trigger_mlro_alert` — exercises the auto channel; falls back to the local
  audit copy because SES / webhook env vars aren't set. Returns `ok=true`.
- `write_audit_log` — appends two demo entries, then re-walks the chain and
  prints the verification verdict.

## Audit-chain integrity

`write_audit_log` ships a companion function `verify_audit_chain()` that
re-walks the log and reports the first hash mismatch (if any). Use it:

- During the demo, to prove the log is tamper-evident.
- In a scheduled CI job, to detect unauthorised edits.
- As part of an external auditor handover.

The chain seed (genesis hash) is fixed at
`sha256(b"CATAS-AUDIT-CHAIN-GENESIS-v1")`, so any third party can
independently verify the chain from `logs/audit_trail.jsonl` alone.
