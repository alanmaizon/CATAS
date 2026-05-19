# Architect Beta Reproducibility Guide for CATAS Dashboard

This document outlines the exact steps, prompts, and configurations required to recreate the CATAS Dual-Agent Command Center dashboard in Architect Beta (`architect.new`).

---

## 1. Initial Prompt & App Generation
When you first open Architect Beta, paste the following prompt into the main text box. **Before submitting**, attach these two files to give the AI schema context:
*   `data/bank_transactions_input.json`
*   `logs/audit_trail.jsonl`

**Prompt to copy/paste:**
> Build an enterprise-grade "CATAS Dual-Agent Command Center" dashboard. I have a Python backend that processes financial transactions using two AI agents: a Treasury Agent (Isolation Forest ML) and a Compliance Agent (CBI/EBA Sanctions Rules). I need a UI to visualize the output data from the attached `audit_trail.jsonl` file. 
> Please include: 
> 1. Top KPI Metrics: Total Transactions Processed, Total Volume (EUR), Treasury Anomalies Detected, and Compliance Blocks/Holds. 
> 2. Transaction Ledger (Table): A data table displaying Transaction ID, Counterparty, Amount, and the Final Decision. Color-code the decisions: APPROVE (Green), HOLD (Yellow), BLOCK (Red). 
> 3. Immutable Audit Trail Viewer: When a user clicks on a row in the table, open a side panel or modal. This must display the exact rules_evaluated array, the evidence strings, and critically, the audit_chain_hash to prove cryptographic accountability. 
> 4. Design: Make it look like a sleek, high-end financial terminal (dark mode preferred). Add a button at the top that says "Export MLRO Alert (PDF)" that triggers a simple success toast notification.

### Discovery Phase Questionnaire
The Requirements Agent will ask clarifying questions. Provide these exact answers:
1. **Real-Time Data Updates:** Select `Historical review — Dashboard loads and displays the existing audit trail file`
2. **User Interaction & Drill-Down:** Select `Filtering by decision type` AND `Counterparty search`
3. **Database Requirements:** Select `No — Dashboard reads directly from the JSONL file with no persistent user data`

---

## 2. Lyzr Agent Studio Configurations
The dashboard backend connects to the Lyzr Agent Studio API. You must manually create these two agents in the Lyzr Studio UI (`https://studio.lyzr.ai/agent-create/`) and copy their generated Agent IDs.

### Agent 1: Treasury Operations
*   **Name:** `Treasury Agent`
*   **Description:** `Evaluates transactions for liquidity risk and anomalies using ML inputs.`
*   **Model:** `gpt-4o-mini`
*   **Agent Role:** `You are the primary Treasury Operations Agent for CATAS.`
*   **Agent Goal:** `Your goal is to validate incoming financial transactions by assessing the deterministic anomaly and liquidity scores provided to you by offline scikit-learn ML models.`
*   **Agent Instructions:** 
    ```text
    1. EXAMINE the incoming payload and the ML scores.
    2. EXECUTE the 'parse-ledger-data' skill to validate the formatting.
    3. STRUCTURE a concise summary payload of the risk.
    4. DO NOT hallucinate data; rely strictly on the incoming numbers.
    ```
*(Leave Manager Agent toggle OFF. Save and copy the Agent ID.)*

### Agent 2: Compliance Operations
*   **Name:** `Compliance Agent`
*   **Description:** `Applies CBI/EBA rule sets and enforces EU sanctions.`
*   **Model:** `gpt-4o-mini`
*   **Agent Role:** `You are the primary Compliance Agent for CATAS.`
*   **Agent Goal:** `Your goal is to perform strict regulatory compliance checks against EU Sanctions (CBI/EBA) and generate an immutable audit log.`
*   **Agent Instructions:** 
    ```text
    1. RECEIVE the summarized payload from the Treasury Agent.
    2. EVALUATE the ML-derived 'approval probability'.
    3. IF a transaction violates sanctions or fails the ML threshold, EXECUTE the 'trigger-mlro-alert' skill.
    4. FOR EVERY transaction, EXECUTE the 'write-audit-log' skill to maintain structural accountability.
    ```
*(Leave Manager Agent toggle OFF. Save and copy the Agent ID.)*

**Backend `.env` file configuration:**

These three variables tell `orchestration/run_catas.py` how to reach your Lyzr Studio agents. The keys are read in [orchestration/run_catas.py:52-53](orchestration/run_catas.py#L52-L53); the names must match exactly (with the `LYZR_` prefix) or the live pipeline will fall back to mock mode.

```env
# Lyzr Studio → Settings → API Keys
LYZR_API_KEY="your-lyzr-api-key"

# The Agent IDs you copied from the two agents above.
# Find them again in Lyzr Studio at studio.lyzr.ai/agent/<ID>.
LYZR_TREASURY_AGENT_ID="copied-treasury-uuid"
LYZR_COMPLIANCE_AGENT_ID="copied-compliance-uuid"
```

Save this file as `.env` at the **repository root** (not inside `docs/` or `orchestration/`). It is git-ignored. A template with every supported variable lives at [orchestration/.env.example](orchestration/.env.example).

---

## 3. UI Tweaks & Adjustments (Post-Generation)
Once the Architect UI finishes its initial build, paste these follow-up prompts one by one into the Architect chat panel to refine the application:

**Prompt 1 (Responsiveness):**
> "Please update the CSS and responsiveness of the Dashboard. Make sure the TransactionLedger table is fully scrollable horizontally on smaller screens, and that the text doesn't overflow or clip. Ensure the KpiStrip cards stack neatly (2x2 or 1x4) on mobile devices using Tailwind grid or flexbox rules. Give the AuditPanel a smooth slide-in animation from the right side, and ensure the audit_chain_hash text breaks properly so it doesn't break the layout. Double-check that the HeaderBar and floating ChatDrawer are fixed and don't overlap awkwardly on smaller browser windows."

**Prompt 2 (Chat Formatting):**
> "Update the ChatDrawer UI to ensure that the Treasury and Compliance Insights Agents render their responses as flowing conversational text instead of structured JSON objects. Parse the underlying JSON returned by the agents so that any summaries or details are displayed naturally in standard chat bubbles. The underlying data payload should still be preserved for the PDF export feature, but the user-facing chat should read like a normal, human-readable conversation."

---

## 4. Final Knowledge Base Upload

The dashboard's internal agents need to read the backend's output. The "Knowledge Base" widget inside the Architect Beta app builder connects directly to the core Lyzr Agent Studio Knowledge Base APIs. 

You have two options for loading the data:

### Option A: Upload as a Text File
Because the basic file uploader only accepts `PDF`, `DOCX`, and `TXT` files, you must convert the `.jsonl` audit trail into a `.txt` file before uploading.

Run this in the terminal:
```bash
python3 -c "import json; [print(json.dumps(json.loads(line), indent=2)) for line in open('logs/audit_trail.jsonl')]" > logs/audit_trail.txt
```
Then click **Upload Files** underneath both the Treasury and Compliance Insights Agents within the Architect UI and upload `logs/audit_trail.txt`.

### Option B: Paste as Raw Text
Alternatively, you can skip the file conversion entirely:
1. Open `logs/audit_trail.jsonl` in your code editor and copy all the text.
2. In the Architect Beta UI, select **Add Text** under the Knowledge Base configuration.
3. Paste the raw JSONL contents directly into the prompt box.

Once the Knowledge Base is populated using either method, click **Preview** to view the finished, fully interactive dashboard!