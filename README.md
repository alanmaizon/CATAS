# CATAS (Compliance And Treasurer Agentic Solutions)

A Multi-Agent System Design for Compliance & Treasury Automation built for the Lyzr Architect Hackathon.

## Overview
CATAS uses a Python-orchestrated Dual-Agent framework to solve the reconciliation bottleneck, the audit-trail gap, and the treasury-compliance silo. 

The system utilizes deterministic offline ML models to ground LLM reasoning across two distinct operations:
- **Agent 1:** Treasury Operations (Isolation Forest Anomaly Detection & Prophet Time-Series Forecasts)
- **Agent 2:** Compliance Operations (Logistic Regression EU Sanction filtering & Immutable Audit Log generation)

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
   pip install -r orchestration/requirements.txt
   ```

## Pre-Hackathon Pipeline (Data & Offline ML)
To ensure reliable performance during the hackathon, we are using synthesized data and offline-trained ML models. These must be prepared *before* the live event.

1. **Generate Data:**
   Run the data generation script to build synthetic historical data, GL balances, and the live demo dataset.
   ```bash
   # Synthetic data already pre-loaded into /data/ directory
   ```

2. **Train Models:**
   Train and serialize the Machine Learning `.pkl` models based on the offline synthetic data.
   ```bash
   # Offline Models already serialized in /models/ directory
   ```

## Live Execution Pipeline (Hackathon Demo)

CATAS runs seamlessly using a custom Python script that strings together the Offline ML Models with the live Lyzr Agent API.

1. **Set your API Keys:**
   Create a `.env` file in the root directory:
   ```bash
   LYZR_API_KEY="your-api-key"
   LYZR_TREASURY_AGENT_ID="treasury-id"
   LYZR_COMPLIANCE_AGENT_ID="compliance-id"
   ```

   - `LYZR_API_KEY` — from Lyzr Studio → Settings → API Keys.
   - `LYZR_TREASURY_AGENT_ID` / `LYZR_COMPLIANCE_AGENT_ID` — the IDs of the two agents you create in Lyzr Studio. Each ID appears in the agent's URL (`studio.lyzr.ai/agent/<ID>`).

   The exact agent configuration (name, model, role, goal, instructions) is documented step-by-step in [docs/CATAS_Architect_Setup_Guide.md §2](docs/CATAS_Architect_Setup_Guide.md). Without these three variables set, `run_catas.py` automatically falls back to mock mode. See [orchestration/.env.example](orchestration/.env.example) for the full list of supported variables (webhook alerts, AWS SES, path overrides).

2. **Run the Orchestrator:**
   To run the script in deterministic Mock mode (no Lyzr Credits required):
   ```bash
   python orchestration/run_catas.py --mode mock
   ```

   To run the script against the live Lyzr API:
   ```bash
   python orchestration/run_catas.py --mode live --limit 5
   ```

3. **View the Dashboard:**
   To visualize the generated `/logs/audit_trail.txt`, load it into the **Architect Beta (`architect.new`)** UI dashboard!

## Hackathon Phases & Roles

- **Data Scientist/ML Engineer:** Responsible for features, data schema, and predictive analytics.
- **Platform/Orchestration Engineer:** Responsible for Python integration, Lyzr API orchestration, AWS Guardrails, and Architect.new UI display.

*See `docs/CATAS_Hackathon_Roadmap.md` for specific timelines and event details.*