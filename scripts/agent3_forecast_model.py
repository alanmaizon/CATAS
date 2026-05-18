"""
agent3_forecast_model.py  --  Agent 3: Cash-flow / balance forecaster
======================================================================

PROBLEM WITH THE ORIGINAL (`scripts/train_models.py :: train_agent3...`)
-------------------------------------------------------------------------
1. NO BACKTEST. The original fits ARIMA(1,1,1) on the ENTIRE 365-day
   series and pickles it. The forecast is never compared against any
   held-out actuals, so its accuracy is completely unknown. "Trained
   successfully" is not the same as "forecasts well".
2. NO BASELINE. A forecast model is only useful if it beats the trivial
   baselines (last-value / seasonal-naive). Without that comparison there
   is no evidence the ARIMA adds anything.
3. SEASONALITY IGNORED. The GL series carries a weekly cycle, but a plain
   ARIMA(1,1,1) has no seasonal term, so it forecasts a smooth line and
   systematically misses the weekly peaks and troughs.
4. ORDER ASSUMED, NOT CHECKED. `(1,1,1)` is hard-coded "for simplicity"
   with no stationarity test (ADF) to justify the single difference.

Is the model "overfitting"? For a time series the wording is different,
but the underlying disease is identical to Agents 1 & 2: it was trained on
synthetic data and NEVER validated, so a great-looking fit tells you
nothing about real forecasting skill. This file adds the validation.

WHAT THIS FILE FIXES
--------------------
* Trains on the realistic `_v2` GL series (trend + weekly + monthly cycles
  + noise + occasional outflow spikes).
* Holds out the last HORIZON days as a backtest set.
* Compares SARIMAX (with a weekly seasonal term) against two baselines:
  last-value naive and seasonal (t-7) naive.
* Reports MAE / RMSE / MAPE on the held-out window for every method.
* Runs an ADF stationarity test to justify the differencing order.

Run:  python agent3_forecast_model.py
"""

import os
import pickle
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
import warnings
warnings.filterwarnings('ignore')

HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, '..', 'data')
MODELS_DIR = os.path.join(HERE, '..', 'models')
os.makedirs(MODELS_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, 'gl_balances_daily_v2.csv')
if not os.path.exists(DATA_FILE):
    DATA_FILE = os.path.join(DATA_DIR, 'gl_balances_daily.csv')

HORIZON = 30          # days held out for the backtest
ENTITY, CURRENCY = 'Entity A', 'USD'


def metrics(actual, pred):
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    mae = np.mean(np.abs(actual - pred))
    rmse = np.sqrt(np.mean((actual - pred) ** 2))
    mape = np.mean(np.abs((actual - pred) / np.clip(np.abs(actual), 1e-9, None))) * 100
    return mae, rmse, mape


def report(name, actual, pred):
    mae, rmse, mape = metrics(actual, pred)
    print(f"  {name:22s}  MAE={mae:12,.0f}  RMSE={rmse:12,.0f}  MAPE={mape:6.2f}%")
    return rmse


def main():
    print("=" * 70)
    print(f"AGENT 3 -- Cash-Flow Forecaster   (data: {os.path.basename(DATA_FILE)})")
    print("=" * 70)
    df = pd.read_csv(DATA_FILE)
    ts = df[(df.entity == ENTITY) & (df.currency == CURRENCY)].copy()
    ts['date'] = pd.to_datetime(ts['date'])
    ts = ts.sort_values('date').set_index('date')['balance'].asfreq('D')
    print(f"series: {ENTITY}/{CURRENCY}  length={len(ts)} days\n")

    # --- stationarity check (justifies the differencing order d) --------
    adf_p = adfuller(ts.dropna())[1]
    print(f"[ADF] p-value on raw series      = {adf_p:.4f} "
          f"({'stationary' if adf_p < 0.05 else 'non-stationary -> needs d>=1'})")
    adf_p_diff = adfuller(ts.diff().dropna())[1]
    print(f"[ADF] p-value after 1 difference = {adf_p_diff:.4f} "
          f"({'stationary' if adf_p_diff < 0.05 else 'still non-stationary'})\n")

    # --- train / backtest split -----------------------------------------
    train, test = ts.iloc[:-HORIZON], ts.iloc[-HORIZON:]
    print(f"train={len(train)} days   backtest={len(test)} days\n")

    print(f"--- Backtest over the last {HORIZON} days ---")
    # Baseline 1: last observed value carried forward.
    naive = np.repeat(train.iloc[-1], HORIZON)
    report("naive (last value)", test, naive)

    # Baseline 2: seasonal naive -- repeat the value from 7 days earlier.
    seasonal_naive = [train.iloc[-7 + (i % 7)] for i in range(HORIZON)]
    report("seasonal naive (t-7)", test, seasonal_naive)

    # SARIMAX with a weekly seasonal component.
    order, seasonal_order = (1, 1, 1), (1, 0, 1, 7)
    sarimax = SARIMAX(train, order=order, seasonal_order=seasonal_order,
                      enforce_stationarity=False,
                      enforce_invertibility=False).fit(disp=False)
    fc = sarimax.get_forecast(steps=HORIZON).predicted_mean
    sarimax_rmse = report(f"SARIMAX{order}x{seasonal_order}", test, fc)

    # Plain ARIMA(1,1,1) -- the original model, for direct comparison.
    arima = SARIMAX(train, order=(1, 1, 1)).fit(disp=False)
    arima_fc = arima.get_forecast(steps=HORIZON).predicted_mean
    arima_rmse = report("ARIMA(1,1,1) [original]", test, arima_fc)

    print()
    # --- model selection: ship whatever actually won the backtest -------
    scores = {
        'seasonal_naive': metrics(test, seasonal_naive)[1],
        'sarimax': sarimax_rmse,
        'arima': arima_rmse,
    }
    winner = min(scores, key=scores.get)
    print(f">> Backtest winner: '{winner}' (RMSE={scores[winner]:,.0f}).")
    if winner == 'seasonal_naive':
        print("   The seasonal-naive baseline wins -- a heavier model is NOT")
        print("   justified for this series. Shipping the baseline forecaster.")
    else:
        print(f"   '{winner}' beats the naive baseline -- shipping it.")
    print()

    # --- serialise the WINNING method (refit on the full series) --------
    bundle = {
        'entity': ENTITY, 'currency': CURRENCY,
        'method': winner,
        'backtest_rmse': float(scores[winner]),
        'backtest_horizon': HORIZON,
        'backtest_scores': {k: float(v) for k, v in scores.items()},
    }
    if winner == 'seasonal_naive':
        # The "model" is just the last weekly cycle of observed values.
        bundle['last_week'] = ts.iloc[-7:].tolist()
        bundle['model'] = None
    else:
        ord_, sord_ = ((order, seasonal_order) if winner == 'sarimax'
                       else ((1, 1, 1), (0, 0, 0, 0)))
        bundle['model'] = SARIMAX(ts, order=ord_, seasonal_order=sord_,
                                  enforce_stationarity=False,
                                  enforce_invertibility=False).fit(disp=False)
        bundle['order'], bundle['seasonal_order'] = ord_, sord_

    out = os.path.join(MODELS_DIR, 'forecast_model.pkl')
    with open(out, 'wb') as f:
        pickle.dump(bundle, f)
    print(f"Saved {out}")
    print(f"  (pickle is a dict: method='{winner}' + model/last_week + backtest RMSE)")


if __name__ == "__main__":
    main()
