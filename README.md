# CATAS (Compliance And Treasurer Agentic Solutions)

A Multi-Agent System Design for Compliance & Treasury Automation built for the Lyzr Architect Hackathon.

## Overview
CATAS uses a multi-agent framework to solve the reconciliation bottleneck, the audit-trail gap, and the treasury-compliance silo. 

The system consists of a Manager Agent coordinating 5 sub-agents:
- **Agent 1:** Transaction Validator & Normalizer (Isolation Forest Anomaly Detection)
- **Agent 2:** Compliance Rules Engine (Logistic Regression)
- **Agent 3:** Treasurer Position & Risk (ARIMA Forecast)
- **Agent 4:** Reconciliation & Matching Engine
- **Agent 5:** Regulatory Reporting & Audit Trail

## Prerequisites
- Python 3.10+
- Lyzr Architect account / access
- Dependencies from `requirements.txt`

## Collaborator Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd CATAS
   ```

2. **Set up a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Pre-Hackathon Pipeline (Data & Offline ML)
To ensure reliable performance during the hackathon, we are using synthesized data and offline-trained ML models. These must be prepared *before* the live event.

1. **Generate Data:**
   Run the data generation script to build synthetic historical data, GL balances, and the live demo dataset.
   ```bash
   python scripts/generate_data.py
   ```
   *Outputs will be placed in the `/data/` directory.*

2. **Train Models:**
   Train and serialize the Machine Learning `.pkl` models based on the offline synthetic data.
   ```bash
   python scripts/train_models.py
   ```
   *Outputs will be placed in the `/models/` directory.*

## Hackathon Phases & Roles

- **Data Scientist/ML Engineer:** Responsible for features, data schema, and predictive analytics.
- **Platform/Orchestration Engineer:** Responsible for Lyzr Architect orchestration, agent workflows, and the UI layout.

*See `CATAS_Hackathon_Roadmap.md` for specific timelines and event details.*