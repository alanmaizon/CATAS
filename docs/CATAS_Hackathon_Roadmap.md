# CATAS Hackathon: Implementation Roadmap
## Development Plan & ML Engineering Assignments

**Event Details:**
- **Date:** May 19, 2026
- **Time:** 6:30 PM – 9:00 PM
- **Location:** Baseline, Dublin (Exact details provided upon acceptance).
- **Format:** Hands-on building and live demos. No slide decks allowed.

---

## Hackathon Timeline

### **Schedule (6:30 PM - 9:00 PM)**

| Time | Activity | Description |
| ---- | -------- | ----------- |
| **6:30 PM - 7:00 PM** | **Doors Open & Networking** | Arrive, check-in, grab some refreshments, and start networking with fellow participants. |
| **7:00 PM - 7:15 PM** | **Welcome & Opening Ceremony** | Official welcome, introduction to the hackathon theme, Lyzr AI, and the challenges. |
| **7:15 PM - 8:45 PM** | **Building Starts** | Get ready to build! Rapid development, model training, and agent orchestration. |
| **8:45 PM - 9:00 PM** | **Crowd Source Voting & Live Demos** | Demo your solution and vote on the best projects. No slide decks permitted. |

---

### **Pre-Hackathon Preparation (Prior to May 19)**

Due to limited hackathon time, data generation and initial model training **must be completed prior to the event**. We will utilize **Offline Learning (Static Pre-Trained Models)** for the hackathon MVP to ensure predictability. Continuous online learning will be deferred to post-hackathon scaling.

#### **Data Strategy (Critical):**
- **Synthetic Data Generation:** We will *generate* synthetic data rather than searching for real datasets to avoid PII/compliance issues and to tightly control the schema.
- **Strict Schema Enforcement:** It is CRITICAL that the incoming hackathon payload precisely matches the pre-trained distribution. If schemas or distributions drift (data gap), the pre-trained offline models will collapse.

#### **Phase 0: Pre-Event Setup & Data Generation**
- [ ] Review problem statement and technical architecture
- [ ] Define precise Lyzr Architect agent interfaces and schemas
- [ ] Set up shared repo (GitHub), data directory structure
- [ ] **Generate Synthetic Pre-Training Data:**
  - 1000 historical transactions with normal/anomaly annotations
  - 12-month historical flow for cash positioning
  - Enforce static JSON structure

#### **Phase 1: Pre-Event Offline ML Training**
- [ ] **Data Scientist/ML Engineer Task:**
  - Train Agent 1 (Isolation Forest) on synthetic transaction history
  - Train Agent 2 (Logistic Regression) on synthetic approval data
  - Train Agent 3 (ARIMA/Prophet) on 12-month synthetic cash flows
  - **Deliverable:** Serialized `.pkl` models stored in `/models/`

---

### **Hackathon Development Plan (7:15 PM - 8:45 PM)**

#### **Phase 2: Lyzr Agent Studio Setup (30 mins)**

- [ ] **Dual-Agent Creation in UI:**
  - Create **Treasury Agent**: Focuses on liquidity, anomaly detection, and state.
  - Create **Compliance Agent**: Focuses on regulatory rule-sets and sanction checking.
- [ ] **Enterprise Guardrails Setup:**
  - Attach **AWS Bedrock Guardrails** to redact PII (IBANs/Names) before hitting the LLM.
  - Configure **Amazon AgentCore Memory** (`eu-west-1`) for cross-session contexts securely via IAM Role assumption.
- [ ] **Secure API IDs:**
  - Extract Agent IDs and API Keys and populate the `.env` for `run_catas.py`.

---

#### **Phase 3: Python Orchestration & ML Integration (45 mins)**

**Platform/Orchestration Engineer:** Focus on `run_catas.py` and ML injection.

**Architectural Focus:**
- `run_catas.py` orchestrates the flow natively in Python, eliminating the need for a 5-agent sequential chain.
- The Python script executes the pre-trained `scikit-learn` `.pkl` models FIRST, injecting their deterministic math (anomaly scores, liquidity risk, approvals) into the LLM prompt.

**Agent 1: Treasury Operations**
- **Input:** Raw JSON data & Offline ML outputs (`anomaly_detector.pkl`, `forecast_model.pkl`).
- **Tools (Skills):** `parse-ledger-data`.
- **Goal:** Evaluate transactions against liquidity risk and anomaly bounds.

**Agent 2: Compliance Operations**
- **Input:** Treasury summary, RAG Policies, & Offline ML outputs (`approval_classifier.pkl`).
- **Tools (Skills):** `trigger-mlro-alert`, `write-audit-log`.
- **Goal:** Evaluate cross-border transactions against EU Sanctions (CBI/EBA) and generate an immutable log.

**Agent 5: Audit Trail & Reporting**
- **Input:** All agent outputs, Architect audit logs
- **Processing:**
  - Generate immutable audit trail (who, what, when, why for each decision)
  - Compose compliance report (flagged items, approvals needed)
  - Export audit-ready PDF
  - Output: `agent5_audit_trail.json`, `compliance_report.pdf`
- **Lyzr Template:** Use "Report Generation" + "PDF Export" blueprint
- **Estimated Time:** 1.5 hours

#### **Phase 3: Integration, Testing & Orchestration (30 mins)**

- [ ] **Define Agent Dependencies:**
  ```
  Agent 0 (Manager Agent / UI)
    ↓
  Agent 1 (Transaction Validator) 
    ↓
  Agent 2 (Compliance) ← Agent 3 (Treasury)
    ↓
  Agent 4 (Reconciliation)
    ↓
  Agent 5 (Reporting)
    ↓
  Agent 0 (Returns Dashboard & Outputs to User)
  ```

- [ ] **Configure Lyzr Architect Orchestration:**
  - Agent 1 runs first (parallel processing possible for bank feed chunks)
  - Agent 2 & 3 run in parallel (independent of each other)
  - Agent 4 waits for Agents 2 & 3 to complete
  - Agent 5 runs last (aggregates all decisions)
  - Set timeout for long-running steps (e.g., ML inference)

- [ ] **Test Each Agent Independently:**
  - Run Agent 1 on 100 transactions, verify output schema
  - Run Agent 2 on Agent 1 output, check compliance flagging (should flag ~20-30 transactions)
  - Run Agent 3 on Agent 1 output, verify position aggregation
  - Run Agent 4, check match rates (target >95%)
  - Run Agent 5, verify audit trail is complete

- [ ] **End-to-End Test:**
  - Feed sample payload through `run_catas.py`
  - Measure execution time.
  - Verify deterministic ML inference executes correctly before LLM RAG rules apply.
  - Verify `write-audit-log` is capturing the sequence correctly.

**Deliverable:** Fully orchestrated Dual-Agent pipeline running natively in Python, tested end-to-end.

---

#### **Phase 4: Terminal Polish & Demo Prep (15 mins)**

- [ ] **Prepare Terminal Output:**
  - Ensure `run_catas.py` output is clean and readable for judges.
  - Color-code JSON output logs for Treasury vs Compliance returns.
- [ ] **Demo Execution (8:45 PM - 9:00 PM)**
  - [ ] **Create Demo Script:**
    ```
    1. Show problem statement on screen (fraud, manual processes, audit silos).
    2. Kick off `run_catas.py` in Terminal.
    3. Explain the Dual-Agent Architecture while it executes: Treasury (Agent 1) hands off to Compliance (Agent 2).
    4. Emphasize offline ML models grounding the AI decisions.
    5. Show the EU Sanctions rules being applied deterministically.
    6. Open the `audit_log.jsonl` to prove Structural Accountability.
    ```
  - [ ] **Prepare Talking Points (No Slides Allowed):**
    - Private-by-design (AWS Bedrock Guardrails, AgentCore Memory in `eu-west-1`).
    - Deterministic skills execution (`parse-ledger-data`, `trigger-mlro-alert`).
    - Explainable "Human-in-the-Loop" architecture.

**Deliverable:** Polished, 5-minute live terminal demo.

---

## Specific ML Engineering Tasks

### **Task 1: Anomaly Detection (Treasury ML)**

**Objective:** Identify unusual transactions that may indicate fraud or data entry errors.

**Steps:**
1. **Load Data:**
   ```python
   import pandas as pd
   df_historical = pd.read_csv('data/historical_transactions.csv')
   ```

2. **Feature Engineering:**
   ```python
   df_historical['amount_normalized'] = df_historical['amount'] / df_historical['amount'].mean()
   df_historical['hour'] = pd.to_datetime(df_historical['timestamp']).dt.hour
   df_historical['day_of_week'] = pd.to_datetime(df_historical['timestamp']).dt.dayofweek
   df_historical['counterparty_encode'] = pd.factorize(df_historical['counterparty_name'])[0]
   df_historical['txn_type_encode'] = pd.factorize(df_historical['transaction_type'])[0]
   df_historical['currency_encode'] = pd.factorize(df_historical['currency'])[0]
   
   features = ['amount_normalized', 'hour', 'day_of_week', 'counterparty_encode', 
               'txn_type_encode', 'currency_encode']
   X = df_historical[features].fillna(0)
   ```

3. **Train Model:**
   ```python
   from sklearn.ensemble import IsolationForest
   
   iso_forest = IsolationForest(contamination=0.1, random_state=42)
   iso_forest.fit(X)
   
   # Save model
   import pickle
   pickle.dump(iso_forest, open('models/anomaly_detector.pkl', 'wb'))
   ```

4. **Inference (in Agent 1):**
   ```python
   # For each new transaction:
   features_new = [amount_norm, hour, day, cp_code, type_code, curr_code]
   anomaly_score = iso_forest.decision_function([features_new])[0]
   is_anomaly = iso_forest.predict([features_new])[0] == -1
   
   # Output: anomaly_score (continuous), is_anomaly (boolean)
   ```

**Success Criteria:**
- Precision > 80% (if flagged as anomaly, is it actually unusual?)
- Recall > 70% (catch most real anomalies)
- Flag rate 10-15% of transactions (tune contamination parameter)

---

### **Task 2: Approval Classification (Agent 2)**

**Objective:** Learn which transactions compliance officers typically escalate vs. approve automatically.

**Steps:**
1. **Load Training Data:**
   ```python
   df_approval = pd.read_csv('data/historical_transactions.csv')
   # Assume columns: transaction_type, amount, counterparty_risk, user_role, approved (0/1)
   ```

2. **Feature Engineering:**
   ```python
   df_approval['amount_ratio'] = df_approval['amount'] / df_approval['daily_limit']
   df_approval['days_since_last_txn'] = (df_approval['date'] - df_approval['date'].shift(1)).dt.days
   df_approval['txn_type_encode'] = pd.factorize(df_approval['transaction_type'])[0]
   df_approval['cp_risk_encode'] = df_approval['counterparty_risk'].map({'low': 0, 'medium': 1, 'high': 2})
   df_approval['user_role_encode'] = pd.factorize(df_approval['user_role'])[0]
   
   features = ['amount_ratio', 'days_since_last_txn', 'txn_type_encode', 'cp_risk_encode', 'user_role_encode']
   X = df_approval[features].fillna(0)
   y = df_approval['approved']
   ```

3. **Train Model:**
   ```python
   from sklearn.linear_model import LogisticRegression
   
   lr = LogisticRegression(random_state=42, max_iter=1000)
   lr.fit(X, y)
   
   pickle.dump(lr, open('models/approval_classifier.pkl', 'wb'))
   ```

4. **Inference (in `run_catas.py` LLM Orchestrator):**
   ```python
   # For each transaction:
   features_new = [amount_ratio, days_since_last, type_code, risk_code, role_code]
   approval_prob = lr.predict_proba([features_new])[0][1]  # Probability of approval
   
   # Output: approval_prob (0-1)
   # Business logic: If approval_prob > 0.7, mark as "likely approve"
   #                 If approval_prob < 0.3, mark as "likely escalate"
   #                 If 0.3-0.7, "uncertain" (manual review)
   # HITL Logic:     Compare deterministic rule status vs ML approval_prob
   #                 If Rule Status == "APPROVE" but approval_prob < 0.3 -> Route to Human-in-the-Loop review
   ```

**Success Criteria:**
- Accuracy > 75% on held-out test set
- Precision/recall balanced (avoid over-favoring approval)
- Approval confidence (0-1) matches human confidence

---

### **Task 3: Cash Flow Forecast (Treasury ML)**

**Objective:** Predict next 30 days of cash outflows to identify liquidity risk.

**Steps:**
1. **Load Data:**
   ```python
   df_gl = pd.read_csv('data/gl_balances_daily.csv')  # daily closing balances, 12 months
   # Columns: date, entity, currency, account_type, balance
   
   # Aggregate daily outflows by entity/currency
   df_outflows = df_gl[df_gl['account_type'] == 'payable'].groupby(['date', 'entity', 'currency'])['balance'].sum()
   ```

2. **Feature Engineering (if using traditional time-series):**
   ```python
   # Simple approach: Use 12-month daily outflow averages
   df_outflows_pivot = df_outflows.unstack(fill_value=0)  # Wide format: date vs entity/currency
   
   # Or use Prophet (no manual feature engineering):
   from fbprophet import Prophet
   
   for entity in ['Entity_A', 'Entity_B', 'Entity_C']:
     for currency in ['USD', 'EUR', 'GBP']:
       df_ts = df_outflows[entity][currency].reset_index()
       df_ts.columns = ['ds', 'y']
       
       model = Prophet(yearly_seasonality=True, seasonality_mode='additive')
       model.fit(df_ts)
       
       future = model.make_future_dataframe(periods=30)
       forecast = model.predict(future)  # Returns: yhat (forecast), yhat_lower, yhat_upper
   ```

3. **Serialize Model:**
   ```python
   import joblib
   joblib.dump(model, 'models/forecast_model.pkl')
   # (repeat for each entity/currency combination)
   ```

4. **Inference (in `run_catas.py` LLM Orchestrator):**
   ```python
   # Load model, make 30-day forecast
   forecast = model.predict(future_dates_30)
   
   # Calculate liquidity metrics:
   avg_daily_outflow = forecast['yhat'].mean()
   min_balance_forecast = current_balance - forecast['yhat'].sum()
   liquidity_coverage_days = current_balance / avg_daily_outflow
   
   # Flag if liquidity < 5 days
   if liquidity_coverage_days < 5:
       flag_liquidity_risk = True
   ```

**Success Criteria:**
- MAPE < 15% (mean absolute percentage error on validation set)
- Forecast captures seasonality (e.g., month-end spikes in payables)
- Confidence intervals reasonable (not too wide)

---

## Collaboration Checkpoints

### **End of Pre-Hackathon:**
- [ ] **Data Scientist/ML Engineer:** Synthetic datasets mapped, 3 ML models trained (offline), serialized (`.pkl`), ready for integration
- [ ] **Platform/Orchestration Engineer:** Repos initialized, Python orchestrator `.env` ready

### **End of Phase 2 (8:00 PM):**
- [ ] **Platform/Orchestration Engineer:** Treasury and Compliance agents built in Lyzr UI, API IDs inserted to `.env`.
- [ ] **Data Scientist/ML Engineer:** Verify incoming live schemas match pre-trained models.

### **End of Phase 3 (8:30 PM):**
- [ ] **Platform/Orchestration Engineer:** `run_catas.py` successfully chaining Python + Lyzr API + Skills.
- [ ] **Both:** Models integrated, Dual-Agent End-to-end pipeline tested.

### **End of Phase 4 (8:45 PM):**
- [ ] **Platform/Orchestration Engineer:** Terminal output polished, JSON strings color-coded.
- [ ] **Both:** Demo rehearsed, talking points finalized (live terminal demo only)

---

## Failure Recovery Plan

**If ML models aren't training properly:**
- Use simpler heuristics instead (e.g., hardcoded anomaly rules: flag if amount > 3σ from mean)
- Agent 1: Flag transactions with amount > $1M as anomalies.
- Agent 2: Flag high-risk counterparties automatically, approve low-risk.

**If `run_catas.py` API bridging fails:**
- Drop dual-agent complex pass-off, just ask the Treasury agent for both pieces of logic.
- Or use bash/shell scripts to chain `.pkl` output directly to pure ChatGPT APIs.

**If Terminal Output unreadable:**
- Turn off debug JSON logs, print clear `[TREASURY]` and `[COMPLIANCE]` headers.

**Time constraints:**
- Minimum viable demo: Show just the Treasury agent running the anomaly detector.

---

## Success Metrics (Hackathon)

| Metric | Target | Importance |
|--------|--------|-----------|
| **Pipeline executes end-to-end** | Yes | Critical |
| **Dual-Agent Passing works** | Yes | High |
| **Deterministic skills hit** | >95% | High |
| **Compliance rules applied** | 5+ | High |
| **Audit trail complete** | 100% coverage | Critical |
| **Demo runs live** | No crashes | High |
| **Pitch clarity** | Problem → Solution → Impact | High |

---

## Post-Hackathon Next Steps

If judges show interest / you win:

1. **Expand to real data:** Connect to actual bank APIs (Plaid, etc.)
2. **Production ML:** Retrain models on larger datasets, optimize hyperparameters
3. **Regulatory integration:** Add real EU/CBI sanction list integration, regulatory submission APIs
4. **Enterprise deployment:** Scale to multi-user, add user auth/permissions
5. **IP & IP protection:** Patent agent orchestration approach, trademark CATAS

