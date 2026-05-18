import os
import json
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Configurations
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(DATA_DIR, exist_ok=True)

ENTITIES = ['Entity A', 'Entity B', 'Entity C']
CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD']
COUNTERPARTIES = [
    'Acme Corp', 'Globex', 'Soylent', 'Initech', 'Umbrella Corp',  # Normal
    'Stark Industries', 'Wayne Enterprises', 'Vandelay', 'Massive Dynamic', 'Cyberdyne', # High risk
    'Goliath National Bank' # OFAC listed mock
]
TXN_TYPES = ['wire_payment', 'ach_transfer', 'internal_transfer', 'fee']
USER_ROLES = ['treasury_analyst', 'treasury_manager', 'cfo']
RISK_LEVELS = ['low', 'medium', 'high']

def generate_historical_transactions(n=1000):
    print(f"Generating {n} historical transactions...")
    data = []
    start_date = datetime(2025, 1, 1)
    
    for i in range(n):
        date = start_date + timedelta(days=random.randint(0, 365), hours=random.randint(8, 18))
        counterparty = random.choice(COUNTERPARTIES)
        cp_risk = 'high' if counterparty in ['Stark Industries', 'Wayne Enterprises', 'Vandelay', 'Massive Dynamic', 'Cyberdyne'] else 'low'
        if counterparty == 'Goliath National Bank': cp_risk = 'high'
        
        # Inject anomalies (~10%)
        is_anomaly = random.random() < 0.1
        if is_anomaly:
            amount = round(random.uniform(500000, 2000000), 2)
            hour = random.choice([2, 3, 4, 22, 23]) # unusual hours
            date = date.replace(hour=hour)
        else:
            amount = round(random.uniform(100, 50000), 2)
            
        txn_type = random.choice(TXN_TYPES)
        daily_limit = 100000 if cp_risk == 'low' else 25000
        
        # Simulate approval logic
        approved = 1
        if cp_risk == 'high' or amount > daily_limit or is_anomaly:
             approved = 0 if random.random() < 0.8 else 1 # mostly rejected/escalated
            
        data.append({
            'transaction_id': f"HIST-{i:05d}",
            'timestamp': date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'date': date.strftime("%Y-%m-%d"),
            'amount': amount,
            'currency': random.choice(CURRENCIES),
            'counterparty_name': counterparty,
            'counterparty_id': f"CP-{abs(hash(counterparty)) % 10000:04d}",
            'transaction_type': txn_type,
            'counterparty_risk': cp_risk,
            'daily_limit': daily_limit,
            'user_role': random.choice(USER_ROLES),
            'approved': approved,
            'is_anomaly': int(is_anomaly)
        })
        
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(DATA_DIR, 'historical_transactions.csv'), index=False)
    print("Saved historical_transactions.csv")

def generate_gl_flows():
    print("Generating 12-month GL daily closing balances...")
    data = []
    start_date = datetime(2025, 1, 1)
    
    for day in range(365):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d")
        
        for entity in ENTITIES:
            for currency in CURRENCIES:
                # Add some seasonality and random walk
                base = 1000000 + (day * 1000)
                seasonality = np.sin(day / 30.0) * 200000
                noise = random.uniform(-50000, 50000)
                balance = round(base + seasonality + noise, 2)
                
                data.append({
                    'date': date_str,
                    'entity': entity,
                    'currency': currency,
                    'account_type': 'payable',
                    'balance': max(0, balance)
                })
                
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(DATA_DIR, 'gl_balances_daily.csv'), index=False)
    print("Saved gl_balances_daily.csv")

def generate_hackathon_live_data():
    print("Generating 100 live transactions and GL entries for demo...")
    transactions = []
    gl_entries = []
    
    demo_date = datetime(2026, 5, 19, 10, 0, 0)
    
    for i in range(100):
        amount = round(random.uniform(500, 75000), 2)
        counterparty = random.choice(COUNTERPARTIES)
        
        # Inject 5 explicit anomalies to be caught by demo
        if i < 5:
            amount = round(random.uniform(1000000, 5000000), 2) # High amount anomaly
        
        txn = {
            "transaction_id": f"TXN-2026-{i:04d}",
            "bank_date": demo_date.strftime("%Y-%m-%d"),
            "timestamp": demo_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "amount": amount,
            "currency": random.choice(CURRENCIES),
            "counterparty_name": counterparty,
            "counterparty_id": f"CP-{abs(hash(counterparty)) % 10000:04d}",
            "transaction_type": random.choice(TXN_TYPES),
            "reference": f"INV-{random.randint(1000,9999)}",
            "source_system": "bank_feed"
        }
        transactions.append(txn)
        
        # Create GL matches for 80% of transactions
        if random.random() < 0.8:
            gl_entries.append({
                "gl_id": f"GL-2026-{i:04d}",
                "gl_date": txn['bank_date'],
                "amount": txn['amount'], # exact match
                "currency": txn['currency'],
                "counterparty_name": txn['counterparty_name'],
                "account_code": f"4000-{random.randint(10,99)}",
                "reference": txn['reference']
            })
            
    with open(os.path.join(DATA_DIR, 'bank_transactions_input.json'), 'w') as f:
        json.dump(transactions, f, indent=2)
    with open(os.path.join(DATA_DIR, 'gl_ledger.json'), 'w') as f:
        json.dump(gl_entries, f, indent=2)
        
    print("Saved bank_transactions_input.json and gl_ledger.json")

if __name__ == "__main__":
    generate_historical_transactions()
    generate_gl_flows()
    generate_hackathon_live_data()
    print("All synthetic data generated successfully!")
