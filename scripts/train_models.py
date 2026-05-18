import os
import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

def train_agent1_anomaly_detector():
    print("Training Agent 1: Isolation Forest (Anomaly Detector)...")
    df = pd.read_csv(os.path.join(DATA_DIR, 'historical_transactions.csv'))
    
    # Feature Engineering
    df['amount_normalized'] = df['amount'] / df['amount'].mean()
    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
    df['counterparty_encode'] = pd.factorize(df['counterparty_name'])[0]
    df['txn_type_encode'] = pd.factorize(df['transaction_type'])[0]
    df['currency_encode'] = pd.factorize(df['currency'])[0]
    
    features = ['amount_normalized', 'hour', 'day_of_week', 'counterparty_encode', 'txn_type_encode', 'currency_encode']
    X = df[features].fillna(0)
    
    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(X)
    
    model_path = os.path.join(MODELS_DIR, 'anomaly_detector.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Saved: {model_path}")

def train_agent2_approval_classifier():
    print("Training Agent 2: Logistic Regression (Approval Classifier)...")
    df = pd.read_csv(os.path.join(DATA_DIR, 'historical_transactions.csv'))
    
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date')
    
    # Feature Engineering
    df['amount_ratio'] = df['amount'] / df['daily_limit']
    df['days_since_last_txn'] = (df['date'] - df['date'].shift(1)).dt.days.fillna(0)
    df['txn_type_encode'] = pd.factorize(df['transaction_type'])[0]
    df['cp_risk_encode'] = df['counterparty_risk'].map({'low': 0, 'medium': 1, 'high': 2})
    df['user_role_encode'] = pd.factorize(df['user_role'])[0]
    
    features = ['amount_ratio', 'days_since_last_txn', 'txn_type_encode', 'cp_risk_encode', 'user_role_encode']
    X = df[features].fillna(0)
    y = df['approved']
    
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X, y)
    
    model_path = os.path.join(MODELS_DIR, 'approval_classifier.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Saved: {model_path}")

def train_agent3_forecast_model():
    print("Training Agent 3: ARIMA (Cash Flow Forecaster)...")
    df = pd.read_csv(os.path.join(DATA_DIR, 'gl_balances_daily.csv'))
    
    # Train a simple model for Entity A / USD as an example
    df_ts = df[(df['entity'] == 'Entity A') & (df['currency'] == 'USD')].copy()
    df_ts['date'] = pd.to_datetime(df_ts['date'])
    df_ts = df_ts.sort_values(by='date').set_index('date')
    
    # Fit ARIMA model
    # Using order (1,1,1) for simplicity
    model = ARIMA(df_ts['balance'], order=(1, 1, 1))
    fitted_model = model.fit()
    
    model_path = os.path.join(MODELS_DIR, 'forecast_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(fitted_model, f)
    print(f"Saved: {model_path}")

if __name__ == "__main__":
    train_agent1_anomaly_detector()
    train_agent2_approval_classifier()
    train_agent3_forecast_model()
    print("All ML models trained and serialized successfully!")
