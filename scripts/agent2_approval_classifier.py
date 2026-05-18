"""
agent2_approval_classifier.py  --  Agent 2: Approval / escalation classifier
=============================================================================

PROBLEM WITH THE ORIGINAL (`scripts/train_models.py :: train_agent2...`)
-------------------------------------------------------------------------
1. NEAR-DETERMINISTIC LABEL. The generator sets:
       approved = 0  if (cp_risk=='high' OR amount>limit OR is_anomaly)
                       with only 20% noise, else 1
   The classifier's features include `amount_ratio` (= amount/limit) and
   `cp_risk_encode`. So the label is essentially `features` fed straight
   back in. The model recovers the generator rule, not a learned pattern.
2. NO EVALUATION. `.fit()` on all rows, then pickled. No train/test split,
   no ROC-AUC, no confusion matrix -- generalisation is never measured.
3. UNSCALED FEATURES FOR LOGISTIC REGRESSION. `amount_ratio` (0..50+) and
   `cp_risk_encode` (0..2) live on wildly different scales. Without
   standardisation the L2 penalty is applied unfairly and `max_iter`
   convergence is fragile.
4. BROKEN FEATURE: `days_since_last_txn`. It is computed as the gap between
   globally-sorted rows -- i.e. the time between two ARBITRARY transactions
   from different counterparties. It carries no signal. The intended
   feature is the gap since this COUNTERPARTY's previous transaction.
5. LOSSY ENCODING. `pd.factorize(user_role)` invents an ordinal ranking
   over unordered roles; one-hot is correct.

WHAT THIS FILE FIXES
--------------------
* Trains on realistic `_v2` data: `approved` is drawn from a noisy logistic
  model, so it is learnable but NOT perfectly separable.
* Proper sklearn Pipeline: StandardScaler (numeric) + OneHotEncoder
  (categorical) + LogisticRegression -- no leakage, scaled correctly.
* `days_since_last_txn` computed PER COUNTERPARTY (the real signal).
* Stratified train/test split + 5-fold cross-validated ROC-AUC.
* Reports ROC-AUC, confusion matrix, classification report, and the
  learned coefficients (explainability -- Agent 2's whole job).

Run:  python agent2_approval_classifier.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, '..', 'data')
MODELS_DIR = os.path.join(HERE, '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, 'historical_transactions_v2.csv')
if not os.path.exists(DATA_FILE):
    DATA_FILE = os.path.join(DATA_DIR, 'historical_transactions.csv')

NUMERIC = ['amount_ratio', 'log_amount', 'days_since_last_txn']
CATEGORICAL = ['transaction_type', 'counterparty_risk', 'user_role']


def build_features(df):
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['amount_ratio'] = df['amount'] / df['daily_limit']
    df['log_amount'] = np.log1p(df['amount'])

    # FIX: gap since the PREVIOUS transaction of the SAME counterparty.
    df = df.sort_values(['counterparty_name', 'date'])
    df['days_since_last_txn'] = (
        df.groupby('counterparty_name')['date'].diff().dt.days
    ).fillna(0.0)

    return df


def main():
    print("=" * 70)
    print(f"AGENT 2 -- Approval Classifier   (data: {os.path.basename(DATA_FILE)})")
    print("=" * 70)
    df = build_features(pd.read_csv(DATA_FILE))
    X = df[NUMERIC + CATEGORICAL]
    y = df['approved'].astype(int)
    print(f"rows={len(df)}  approved rate={y.mean():.3f}\n")

    pre = ColumnTransformer([
        ('num', StandardScaler(), NUMERIC),
        ('cat', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL),
    ])
    pipe = Pipeline([
        ('pre', pre),
        ('clf', LogisticRegression(max_iter=1000, random_state=42,
                                   class_weight='balanced')),
    ])

    # --- cross-validated ROC-AUC (does it generalise?) -------------------
    cv_auc = cross_val_score(pipe, X, y, cv=5, scoring='roc_auc')
    print(f"5-fold CV ROC-AUC : {cv_auc.mean():.3f} +/- {cv_auc.std():.3f}")
    if cv_auc.mean() > 0.99:
        print("  >> WARNING: AUC ~1.0 -- label is a deterministic function of")
        print("     the features (data leakage). Regenerate with generate_data.py.")
    else:
        print("  >> OK: realistic AUC -- the model learned a genuine pattern.")
    print()

    # --- held-out test split --------------------------------------------
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)
    pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    pred = pipe.predict(X_te)

    print("--- Held-out test performance ---")
    print(f"ROC-AUC : {roc_auc_score(y_te, proba):.3f}")
    print("Confusion matrix [[TN FP] [FN TP]]:")
    print(confusion_matrix(y_te, pred))
    print(classification_report(y_te, pred, digits=3,
                                target_names=['escalate(0)', 'approve(1)']))

    # --- explainability: which features drive approval? -----------------
    feat_names = (NUMERIC +
                  list(pipe.named_steps['pre']
                       .named_transformers_['cat']
                       .get_feature_names_out(CATEGORICAL)))
    coefs = pipe.named_steps['clf'].coef_[0]
    print("--- Logistic regression coefficients (sorted by impact) ---")
    for name, c in sorted(zip(feat_names, coefs), key=lambda t: -abs(t[1])):
        direction = "-> approve" if c > 0 else "-> escalate"
        print(f"  {name:28s} {c:+.3f}  {direction}")
    print()

    # --- retrain on all data and serialise ------------------------------
    pipe.fit(X, y)
    bundle = {
        'model': pipe,
        'numeric_features': NUMERIC,
        'categorical_features': CATEGORICAL,
        'cv_roc_auc': float(cv_auc.mean()),
    }
    out = os.path.join(MODELS_DIR, 'approval_classifier.pkl')
    with open(out, 'wb') as f:
        pickle.dump(bundle, f)
    print(f"Saved {out}")
    print("  (pickle is a dict: fitted Pipeline + feature lists + CV score)")


if __name__ == "__main__":
    main()
