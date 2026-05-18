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

#### **Phase 2: Agent Orchestration & Manager Agent Setup (45 mins)**

- [ ] **Platform/Orchestration Engineer:** Focus on Architect setup.
- [ ] **NEW: Build Agent 0 (Manager Agent)**
  - **Responsibility:** Act as the primary UI layer, intercept user input, interpret goals, and dispatch tasks to Agents 1-5.
  - Setup prompt to interface between human operator and the sub-agents.
- [ ] **Agent 1: Transaction Validator Component**
  - Integrate pre-trained `.pkl` Isolation Forest model.
- [ ] **Agent 2: Compliance Rules Engine**
  - Integrate pre-trained `.pkl` LR model. 
- [ ] **Agent 3: Treasurer Position & Risk**
  - Integrate pre-trained `.pkl` forecasting model.

---

### **Phase 3: Agent Development & Orchestration (30 mins)**

**Platform/Orchestration Engineer:** Focus on orchestration and Architect configuration.

**Agent 1: Transaction Validator**
- **Input:** `bank_transactions_input.json`
- **Processing:**
  - Parse transactions → normalize to ISO 20022 schema
  - Call ML anomaly detector (from Day 1)
  - Deduplicate check
  - Output: `agent1_normalized.json` (with anomaly scores)
- **Lyzr Template:** Use "Data Normalization" + "ML Integration" blueprint
- **Estimated Time:** 1.5 hours

**Agent 2: Compliance Rules Engine**
- **Input:** `agent1_normalized.json`, `compliance_rules.json`, `counterparty_reference.json`
- **Processing:**
  - For each transaction:
    - OFAC check (is counterparty in sanctions list?)
    - Transaction limit check (< daily limit per counterparty?)
    - Approval workflow (does it need approval?)
    - Reportable transaction (trigger SAR, CAT, TRACE?)
  - Call ML approval classifier
  - Output: `agent2_compliance_decisions.json` (with compliance status & confidence)
- **Lyzr Template:** Use "Rules Engine" + "API Integration" (for OFAC lookup)
- **Estimated Time:** 2 hours

**Agent 3: Treasurer Position & Risk**
- **Input:** `agent1_normalized.json`, GL balances, FX rates
- **Processing:**
  - Aggregate positions by currency, counterparty, entity
  - Compute liquidity ratios
  - Call ML forecast model (30-day cash flow)
  - Identify concentration risks
  - Output: `agent3_positions.json` (with liquidity metrics, forecast)
- **Lyzr Template:** Use "Data Aggregation" + "Analytics" blueprint
- **Estimated Time:** 1.5 hours

**Agent 4: Reconciliation Engine**
- **Input:** `agent1_normalized.json`, `gl_ledger.json`, Agent 2 & 3 outputs
- **Processing:**
  - Bank-to-ledger matching (fuzzy match on amount, date, counterparty)
  - Call ML match confidence scorer
  - Flag unmatched (timing differences, duplicates, fraud suspects)
  - Route exceptions to escalation queue
  - Output: `agent4_reconciliation.json` (with match status, unmatched list, escalations)
- **Lyzr Template:** Use "Data Matching" blueprint (or custom Python logic)
- **Estimated Time:** 2 hours

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
  - Feed 100 transactions through full pipeline
  - Measure execution time (target <5 minutes)
  - Verify all 5 agents execute in order
  - Check that unmatched items are properly escalated

**Deliverable:** Fully orchestrated 5-agent system, tested end-to-end

---

#### **Phase 4: UI, Polish & Demo Prep (15 mins)**

- [ ] **Leverage Architect's Low-Code UI Builder:**
  - Input form: Bank feed upload (drag-drop or CSV paste)
  - Dashboard 1: Reconciliation Status
    - Total transactions ingested
    - Matched count / % (progress bar)
    - Unmatched count (with drill-down)
    - Execution time
  - Dashboard 2: Compliance Exceptions & Human-in-the-Loop (HITL) Queue
    - Flagged transactions (table with reason, amount, counterparty)
    - Approvals needed (queue with approver names)
    - HITL Queue: Transactions where Rules and ML scores diverged (showing the calculated ML variance).
    - Risk summary (OFAC hits, high-risk counterparties)
  - Dashboard 3: Audit Trail
    - Transaction lookup (search by ID or counterparty)
    - Show all agent decisions for selected transaction (Agent 1 anomaly score → Agent 2 compliance decision → Agent 4 match result → Agent 5 audit log)
  - Export: PDF compliance report, CSV exception list, JSON audit trail

- [ ] **Architect UI Customization:**
  - Use Architect's built-in theming (or provide custom CSS)
  - Add company logo and "CATAS" branding
  - Make dashboards interactive (filter by entity, date range, risk level)

**Deliverable:** Polished, functional UI showing all outputs

#### **Demo Execution (8:45 PM - 9:00 PM)**

- [ ] **Create Demo Script:**
  ```
  1. [Time: 0-30 sec] Show problem statement on screen
     - "80% of companies report payment fraud"
     - "Manual reconciliation takes 20 hrs/month"
     - "Audit trail gaps = regulatory risk"
  
  2. [Time: 30-90 sec] Upload sample bank feed (100 transactions)
     - Show Architect ingesting data
  
  3. [Time: 90-180 sec] Run full pipeline
     - Show each agent executing (or fast-forward to results)
     - Highlight: "Processing 100 transactions in <5 minutes"
  
  4. [Time: 180-240 sec] Show results on dashboard
     - Reconciliation: "97 matched (97%), 3 unmatched (escalated)"
     - Compliance: "22 transactions flagged (OFAC, limits, workflows)"
     - Exposures: "Top counterparty = 18% of portfolio"
  
  5. [Time: 240-300 sec] Drill into one flagged transaction & Show HITL
     - Show Human-in-the-Loop feature: "Rule said approve, but ML detected 90% chance of escalating. Pushing to HITL review."
     - Show audit trail: Agent 1 flagged anomaly → Agent 2 flagged rule/ML variance → Agent 5 HITL recommended
     - Explain: "Complete traceability for regulators by catching edge cases"
  
  6. [Time: 300-330 sec] Export compliance report (PDF)
     - Show PDF with all flagged items, reasoning, recommendations
  
  7. [Time: 330-360 sec] Pitch impact
     - "Reconciliation: 20 hrs → 5 min (240x faster)"
     - "Compliance: Manual checks → Real-time rules"
     - "Audit ready: Full chain-of-custody in seconds"
  ```

- [ ] **Prepare Talking Points (No Slides Allowed):**
  - Point 1: Problem (80% fraud, manual processes, silos)
  - Point 2: Solution (5-agent system, explainable, real-time)
  - Point 3: Architecture verbal overview (workflow of agents)
  - Point 4: Impact metrics walkthrough (speed, accuracy, compliance)
  - Point 5: Why Lyzr Architect (low-code, multi-agent, ACE-V governance)
  - Point 6: Call to action (pilot with real treasury team)

- [ ] **Stress Test for Demo:**
  - Run pipeline 2-3 times to verify repeatability
  - Test on different data (try another 50 transactions)
  - Have backup data in case of issues
  - Pre-record agent execution (as fallback video, since slides aren't allowed)

- [ ] **Logistics:**
  - Test internet connectivity (for live demo)
  - Ensure Architect UI is accessible from demo screen
  - Check laptop + HDMI cable works + battery is ok

**Deliverable:** Polished, 5-minute live demo (strict adherence to hands-on demo rules)

---

## Specific ML Engineering Tasks

### **Task 1: Anomaly Detection (Agent 1)**

**Objective:** Identify unusual transactions that may indicate fraud or data entry errors.

**Steps:**
1. **Load Data:**
   ```python
   import pandas as pd
   df_historical = pd.read_csv('data/historical_transactions.csv')  # 1000 rows
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

4. **Inference (in Agent 2):**
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

### **Task 3: Cash Flow Forecast (Agent 3)**

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
   joblib.dump(model, 'models/forecast_model_entity_a_usd.pkl')
   # (repeat for each entity/currency combination)
   ```

4. **Inference (in Agent 3):**
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
- [ ] **Platform/Orchestration Engineer:** Repos initialized, Lyzr Architect sandbox ready

### **End of Phase 2 (8:00 PM):**
- [ ] **Platform/Orchestration Engineer:** Manager Agent and Agents 1-5 logic built in Architect
- [ ] **Data Scientist/ML Engineer:** Verify incoming live schemas match pre-trained models

### **End of Phase 3 (8:30 PM):**
- [ ] **Platform/Orchestration Engineer:** Agents deployed in Architect, individual tests passing
- [ ] **Both:** Models integrated, End-to-end pipeline tested

### **End of Phase 4 (8:45 PM):**
- [ ] **Platform/Orchestration Engineer:** UI polished, dashboards functional
- [ ] **Both:** Demo rehearsed, talking points finalized (live demo only)

---

## Failure Recovery Plan

**If ML models aren't training properly:**
- Use simpler heuristics instead (e.g., hardcoded anomaly rules: flag if amount > 3σ from mean)
- Agent 1: Flag transactions with amount > $1M as anomalies
- Agent 2: Flag high-risk counterparties automatically, approve low-risk
- Agent 3: Use simple average (no forecasting) for liquidity

**If Architect orchestration issues:**
- Build agents as standalone Python scripts, then wrap in Architect
- Or use bash/shell scripts to chain agents (Agent 1 output → Agent 2 input, etc.)
- Export intermediate results to JSON files for manual inspection

**If UI not rendering:**
- Fallback: Show results as tables/JSON in browser console
- Or export CSV reports instead of interactive dashboards

**Time constraints:**
- Minimum viable demo: Show Agent 1 + Agent 2 (most impactful)
- Skip Agent 3 (treasury functions) if needed
- Still show audit trail (Agent 5) at end

---

## Success Metrics (Hackathon)

| Metric | Target | Importance |
|--------|--------|-----------|
| **Pipeline executes end-to-end** | Yes | Critical |
| **Execution time** | <5 min for 100 txns | High |
| **Match rate** | >95% | High |
| **Compliance rules applied** | 5+ | High |
| **Audit trail complete** | 100% coverage | Critical |
| **UI functional** | All dashboards load | Medium |
| **Demo runs live** | No crashes | High |
| **Pitch clarity** | Problem → Solution → Impact | High |

---

## Post-Hackathon Next Steps

If judges show interest / you win:

1. **Expand to real data:** Connect to actual bank APIs (Plaid, etc.)
2. **Production ML:** Retrain models on larger datasets, optimize hyperparameters
3. **Regulatory integration:** Add real OFAC list integration, regulatory submission APIs
4. **Enterprise deployment:** Scale to multi-user, add user auth/permissions
5. **IP & IP protection:** Patent agent orchestration approach, trademark CATAS

