# CATAS Orchestration

End-to-end runner for the Treasury → Compliance multi-agent pipeline. Loads
the bank-transactions feed, hands each transaction to the Treasury Agent,
then to the Compliance Agent (which evaluates Rules 1–4), and writes the
tamper-evident audit trail.

Two modes — both use the **same CLI**:

| Mode | When | What it does |
|---|---|---|
| **MOCK** (default if no Lyzr creds) | Today, no Lyzr deployment | Deterministic Python implementations of both agents. Calls the three local skills directly. Fills `logs/audit_trail.jsonl` and `logs/mlro_alerts.jsonl`. |
| **LIVE** (auto when Lyzr creds set) | Tomorrow, agents deployed | POSTs to the Lyzr Agent API (`/v3/inference/chat/`) for both agents. The agents call their uploaded skills inside Lyzr; the orchestrator parses the JSON they return. |

## ML scoring layer

In **both** modes, `orchestration/catas_ml.py` scores every transaction with the
three offline-trained models before the agents run:

- **`anomaly_detector.pkl`** (Isolation Forest) — per-transaction `anomaly_score`
  + `anomaly_flag` against a tuned alert threshold.
- **`approval_classifier.pkl`** (Logistic Regression) — `ml_approval_probability`.
- **`forecast_model.pkl`** (30-day cash-balance forecast) — `liquidity_risk_flag`.

The Treasury result carries the anomaly + liquidity signals; the Compliance
agent then runs an **ML-Gate** after Rules 1–4: a would-be `APPROVE` is routed
to `HOLD` when `ml_approval_probability < 0.30` or the transaction is
anomaly-flagged. Sanctions `BLOCK`s skip the gate.

In LIVE mode the scores are computed locally and **injected into the agent
prompts** (a cloud agent cannot read local `.pkl` files). If the ML deps
(`pandas`/`numpy`/`scikit-learn`) are missing, the layer reports "ML models
inactive" and the orchestrator falls back to rule-only scoring.

Models are produced by `scripts/agent{1,2,3}_*.py` — re-run those if you
change the data; they emit the dict-bundle `.pkl` format `catas_ml.py` expects.

## Quick start

```bash
# 1. Install deps (one time — only needed for LIVE mode, but harmless in MOCK)
pip install -r orchestration/requirements.txt

# 2. MOCK mode — works today, end-to-end
python orchestration/run_catas.py --transaction-id TXN-2026-SEED-001
python orchestration/run_catas.py --transaction-id TXN-2026-SEED-002
python orchestration/run_catas.py --transaction-id TXN-2026-SEED-003
python orchestration/run_catas.py --limit 10
python orchestration/run_catas.py                       # all 103 transactions

# 3. LIVE mode — tomorrow, after agents are deployed in Lyzr Studio
cp orchestration/.env.example .env
# fill in LYZR_API_KEY + the two agent IDs
python orchestration/run_catas.py                       # auto-picks live
python orchestration/run_catas.py --mode live           # force live
```

## CLI

```
--mode auto|live|mock     Default 'auto'. Picks live when Lyzr creds are present.
--limit N                 Process only the first N transactions (0 = all).
--transaction-id TXN-...  Process only this transaction.
--verbose / -v            Print per-rule evidence and MLRO/audit IDs.
```

## What a demo run looks like

```
CATAS orchestrator — MOCK mode
================================================================================
  (no Lyzr credentials detected — running deterministic local agents)

[1/2] Loading data snapshot via parse_ledger_data ...
      Bank txns:        103
      GL entries:       77
      Historical rows:  1000
      Currencies:       CAD, EUR, GBP, JPY, USD
      Risk index:       11 counterparties
      Baseline index:   44 (cp, type) groups

[2/2] Orchestrating 3 transaction(s) ...

[Run] mode=mock  session=catas-1747654321  txns=3
  TXN ID                    COUNTERPARTY                        EUR EQ  DECISION  RULE OUTCOMES
  ------------------------------------------------------------------------------------------------
  TXN-2026-SEED-001         BoreasTrade Holdings LLP          EUR    245,000  BLOCK     2=BLOC 1=SKIP 3=SKIP 4=SKIP
  TXN-2026-SEED-002         Volkov Maritime Services AG       EUR     44,395  BLOCK     2=BLOC 1=SKIP 3=SKIP 4=SKIP
  TXN-2026-SEED-003         Wayne Enterprises                 EUR  8,092,875  HOLD      1=HOLD 3=HOLD 4=PASS

================================================================================
Final tally:  APPROVE=0  HOLD=1  BLOCK=2  ERROR=0
Audit trail:  /Users/.../Research/logs/audit_trail.jsonl
MLRO alerts:  /Users/.../Research/logs/mlro_alerts.jsonl
```

That's the same demo sequence the pitch script references: two sanctions
blocks fire MLRO escalations, and the large-Wayne-Enterprises transaction
fires Rule 1 (€8M > €50K) and Rule 3 (huge variance) holds — exactly what
makes the 3-minute pitch concrete.

## Environment variables

| Variable | Mode | Purpose |
|---|---|---|
| `LYZR_API_KEY` | live | Auth key from Lyzr Studio. |
| `LYZR_TREASURY_AGENT_ID` | live | Treasury Agent ID. |
| `LYZR_COMPLIANCE_AGENT_ID` | live | Compliance Agent ID. |
| `LYZR_USER_ID` | live | Session attribution. Defaults to `catas-orchestrator`. |
| `LYZR_BASE_URL` | live | Lyzr API base. Defaults to `https://agent-prod.studio.lyzr.ai`. |
| `ALERT_WEBHOOK_URL` | mock | If set, MLRO alerts POST to this URL (Slack/Teams/PagerDuty). |
| `ALERT_SENDER` / `ALERT_RECIPIENT` / `AWS_REGION` | mock | Enables SES email delivery for MLRO alerts. |
| `CATAS_DATA_DIR` / `CATAS_LOG_DIR` | both | Override default `data/` and `logs/` paths. |

A `.env` file at the repo root is auto-loaded.

## How LIVE mode talks to Lyzr

Single HTTP call per agent invocation:

```http
POST {LYZR_BASE_URL}/v3/inference/chat/
x-api-key: {LYZR_API_KEY}
Content-Type: application/json

{
  "user_id":    "catas-orchestrator",
  "agent_id":   "<treasury or compliance agent id>",
  "session_id": "catas-<unix-ts>",
  "message":    "<structured prompt with the transaction>"
}
```

The agent's `response` is expected to contain a fenced ```` ```json ```` block;
the orchestrator extracts that and dispatches the next step.

> If your Lyzr tenant uses a different inference endpoint (v1, v2, or a
> custom path), edit `call_lyzr_agent()` in `run_catas.py`. It's the only
> place the API surface is referenced.

## Why MOCK mode is worth keeping

- **Demo insurance.** If Lyzr is slow/down at submission, the demo still
  shows the agents reasoning end-to-end.
- **Iteration speed.** Policy-logic changes can be validated in milliseconds
  rather than minutes of round-tripping to remote agents.
- **Audit-chain integrity demo.** The local `logs/audit_trail.jsonl` fills
  up live during the demo; running `verify_audit_chain()` afterwards on stage
  proves the chain holds. That moment lands better when it happens locally.

## Outputs

| File | Mode | Content |
|---|---|---|
| `logs/audit_trail.jsonl` | mock | Hash-chained audit entries — one per decision. |
| `logs/mlro_alerts.jsonl` | mock | MLRO alert outbox (local audit copy of every escalation). |

In LIVE mode the agents write to the Lyzr-side equivalents; local `logs/`
stays empty unless you mix modes.
