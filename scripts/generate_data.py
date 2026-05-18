"""
generate_data.py  --  REALISTIC synthetic data generator for CATAS (v2)
=======================================================================

WHY THIS FILE EXISTS
--------------------
The original `scripts/generate_data.py` produces data where the labels are a
*deterministic, perfectly-separable* function of one or two raw features:

    normal  transactions: amount in [100, 50_000]   , hour in 8..18
    anomaly transactions: amount in [500_000, 2_000_000], hour in {2,3,4,22,23}

There is a ~$458k gap between the two amount ranges and the hour sets are
disjoint. As a result *any* classifier scores a perfect F1 = 1.0 -- even a
depth-1 decision stump on `amount` alone. That is not a good model; it is a
broken dataset. A model trained on it has learned the generator's hard-coded
`if` statement, not a generalisable notion of "anomaly", and it will collapse
on real bank data where large legitimate transfers and small fraud overlap.

WHAT THIS GENERATOR DOES DIFFERENTLY
------------------------------------
1. Reproducible: every random source is seeded.
2. Stable counterparty IDs (no per-process `hash()` randomisation).
3. Each counterparty has a *typical amount scale*. Anomalies are spikes
   RELATIVE to that scale, so a big counterparty's normal payment can exceed
   a small counterparty's anomaly  --> the amount distributions OVERLAP.
4. Hours overlap: ~15% of normal txns are off-hours, ~45% of anomalies happen
   during business hours.
5. `approved` is drawn from a logistic (sigmoid) model with genuine noise, not
   a hard rule, so it is learnable but NOT perfectly separable.
6. `counterparty_risk` is a lossy 3-bucket proxy of an underlying continuous
   risk score -- the bucket alone cannot perfectly predict the label.

Output (written next to the originals, with a _v2 suffix so nothing is
overwritten):
    data/historical_transactions_v2.csv
    data/gl_balances_daily_v2.csv
    data/bank_transactions_input_v2.json
    data/gl_ledger_v2.json
"""

import os
import json
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

ENTITIES = ['Entity A', 'Entity B', 'Entity C']
CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD']
TXN_TYPES = ['wire_payment', 'ach_transfer', 'internal_transfer', 'fee']
USER_ROLES = ['treasury_analyst', 'treasury_manager', 'cfo']

# Each counterparty: stable id, an underlying CONTINUOUS risk score in [0,1],
# and a typical transaction "scale" (median amount in its home currency units).
COUNTERPARTIES = {
    'Acme Corp':             dict(id='CP-1001', risk=0.05, scale=12_000),
    'Globex':                dict(id='CP-1002', risk=0.10, scale=22_000),
    'Soylent':               dict(id='CP-1003', risk=0.08, scale=9_000),
    'Initech':               dict(id='CP-1004', risk=0.12, scale=31_000),
    'Umbrella Corp':         dict(id='CP-1005', risk=0.18, scale=15_000),
    'Stark Industries':      dict(id='CP-1006', risk=0.42, scale=48_000),
    'Wayne Enterprises':     dict(id='CP-1007', risk=0.55, scale=27_000),
    'Vandelay':              dict(id='CP-1008', risk=0.60, scale=8_000),
    'Massive Dynamic':       dict(id='CP-1009', risk=0.48, scale=53_000),
    'Cyberdyne':             dict(id='CP-1010', risk=0.65, scale=19_000),
    'Goliath National Bank': dict(id='CP-1011', risk=0.88, scale=40_000),  # OFAC mock
}

OFF_HOURS = [0, 1, 2, 3, 4, 5, 6, 7, 19, 20, 21, 22, 23]


def _risk_bucket(risk):
    """Lossy 3-bucket proxy of the continuous risk score."""
    if risk >= 0.40:
        return 'high'
    if risk >= 0.15:
        return 'medium'
    return 'low'


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate_historical_transactions(n=1000):
    print(f"Generating {n} realistic historical transactions...")
    rows = []
    start_date = datetime(2025, 1, 1)
    names = list(COUNTERPARTIES.keys())

    for i in range(n):
        name = random.choice(names)
        cp = COUNTERPARTIES[name]
        risk = cp['risk']
        scale = cp['scale']

        # Anomaly probability is mostly the base rate but slightly higher for
        # risky counterparties -- still ~10% overall.
        is_anomaly = int(random.random() < (0.07 + 0.10 * risk))

        # ---- amount: OVERLAPPING distributions ---------------------------
        # Normal: lognormal around the counterparty scale (heavy right tail).
        # Anomaly: a 5x-60x multiplicative spike on the same scale.
        # A big counterparty's normal tail can therefore exceed a small
        # counterparty's anomaly -> amount alone CANNOT separate the classes.
        if is_anomaly:
            amount = scale * np.random.uniform(5, 60) * np.random.lognormal(0, 0.35)
        else:
            amount = scale * np.random.lognormal(0, 0.65)
        amount = round(float(amount), 2)

        # ---- hour: OVERLAPPING ------------------------------------------
        if is_anomaly:
            hour = random.choice(OFF_HOURS) if random.random() < 0.55 \
                else random.randint(8, 18)
        else:
            hour = random.randint(8, 18) if random.random() < 0.85 \
                else random.choice(OFF_HOURS)

        day_offset = random.randint(0, 364)
        date = start_date + timedelta(days=day_offset)
        date = date.replace(hour=hour, minute=random.choice([0, 15, 30, 45]))

        txn_type = random.choice(TXN_TYPES)
        risk_bucket = _risk_bucket(risk)
        daily_limit = 100_000 if risk_bucket == 'low' else 25_000
        user_role = random.choice(USER_ROLES)
        amount_ratio = amount / daily_limit

        # ---- approved: probabilistic logistic model, NOT a hard rule -----
        logit = (
            1.6                                   # base: most txns approved
            - 3.0 * risk                          # risky counterparty
            - 1.2 * np.log1p(amount_ratio)        # over the limit
            - 1.1 * is_anomaly                    # anomalous pattern
            + 0.35 * (user_role == 'cfo')         # CFO has more authority
            + np.random.normal(0, 0.45)           # irreducible human noise
        )
        approved = int(random.random() < _sigmoid(logit))

        rows.append({
            'transaction_id': f"HIST-{i:05d}",
            'timestamp': date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'date': date.strftime("%Y-%m-%d"),
            'amount': amount,
            'currency': random.choice(CURRENCIES),
            'counterparty_name': name,
            'counterparty_id': cp['id'],
            'transaction_type': txn_type,
            'counterparty_risk': risk_bucket,
            'counterparty_risk_score': round(risk, 3),  # the true continuous score
            'daily_limit': daily_limit,
            'user_role': user_role,
            'approved': approved,
            'is_anomaly': is_anomaly,
        })

    df = pd.DataFrame(rows)
    out = os.path.join(DATA_DIR, 'historical_transactions_v2.csv')
    df.to_csv(out, index=False)
    print(f"  Saved {out}")
    print(f"  anomaly rate = {df['is_anomaly'].mean():.3f} | "
          f"approved rate = {df['approved'].mean():.3f}")
    # Sanity check: confirm the amount ranges now OVERLAP.
    norm_max = df.loc[df.is_anomaly == 0, 'amount'].max()
    anom_min = df.loc[df.is_anomaly == 1, 'amount'].min()
    overlap = "OVERLAP (good)" if anom_min < norm_max else "DISJOINT (bad!)"
    print(f"  normal max={norm_max:,.0f}  anomaly min={anom_min:,.0f}  -> {overlap}")
    return df


def generate_gl_flows():
    print("Generating 12-month GL daily closing balances (weekly seasonality)...")
    rows = []
    start_date = datetime(2025, 1, 1)

    for day in range(365):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d")
        for entity in ENTITIES:
            for currency in CURRENCIES:
                trend = 1_000_000 + day * 800
                weekly = np.sin(2 * np.pi * day / 7.0) * 60_000      # period = 7d
                monthly = np.sin(2 * np.pi * day / 30.0) * 150_000   # period = 30d
                noise = np.random.normal(0, 40_000)
                # Occasional large outflow spikes (real cash books have these).
                spike = -np.random.uniform(150_000, 350_000) if random.random() < 0.04 else 0
                balance = max(0.0, trend + weekly + monthly + noise + spike)
                rows.append({
                    'date': date_str,
                    'entity': entity,
                    'currency': currency,
                    'account_type': 'payable',
                    'balance': round(balance, 2),
                })

    df = pd.DataFrame(rows)
    out = os.path.join(DATA_DIR, 'gl_balances_daily_v2.csv')
    df.to_csv(out, index=False)
    print(f"  Saved {out}")
    return df


def generate_hackathon_live_data(n=100):
    print(f"Generating {n} live demo transactions + GL ledger...")
    transactions, gl_entries = [], []
    demo_date = datetime(2026, 5, 19, 10, 0, 0)
    names = list(COUNTERPARTIES.keys())

    for i in range(n):
        name = random.choice(names)
        cp = COUNTERPARTIES[name]
        # 5 explicit anomalies up front for the demo, rest realistic.
        is_anomaly = i < 5
        if is_anomaly:
            amount = cp['scale'] * np.random.uniform(8, 50)
        else:
            amount = cp['scale'] * np.random.lognormal(0, 0.65)
        amount = round(float(amount), 2)

        txn = {
            "transaction_id": f"TXN-2026-{i:04d}",
            "bank_date": demo_date.strftime("%Y-%m-%d"),
            "timestamp": demo_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "amount": amount,
            "currency": random.choice(CURRENCIES),
            "counterparty_name": name,
            "counterparty_id": cp['id'],
            "transaction_type": random.choice(TXN_TYPES),
            "reference": f"INV-{random.randint(1000, 9999)}",
            "source_system": "bank_feed",
        }
        transactions.append(txn)

        if random.random() < 0.8:  # 80% have a matching GL entry
            gl_entries.append({
                "gl_id": f"GL-2026-{i:04d}",
                "gl_date": txn['bank_date'],
                "amount": txn['amount'],
                "currency": txn['currency'],
                "counterparty_name": txn['counterparty_name'],
                "account_code": f"4000-{random.randint(10, 99)}",
                "reference": txn['reference'],
            })

    with open(os.path.join(DATA_DIR, 'bank_transactions_input_v2.json'), 'w') as f:
        json.dump(transactions, f, indent=2)
    with open(os.path.join(DATA_DIR, 'gl_ledger_v2.json'), 'w') as f:
        json.dump(gl_entries, f, indent=2)
    print("  Saved bank_transactions_input_v2.json and gl_ledger_v2.json")


if __name__ == "__main__":
    generate_historical_transactions()
    generate_gl_flows()
    generate_hackathon_live_data()
    print("Done. Realistic synthetic data generated with _v2 suffix.")
