# CATAS Hackathon: Quick Reference Card

---

## The Pitch (60 seconds)

> **Problem:** Treasury and compliance teams operate in silos with manual processes. 80% of companies report payment fraud. Treasury reconciliation takes 20+ hours/month. Regulators demand complete audit trails that manual systems can't provide.

> **Solution:** CATAS is a Dual-Agent architecture (Treasury & Compliance) that orchestrates transaction validation, compliance rule enforcement, and regulatory reporting in real-time with explainable AI grounded by deterministic ML math.

> **Impact:** Reconciliation time drops from 20 hrs to <5 minutes. Compliance goes from reactive to real-time. Full audit trail ready for regulators instantly.

> **Why Lyzr:** Deploying Lyzr Agent Studio with a Python orchestrator enables us to build, test, and deploy a production-grade multi-agent system in 48 hours instead of months.

---

## The Problem, In Numbers

| Challenge | Current State | CATAS Target |
|-----------|--------------|-------------|
| **Reconciliation time** | 20 hrs/month | <5 min (per 100 txns) |
| **Manual errors** | 50+ per 1,000 txns | 98% auto-match accuracy |
| **Compliance rules** | Manual checks (days) | Real-time (milliseconds) |
| **Audit trail** | Fragmented, incomplete | 100% coverage, immutable |
| **Fraud detection** | Days to discover | Real-time flags |
| **Regulatory reporting** | 2-4 weeks to prepare | Instant log generation |

---

## The Dual-Agent Architecture

```
INPUT: Raw bank feeds, API calls
  ↓
[Python Orchestrator: run_catas.py]
  ↓ Applies deterministic Scikit-Learn logic (.pkl models)
[Agent 1: Treasury Operations]
  ↓ Parses ledger, detects anomalies, forecasts liquidity
[Agent 2: Compliance Operations]
  ↓ Checks EU Sanctions (CBI/EBA), ensures limits, triggers alerts
OUTPUT: Audit log (`audit_log.jsonl`), JSON exception returns
```

---

## What Each Agent Does

### **Agent 1: Treasury Operations** (Normalize + Detect Anomalies + Forecast)
- **Input:** Raw transaction data + ML parameters
- **Processing:** Parse → Check Liquidity Risk → Evaluate Anomaly Score
- **Output:** Structured transaction evaluation
- **ML Models:** Isolation Forest (`anomaly_detector.pkl`) & Time-Series (`forecast_model.pkl`)

### **Agent 2: Compliance Operations** (Validate + Escalate + Log)
- **Input:** Treasury summary + ML approval probability
- **Processing:** EU Sanctions check → Amount limits → Approval workflows → Write Audit Log
- **Output:** Compliance decision (APPROVE / ESCALATE / FLAG) written to JSONL
- **ML Model:** Logistic Regression (`approval_classifier.pkl`)

---

## Demo Flow (5 Minutes)

```
[0:00-0:30]  Problem: Show 80% fraud stat, manual process pain, audit risk
[0:30-1:00]  Solution: Explain the Dual-Agent python flow with deterministic ML
[1:00-1:30]  Execution: Run `run_catas.py` in Terminal
[1:30-2:30]  Live Execution: Walk through the JSON outputs as they return
[2:30-3:30]  Results: Review the terminal output:
             - Treasury Anomaly Detections
             - Compliance Flags (EU Sanctions hits)
[3:30-4:00]  Accountability: Open `audit_log.jsonl` to show permanent record
[4:00-5:00]  Impact & Pitch: Private-by-design, immutable, deterministic
```

---

## Data You Need

### **Minimum Dataset for MVP:**
```
100 bank transactions (5 currencies, 10 counterparties, 3 entities)
  - 97 normal transactions
  - 3 anomalies (unusual amount, time, counterparty)
  - Include 1 OFAC-hit, 5 high-risk, 2 duplicate attempts

50 GL ledger entries (matching ~80% of bank transactions)

12 months historical data (1000 transactions) for ML training
  - Used to train anomaly detector, approval classifier, forecaster

5 compliance rules (JSON config):
  - OFAC sanctions check
  - Daily transaction limit per counterparty
  - High-amount approval workflow ($>100K = CFO sign-off)
  - Reportable transactions (SAR, CAT triggers)
  - Duplicate detection
```

---

## Key File Paths (Local Codebase)

```
Inputs & Models:
  - data/dataset.json (Raw financial JSON payloads)
  - models/anomaly_detector.pkl (Isolation Forest)
  - models/approval_classifier.pkl (Logistic Regression)
  - models/forecast_model.pkl (Prophet Time-Series)

Outputs & Orchestration:
  - run_catas.py (Dual-Agent Python Orchestrator)
  - .env (Lyzr Agent/API Keys + AWS Bedrock Configs)
  - SKILL.md files (Discrete tools like `parse-ledger-data`)
  - output/audit_log.jsonl (Permanent accountability record)
```

---

## ML Models (Quick Setup)

### **Model 1: Anomaly Detector (Treasury)**
```python
from sklearn.ensemble import IsolationForest
iso = IsolationForest(contamination=0.1, random_state=42)
iso.fit(X_historical)  # 1000 historical transactions
# Inference: score = iso.decision_function(X_new)
```

### **Model 2: Approval Classifier (Compliance)**
```python
from sklearn.linear_model import LogisticRegression
lr = LogisticRegression(max_iter=1000, random_state=42)
lr.fit(X_historical, y_approval)  # y = 1 if approved, 0 if escalated
# Inference: prob = lr.predict_proba(X_new)[0][1]
```

### **Model 3: Cash Flow Forecast (Treasury)**
```python
from statsmodels.tsa.arima.model import ARIMA
model = ARIMA(endog=daily_outflows, order=(1,1,1))
fitted = model.fit()
# Inference: forecast = fitted.get_forecast(steps=30)
```

---

## Critical Success Factors

### **Non-Negotiables:**
1. ✅ **Agent orchestration works natively in Python**
2. ✅ **Deterministic `.pkl` models execute before the LLM**
3. ✅ **Audit trail is complete** (every transaction has full decision history in `.jsonl`)
4. ✅ **Demo doesn't crash** (pre-test, have backup data)

### **Death Knells to Avoid:**
- ❌ Hallucinating fake outputs instead of using deterministic skill tools
- ❌ Execution times out due to sequential blocking
- ❌ Audit log doesn't match the LLM reasoning

---

## Judging Criteria You're Optimizing For

1. **Problem Validation:** Is this a real problem? (YES: 80% fraud, manual reconciliation pain, regulatory risk)
2. **Solution Fit:** Does your solution address the problem? (YES: Real-time validation, explainable rules, audit trail)
3. **Technical Depth:** Can you build this? (YES: Multi-agent orchestration, offline ML models, AWS Integrations)
4. **Scalability:** Will this work for real treasury teams? (YES: Evaluated by AgentCore memory and EU data sovereignty)

---

## Elevator Pitch Variants

**30 seconds (Very Short):**
> CATAS uses Dual-Agent AI to automate treasury and compliance. Instead of 20 hours of manual reconciliation, we do it in 5 minutes with full audit trails for regulators, using deterministic ML and strict AWS guardrails.

**90 seconds (Investors):**
> Manual treasury operations cost the finance industry billions in lost time, fraud, and penalties. CATAS is a dual-agent Python architecture running on Lyzr APIs. It automates transaction validation, compliance enforcement, and regulatory reporting in real-time. We orchestrate Treasury Operations and Compliance rule-sets grounded by hard mathematical models (Scikit-Learn). Target market: $15.15B treasury automation space, growing 12.84% annually.

**2 minutes (Technical Judges):**
> Treasury teams struggle with fragmented systems. CATAS solves this by deploying a dual-agent python orchestration layer on Lyzr. Agent 1 (Treasury) validates transactions utilizing Isolation Forest anomaly detection and time-series cash forecasts. Agent 2 (Compliance) applies EU Sanction rules using Logistic Regression classification and Bedrock Guardrails. `run_catas.py` chains the deterministic `.pkl` math directly into the RAG rule context. Finally, it uses strict tool triggers to write immutable audit trails. We process payloads instantly with zero hallucination.

---

## Quick Troubleshooting

| Problem | Fix |
|---------|-----|
| **Lyzr API Authentication Errors** | Check `.env` contains valid UUIDs for Agent IDs and correct `Bearer` token formatting. |
| **AWS Bedrock Guardrails failing** | Verify the Cross-Account IAM Role allows `bedrock:InvokeModel` for `eu-west-1`. |
| **`.pkl` load errors** | Make sure you are using Python 3.10+ and the sklearn versions perfectly match the training environment. |
| **Skill Name rejected** | Lyzr Studio UI requires kebab-case (e.g. `parse-ledger-data`) without spaces or underscores. |

---

## Links & Resources

- **Lyzr Agent Studio:** https://www.lyzr.ai
- **EU CBI Regulations:** https://www.centralbank.ie
- **sklearn Isolation Forest:** https://scikit-learn.org
- **Python `.env` Loaders:** https://pypi.org/project/python-dotenv/

---

## Checklist: Final Countdown to Pitch

- [ ] **Phase 1 & 2:** ML models trained, serialized (`.pkl`), Lyzr Studio UI generated Agent IDs
- [ ] **Phase 3:** Target `.env` file loaded in `run_catas.py` environment
- [ ] **Phase 4:** Terminal output color-coded and polished
- [ ] **Demo Prep (Before 8:45 PM):**
  - [ ] Terminal Demo script finalized, rehearsed 3x
  - [ ] Talking points ready (No presentation deck allowed)
  - [ ] Mention "Private-by-Design", EU Sovereignty, and Deterministic Skills

---

## Win Conditions (in priority order)

1. **Python script executes end-to-end without crashing**
2. **Terminal JSON output is easily readable for judges**
3. **Audit trail `.jsonl` proves structural accountability**
4. **Implementation proves offline ML grounding prevents hallucinations**
5. **Demonstrated strict integration of AWS Guardrails & AgentCore Memory**

