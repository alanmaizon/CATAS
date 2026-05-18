"""
agent1_anomaly_detector.py  --  Agent 1: Transaction anomaly detection
=======================================================================

PROBLEM WITH THE ORIGINAL (`scripts/train_models.py :: train_agent1...`)
------------------------------------------------------------------------
1. TRIVIALLY SEPARABLE DATA. The generator put normal amounts in
   [100, 50k] and anomalies in [500k, 2M] with a $458k empty gap, and gave
   the two classes disjoint hour sets. Result: the task is not "detect
   anomalies", it is "is amount > 100k". A depth-1 stump scores F1 = 1.0.
2. NO EVALUATION. The model is `.fit()` on 100% of the data and pickled.
   There is no train/test split and no metric -- so the fact that the task
   is trivial is completely invisible. "It works" is never actually checked.
3. LEAKY / UNSTABLE FEATURE. `amount_normalized = amount / amount.mean()`.
   The mean is dominated by the injected mega-anomalies, so the scaling
   factor itself depends on the anomaly rate and shifts every data refresh.
4. MIS-TYPED CATEGORICALS. `pd.factorize()` turns counterparty / currency
   into arbitrary integer codes. Isolation Forest splits them as if 'CAD'(4)
   were "greater than" 'USD'(0). That ordering is meaningless.
5. `contamination=0.1` is hard-wired to the exact 10% injection rate. On
   real data the true rate is unknown; baking it in is circular reasoning.

IS IT "OVERFitting"?  -- Not in the classic high-variance sense. The model
generalises perfectly... to more data from the SAME broken generator. The
real failure is *distributional*: the synthetic data is unrealistically
easy, so good offline numbers say nothing about real-world performance.
That is the danger the project owner correctly suspected.

WHAT THIS FILE FIXES
--------------------
* Trains on the realistic `_v2` data (overlapping classes) by default.
* Honest evaluation: train/test split, ROC-AUC and average precision of the
  anomaly score against the held-out `is_anomaly` ground truth.
* Stable, sensible features: log-amount, amount-vs-counterparty-typical
  ratio, hour, off-hours flag, day-of-week; categoricals one-hot encoded.
* `contamination='auto'`; the alert threshold is *tuned* on the training
  fold (best-F1) instead of being assumed.
* Prints the depth-1-stump baseline so anyone can see whether the task is
  still trivially separable.

Run:  python agent1_anomaly_detector.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, classification_report
import warnings
warnings.filterwarnings('ignore')

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, '..', 'data')
MODELS_DIR = os.path.join(HERE, '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

# Prefer the realistic v2 data; fall back to the original if not generated.
DATA_FILE = os.path.join(DATA_DIR, 'historical_transactions_v2.csv')
if not os.path.exists(DATA_FILE):
    DATA_FILE = os.path.join(DATA_DIR, 'historical_transactions.csv')


def build_features(df):
    """Stable, model-appropriate features (no leaky mean, no fake ordinals)."""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_offhours'] = (~df['hour'].between(8, 18)).astype(int)

    # log-amount: stable and bounded, unlike amount / amount.mean().
    df['log_amount'] = np.log1p(df['amount'])

    # How big is this txn vs what is TYPICAL for this counterparty?
    # This is the genuinely informative signal -- a $200k payment is normal
    # for a big counterparty but a red flag for a small one.
    cp_median = df.groupby('counterparty_name')['amount'].transform('median')
    df['amount_vs_cp_typical'] = df['amount'] / cp_median.clip(lower=1.0)

    numeric = ['log_amount', 'amount_vs_cp_typical', 'hour',
               'day_of_week', 'is_offhours']
    # One-hot encode categoricals instead of arbitrary integer codes.
    cats = pd.get_dummies(df[['transaction_type', 'currency']],
                          prefix=['type', 'ccy'])
    X = pd.concat([df[numeric], cats.astype(float)], axis=1)
    return X.fillna(0.0)


def main():
    print("=" * 70)
    print(f"AGENT 1 -- Anomaly Detector   (data: {os.path.basename(DATA_FILE)})")
    print("=" * 70)
    df = pd.read_csv(DATA_FILE)
    X = build_features(df)
    y = df['is_anomaly'].astype(int)
    print(f"rows={len(df)}  features={X.shape[1]}  anomaly rate={y.mean():.3f}\n")

    # --- separability check: is the task still trivially easy? -----------
    stump = DecisionTreeClassifier(max_depth=1, random_state=42)
    stump_f1 = cross_val_score(stump, df[['amount']], y, cv=5, scoring='f1').mean()
    print(f"[separability] depth-1 stump on `amount` alone, 5-fold F1 = {stump_f1:.3f}")
    if stump_f1 > 0.98:
        print("  >> WARNING: data is trivially separable -- metrics below are")
        print("     meaningless. Regenerate with ml/generate_data.py.\n")
    else:
        print("  >> OK: classes overlap, the task is non-trivial.\n")

    # --- honest train/test split ----------------------------------------
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    # Isolation Forest is unsupervised: it sees ONLY X_tr, never the labels.
    iso = IsolationForest(n_estimators=300, contamination='auto',
                          random_state=42, n_jobs=-1)
    iso.fit(X_tr)


    train_score = -iso.score_samples(X_tr)
    test_score = -iso.score_samples(X_te)

    
    auc = roc_auc_score(y_te, test_score)
    ap = average_precision_score(y_te, test_score)

    
    for thr in np.quantile(train_score, np.linspace(0.5, 0.99, 50)):
        f1 = f1_score(y_tr, (train_score >= thr).astype(int))
        if f1 > best_f1:
            best_f1, best_thr = f1, thr
    test_pred = (test_score >= best_thr).astype(int)

    print("--- Held-out test performance (Isolation Forest) ---")
    print(f"ROC-AUC                : {auc:.3f}")
    print(f"Average precision (PR) : {ap:.3f}")
    print(f"Tuned threshold        : {best_thr:.4f}  (chosen on train fold)")
    print(classification_report(y_te, test_pred, digits=3,
                                target_names=['normal', 'anomaly']))

    if auc > 0.995:
        print(">> NOTE: AUC ~1.0 means the data is still too easy; trust this")
        print("   model only after testing on REAL transactions.\n")
    else:
        print(">> Realistic AUC -- model has learned a non-trivial signal.\n")

   
    final = IsolationForest(n_estimators=300, contamination='auto',
                            random_state=42, n_jobs=-1)
    final.fit(X)
    bundle = {
        'model': final,
        'feature_names': list(X.columns),
        'alert_threshold': float(best_thr),
        'test_roc_auc': float(auc),
        'test_avg_precision': float(ap),
    }
    out = os.path.join(MODELS_DIR, 'anomaly_detector.pkl')
    with open(out, 'wb') as f:
        pickle.dump(bundle, f)
    print(f"Saved {out}")
    print("  (pickle is a dict: model + feature_names + tuned threshold + metrics)")


if __name__ == "__main__":
    main()
