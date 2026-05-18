# CATAS - Hackathon Pitch Script

**Target Time:** 3-4 Minutes  
**Tone:** Confident, visionary, enterprise-grade, ecosystem-aware.

---

### [Intro - The Hook] (0:00 - 0:45)

**Speaker:** 
"We are here at Baseline this weekend to bridge the gap between autocomplete and autonomous workflows. But in the financial sector, there is an even bigger gap: the gap between Treasury and Compliance.

Fraud is not just a problem of bad actors. It’s a problem of broken substrates. 

Today, Treasury and Compliance teams sit one floor apart but operate in entirely different realities. When a suspect transaction hits, teams spend up to 20 hours a month manually cross-referencing spreadsheets and general ledgers just to reconcile the data, let alone confidently stop the fraud. 

This isn't a problem we can solve by just adding another detection tool. It’s an architectural failure. The gaps between our disconnected systems are exactly where fraudsters hide. 

That is why we used the Lyzr Architect framework to build **CATAS**—a cross-application autonomous workforce for Compliance and Treasury."

### [The Ecosystem Flex - Demonstrating Lyzr Knowledge] (0:45 - 1:45)

**Speaker:**
"If you look at the landscape today, we have some incredible components. 

On the community side, in the **Lyzr Architect Beta**, we see brilliant, highly specialized point-solutions like *Fraud-Orchestrate* and *Trade-Pilot*. But they operate in isolation.

On the enterprise side, **Lyzr Agent Studio** provides powerhouse tools—like the *Banking Refund Management Agent*, the *Claims Processing Agent*, and the *Teller Assistance Agent*. These are massive leaps forward in operational efficiency. 

But if you deploy them as stand-alone silos, a human still has to sit in the middle, staring at three different screens trying to answer one question: *'Did treasury and compliance actually agree on this transaction?'*

**CATAS doesn't compete with these tools; it is the enterprise substrate that harnesses them.**"

### [The Solution - How CATAS Works] (1:45 - 2:45)

**Speaker:**
"CATAS acts as the unified, multi-agent layer utilizing Lyzr's powerful architecture. 

When a transaction is initiated, our system doesn't just scan it post-transaction. It triggers a real-time, adversarial analysis using Lyzr's 'private-by-design' architecture. 

- Before any data hits the core LLM, **AWS Bedrock Guardrails** instantly redact PII like IBANs and client names natively, guaranteeing zero data leakage.
- Agent 1 handles the Treasury context, executing our custom **`parse-ledger-data`** skill to securely ingest and reconcile the bank feeds without exploding the context window.
- Agent 2 then takes that parsed data and queries our **Regulatory Monitoring Agent** — a Lyzr Knowledge Assistant built on the EU's Consolidated Financial Sanctions feed and the Central Bank of Ireland's published AML guidance — so every rule the agent enforces traces back to the actual regulator's source.
- Underpinning it all is Lyzr's ACE-V protocol (Authenticate, Corroborate, Evaluate, Validate), which ensures that every action is secure and explainable.

When an anomaly is flagged, the agent dynamically executes our **`trigger-mlro-alert`** skill to instantaneously route a structured case to the compliance officer in Slack or PagerDuty. Simultaneously, it fires the **`write-audit-log`** skill, saving a perfectly synthesized, immutable audit record locally before the human even opens the ticket.

But what makes this truly autonomous is our use of **Amazon Bedrock AgentCore Memory**. Because our memory is deployed locally in AWS Ireland via cross-account role assumption, the platform securely remembers past MLRO variances across sessions. It eliminates repetitive false-positives without ever breaking data residency rules.

Every decision, whether approved or blocked, carries a verifiable cryptographic attestation. We are replacing a 3-week post-mortem audit process with real-time, explainable, structural accountability."

### [The Results & Close] (2:45 - 3:30)

**Speaker:**
"In the last 48 hours, we proved this works. We ran 100 localized, simulated transactions through CATAS. 
- We reduced a standard 20-hour manual reconciliation process down to 5 minutes. 
- We achieved a 97% auto-match rate, with 100% audit-trail coverage on every flagged anomaly.

We aren't just presenting an app today. We are presenting the blueprint for a fraud-resistant financial infrastructure built natively on the Lyzr multi-agent ecosystem. 

Thank you."