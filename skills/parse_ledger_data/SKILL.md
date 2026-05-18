---
name: parse-ledger-data
display_name: Parse Ledger Data
description: Loads the four canonical CATAS financial files (bank feed, GL ledger, historical transactions, FX rates) and returns a pre-indexed snapshot — transactions enriched with EUR-equivalent amounts, a counterparty risk-score index, a rolling-window baseline index for Rule 3 variance checks, and naive reconciliation candidates. Call this once at the start of an incident loop instead of pasting raw data into the LLM context.
version: 1.1.0
author: CATAS Compliance Team
license: Apache-2.0
language: python
entrypoint: parse_ledger_data.py
function: parse_ledger_data
requires_python: ">=3.10"
permissions:
  - filesystem:read
tags:
  - treasury
  - reconciliation
  - data-loader
  - fx-normalisation
---

# Parse Ledger Data

The Treasury Agent's first call in every incident loop. Replaces "the LLM tries to
read raw CSV/JSON" with "the LLM reads one structured dict that already has every
derived index it needs."

## When to invoke

- Beginning of any reconciliation pass.
- Beginning of any compliance review (the snapshot includes everything the
  Compliance Agent needs to evaluate Rules 1–4).

## What it does

1. Loads `bank_transactions_input_v2.json` and `gl_ledger_v2.json` as lists.
2. Loads `fx_rates.csv` and converts every bank-feed and GL row to its
   EUR-equivalent using the FX rate dated on the transaction's own date
   (or nearest prior business day).
3. Scans `historical_transactions_v2.csv` once and builds two indices:
   - **Risk index** — latest `counterparty_risk_score` per `counterparty_id`,
     used directly by Rule 4.
   - **Baseline index** — rolling-window mean and stdev of EUR-equivalent
     amounts per `(counterparty_id, transaction_type)`, used by Rule 3.
     Window defaults to 90 days (policy-aligned) and auto-widens to 365 or
     730 if the 90-day window has fewer than 5 rows. Each baseline entry
     reports `window_days_used` so the agent can communicate uncertainty.
4. Pre-computes naive reconciliation candidates: bank transactions whose
   `reference` field matches a GL entry's `reference`, with a `match_basis`
   list noting which secondary fields also matched (amount, currency, name).

## Parameters

| Name | Type | Default | Description |
|---|---|---|---|
| `bank_feed_filename` | str | `bank_transactions_input_v2.json` | Bank-feed JSON file inside the data dir. |
| `gl_ledger_filename` | str | `gl_ledger_v2.json` | GL JSON file inside the data dir. |
| `historical_filename` | str | `historical_transactions_v2.csv` | Historical-transactions CSV. |
| `fx_rates_filename` | str | `fx_rates.csv` | FX-rates CSV (cols: `date, currency, rate_to_eur, source`). |
| `data_dir` | str | `""` | Override the data directory. Empty triggers the resolution order below. |
| `baseline_window_days` | int | `90` | Primary lookback window for the Rule 3 baseline. |
| `baseline_fallback_windows` | list[int] | `[365, 730]` | Widened windows tried if the primary window has < 5 rows. Pass `[]` to disable. |

## Data-directory resolution

Tried in order until a directory exists:

1. `data_dir` arg
2. `CATAS_DATA_DIR` environment variable
3. `./data` relative to CWD
4. `../data` relative to this skill file
5. `../../data` relative to this skill file (repo layout)

## Returned structure

```jsonc
{
  "bank_transactions": [
    {
      "transaction_id": "TXN-2026-0000",
      "amount": 954151.35,
      "currency": "CAD",
      "counterparty_id": "CP-1004",
      "counterparty_name": "Initech",
      "transaction_type": "internal_transfer",
      "reference": "INV-7468",
      "bank_date": "2026-05-19",
      "eur_equivalent": 648341.86,      // <-- added by this skill
      "fx_rate_used": 0.6796            // <-- added by this skill
    }
    /* ... */
  ],
  "gl_entries": [ /* same shape, plus eur_equivalent */ ],
  "fx_rates": {
    "2026-05-19": {"EUR": 1.0, "USD": 0.9244, "GBP": 1.1775, "JPY": 0.006094, "CAD": 0.6796}
    /* ... */
  },
  "counterparty_risk_index": {
    "CP-1011": 0.88,    // Rule 4 fires for any txn with this counterparty
    "CP-1002": 0.10,
    /* ... */
  },
  "counterparty_baseline_index": {
    "CP-1004|internal_transfer": {
      "mean_eur": 412300.50,
      "stdev_eur": 88720.41,
      "count": 12,
      "window_days_used": 365
    }
    /* ... */
  },
  "candidate_reconciliation_matches": [
    {"bank_transaction_id": "TXN-2026-0000", "gl_id": "GL-2026-0000",
     "match_basis": ["reference", "amount", "currency", "counterparty_name"]}
    /* ... */
  ],
  "summary": {
    "bank_txn_count": 103,
    "gl_entry_count": 77,
    "historical_count": 1000,
    "currencies_seen": ["CAD", "EUR", "GBP", "JPY", "USD"],
    "anchor_date": "2026-05-19",
    "baseline_window_days_default": 90
  }
}
```

## Example agent invocation

```python
snapshot = parse_ledger_data()

# Rule 4 — quick check
for txn in snapshot["bank_transactions"]:
    risk = snapshot["counterparty_risk_index"].get(txn["counterparty_id"], 0.0)
    if risk >= 0.85:
        ...  # hold for EDD

# Rule 3 — baseline lookup
key = f"{txn['counterparty_id']}|{txn['transaction_type']}"
baseline = snapshot["counterparty_baseline_index"].get(key)
if baseline and baseline["count"] >= 5:
    variance_pct = abs(txn["eur_equivalent"] - baseline["mean_eur"]) / baseline["mean_eur"] * 100
    ...
```

## Local smoke-test

From the repo root:

```bash
python skills/parse_ledger_data/parse_ledger_data.py
```

Prints a one-screen summary with counts, currencies, high-risk counterparties,
and a sample of baseline-index entries.
