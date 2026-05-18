# Internal AML & Treasury Operations Policy — Republic of Ireland

**Document ID:** CATAS-RAG-POL-002
**Policy Owner:** Group Treasury & Financial Crime Compliance
**Approved By:** Money Laundering Reporting Officer (MLRO) and Board Risk Committee
**Effective Date:** 2026-04-01
**Last Revised:** 2026-05-18 (v1.1)
**Review Cycle:** Annual; ad-hoc following any material legislative amendment.
**Legal Basis:**
- Criminal Justice (Money Laundering and Terrorist Financing) Act 2010 ("CJA 2010"), as amended by the 2013, 2018, and 2021 Acts.
- Central Bank of Ireland AML/CFT Guidelines for the Financial Sector (current edition).
- EU Directive 2015/849 (4AMLD) and Directive (EU) 2018/843 (5AMLD).
- Regulation (EU) 2015/847 on information accompanying transfers of funds.

**Classification:** INTERNAL — Treasury, Compliance, and Audit personnel only.

---

## 1. Scope and Applicability

This Standard Operating Procedure ("SOP") applies to **all outbound and inbound payment instructions** processed by the Group Treasury function of the Irish-domiciled entity, including but not limited to:

- SEPA Credit Transfers (SCT) and SEPA Instant (SCT Inst), classified in source systems as `ach_transfer`.
- SWIFT MT103 / pacs.008 cross-border wires, classified in source systems as `wire_payment`.
- Intra-group sweeps and internal book transfers, classified in source systems as `internal_transfer`.
- All vendor settlements, payroll disbursements, and refund disbursements, regardless of rail.

The CATAS Compliance Agent operationalises the rules below as automated pre-settlement controls. Manual operator override is **only** permitted under the conditions in §6.

---

## 2. Governing Principles

1. **Risk-based approach** — controls scale with transaction risk in line with CJA 2010 §30A.
2. **Four-eyes principle** — no single individual may both initiate and approve a payment above defined thresholds.
3. **Auditability** — every control decision (block, hold, release, override) is logged with rule ID, evidence, and decision-maker identity for a minimum of **5 years** per CJA 2010 §55.
4. **Human-in-the-loop** — automated agents may RECOMMEND and BLOCK, but RELEASE of any held or escalated transaction requires a named human approver.
5. **Currency neutrality** — all monetary thresholds in this SOP are expressed in EUR. The Compliance Agent MUST convert non-EUR amounts to EUR using the canonical FX feed (§3 Rule 1) before evaluating any threshold-based rule.

---

## 3. Mandatory Control Rules

### Rule 1 — Large-Value Transfer Threshold (Level 2 ACE-V Protocol)

**Trigger:** Any single outbound `wire_payment`, `ach_transfer`, or `internal_transfer` whose **EUR-equivalent settlement value exceeds €50,000**.

**FX Normalisation (mandatory pre-evaluation step):** Non-EUR amounts MUST be converted to EUR using the ECB reference rate dated `T-1` (previous business day) prior to evaluating this rule. The Compliance Agent reads the rate from the canonical `data/fx_rates.csv` feed (columns: `date, currency, rate_to_eur, source`):

```
eur_equivalent = amount × rate_to_eur(currency, T-1)
```

If no rate is published for a given currency on `T-1` (e.g., bank holiday or weekend), the most recent prior published rate is used and the substitution is recorded in the audit log. For `currency = EUR`, `rate_to_eur = 1.0` (identity conversion).

**Action Required:** Hold transaction pre-settlement and route to **Level 2 ACE-V Protocol Review**.

**Level 2 ACE-V Protocol Review consists of:**
- **A** — *Authenticate*: re-verify the counterparty record (`counterparty_id`, `counterparty_name`) against the master vendor file; reject if last verification > 90 days old.
- **C** — *Corroborate*: match the payment to an open purchase order, signed contract, or board-approved capital instruction; the PO or contract reference must be present in the `reference` field of the payment instruction.
- **E** — *Evaluate*: assess the counterparty against the [[EU_Sanctions_and_CBI_Watchlist_Mock]] register; if any match, Rule 2 supersedes this rule.
- **V** — *Validate*: sign-off by two named approvers, at least one of whom is a Treasury Manager (Grade T3 or above). Approvals captured in the audit log.

**Cycle Time SLA:** ACE-V review must complete within 4 working hours during the SEPA settlement window; transactions submitted after 14:00 IST are deferred to next business day.

**Exception Handling:** Emergency same-day overrides require the written authorisation of the Group Treasurer **and** the MLRO; emergency overrides are reported to the Board Risk Committee at the next scheduled meeting.

---

### Rule 2 — Sanctions Screening and Automatic Block

**Trigger:** Any transaction (any amount, any direction, any currency) where the counterparty matches an entry in the [[EU_Sanctions_and_CBI_Watchlist_Mock]] register. Active match types:

- **Exact** match on `counterparty_id` against the listed entity IDs (e.g., `CP-9471`).
- **Exact or fuzzy** match on `counterparty_name` (similarity ≥ 0.92) against designated persons, entities, or known aliases in §2–§3 of the sanctions register.
- **Substring** match in the payment `reference` field containing any listed alias.

> *Note:* IBAN and BIC pattern matching is documented in the sanctions register (§5.1) for forward compatibility, but is **not currently active** because the bank-feed source system (`bank_transactions_input_v2.json`) does not emit IBAN/BIC fields. Activation is contingent on the ISO 20022 enrichment scheduled for FY27.

**Action Required:**
1. **Automatic block** at the payment-orchestration layer. The transaction MUST NOT reach the SEPA scheme or SWIFT network.
2. **Immediate MLRO Investigation** — the Compliance Agent opens a case ticket assigned to the MLRO with priority `P1-URGENT`. The case ticket must include:
   - The matched register entry (Entity ID, EU reference).
   - Full payment instruction payload (sanitised of unnecessary PII).
   - Match confidence score and the specific pattern (`counterparty_id`, name, or reference substring) that triggered the block.
   - Recommended next steps (typically: freeze pending Suspicious Transaction Report (STR) submission to the Financial Intelligence Unit Ireland (FIU-IE) and Revenue Commissioners).
3. **Reporting obligation** — where the MLRO concludes a suspicion is formed, an STR must be filed via the FIU-IE secure portal **without delay** per CJA 2010 §42.
4. **Tipping-off prohibition** — under CJA 2010 §49, no employee may disclose to the counterparty (or any third party) that an investigation or report is in progress.

**No override permitted.** Rule 2 blocks cannot be released by anyone other than the MLRO, and only following documented investigation outcomes.

---

### Rule 3 — Payment-vs-Baseline Variance Control

**Trigger:** Any outbound payment whose EUR-equivalent settlement amount deviates from the **rolling 90-day mean** of EUR-equivalent payments to the same `counterparty_id` and same `transaction_type` by more than **2.00%**, calculated as:

```
baseline_eur  = mean( eur_equivalent[t]
                      for t in prior 90 days
                      where counterparty_id == c AND transaction_type == tt )

variance_pct  = abs(eur_equivalent − baseline_eur) / baseline_eur × 100
```

The baseline is sourced from `data/historical_transactions_v2.csv`, with each historical row converted to EUR using `data/fx_rates.csv` (rate dated on the historical transaction's own `date`, or nearest prior). If fewer than 5 prior transactions exist for the (`counterparty_id`, `transaction_type`) pair, this rule is suspended and the transaction is auto-routed to **AP Lead for first-time-payee review** instead.

**Rationale:** Originally a payment-vs-invoice variance check, this rule was refactored when the upstream procurement system stopped emitting invoice amounts on the payment instruction. Baseline-deviation analysis covers the same fraud typologies (BEC, invoice manipulation, unauthorised contract amendment) by detecting payments that are anomalously large or small relative to the counterparty's historical pattern.

**Action Required:**

| Variance Band | Action |
|---|---|
| ≤ 2.00% | Auto-approve (subject to all other rules). |
| > 2.00% and ≤ 5.00% | **Hold for manual sign-off** by Accounts Payable Lead; documented justification required (FX adjustment, partial credit note, agreed early-settlement discount, etc.). |
| > 5.00% | Escalate to Treasury Manager (Grade T3+) **and** trigger an automated query to the procurement system to confirm no duplicate-payment or BEC pattern. |
| `eur_equivalent` ≥ 2 × `baseline_eur` (extreme positive variance) | Hold and require written justification regardless of band; commonly indicative of overpayment fraud or duplicate-settlement error. |

---

### Rule 4 — Counterparty Risk Score Threshold

**Trigger:** Any transaction whose counterparty has a `counterparty_risk_score ≥ 0.85` in the master counterparty record (sourced from `data/historical_transactions_v2.csv`), **regardless of amount or currency**.

**Rationale:** A high risk score reflects accumulated negative signals over time — prior anomalies (`is_anomaly = 1`), adverse media, regulatory flags, or a history of rejected approvals (`approved = 0`). Under the risk-based approach mandated by CJA 2010 §30A, a high-risk counterparty warrants enhanced scrutiny even on routine-size payments, because layering and structuring typologies frequently use small, frequent transfers to stay below large-value thresholds.

**Score-band actions:**

| `counterparty_risk_score` | Action |
|---|---|
| < 0.50 | Standard processing (subject to all other rules). |
| 0.50 ≤ score < 0.85 | Soft flag in audit log; no hold. Reviewed at quarterly counterparty re-rating. |
| 0.85 ≤ score < 0.95 | **Hold for EDD** by Treasury Manager (Grade T3+). |
| ≥ 0.95 | **Hold + auto-escalate to MLRO** regardless of sanctions match status. |

**EDD case requirements (for the 0.85 ≤ score < 0.95 band):**
1. Refreshed source-of-funds evidence.
2. Refreshed beneficial ownership confirmation.
3. Documented business rationale for the specific payment.
4. Confirmation that the counterparty is not on the [[EU_Sanctions_and_CBI_Watchlist_Mock]] (Rule 2 supersedes if matched).
5. Treasury Manager sign-off recorded in the audit trail.

**Rule interaction:** Rule 4 stacks additively with Rule 1 (a high-risk-score transaction above €50,000 still requires ACE-V *and* EDD) and is superseded by Rule 2 (a sanctions match short-circuits to immediate block; no EDD path needed).

---

## 4. Roles and Responsibilities

| Role | Responsibility |
|---|---|
| **Payment Initiator (T1–T2)** | Submits payment with complete reference data; cannot self-approve above €10,000 EUR-equivalent. |
| **Accounts Payable Lead** | Reviews Rule 3 variance holds within 1 business day; reviews first-time-payee transactions (Rule 3 suspension condition). |
| **Treasury Manager (T3+)** | Provides the second approval under ACE-V "V" step; signs off Rule 4 EDD holds; cannot approve own initiations. |
| **MLRO** | Sole authority for Rule 2 case adjudication, STR filing, and unblock decisions. Also handles Rule 4 ≥ 0.95 escalations. |
| **CATAS Compliance Agent** | Enforces Rules 1–4 automatically using `data/fx_rates.csv` and `data/historical_transactions_v2.csv` as canonical reference data; produces audit trail; never executes a release without a human approver. |
| **Internal Audit** | Quarterly sample testing of overrides; reports exceptions to the Board Risk Committee. |

---

## 5. Audit Trail Requirements

Every payment that traverses the CATAS pipeline must produce an immutable record containing, at minimum:

- Transaction ID, timestamp (UTC and IST), original `amount`, original `currency`, computed `eur_equivalent`, FX rate used, FX rate source date, `counterparty_id`, `counterparty_name`.
- Rule(s) evaluated and outcome (`PASS` / `HOLD` / `BLOCK`).
- For Rule 3: `baseline_eur` value and computed `variance_pct`.
- For Rule 4: `counterparty_risk_score` value retrieved.
- Identity of any human approver(s) and timestamp of approval action.
- Evidence references (PO number, contract ID, sanctions register version hash, FX feed version hash).
- Final disposition (`SETTLED`, `CANCELLED`, `REFERRED-MLRO`).

Records are retained for **5 years from the date of the last transaction** with the counterparty, per CJA 2010 §55, and made available to the Central Bank of Ireland on request.

---

## 6. Override and Exception Policy

Manual overrides are permitted **only** for Rule 1, Rule 3, and Rule 4 holds, and only under the following conditions:

1. Written justification recorded in the audit log.
2. Sign-off by an authority one grade higher than would normally approve.
3. Same-day notification to the MLRO and Internal Audit.
4. Inclusion in the quarterly override report to the Board Risk Committee.

**Rule 2 (sanctions) blocks are non-overridable** outside the MLRO investigative process.

---

## 7. Training and Attestation

- All Treasury and Finance staff must complete annual AML/CFT training certified by the Compliance Institute (or equivalent) and attest to this SOP.
- New hires must complete training within 30 days of start date and may not exercise approval authority until training is logged.

---

## 8. Cross-References

- [[EU_Sanctions_and_CBI_Watchlist_Mock]] — designated persons, entities, and high-risk corridors referenced by Rule 2.
- `data/fx_rates.csv` — canonical FX feed used by Rule 1 and Rule 3.
- `data/historical_transactions_v2.csv` — source of Rule 3 baselines and Rule 4 `counterparty_risk_score`.
- *Group Code of Conduct* — fraud reporting and whistleblower channels.
- *Information Security Policy* — handling of PII and payment data under GDPR.

---

## 9. Document Control

| Version | Date | Author | Change Summary |
|---|---|---|---|
| 1.0 | 2026-04-01 | Head of Financial Crime Compliance | Initial issuance for CATAS demonstration tenant. |
| 1.1 | 2026-05-18 | Head of Financial Crime Compliance | Aligned policy with v2 mock dataset. Rule 1 reframed with explicit FX normalisation against `data/fx_rates.csv`. Rule 2 matching keys switched from IBAN/BIC to `counterparty_id` / `counterparty_name` (IBAN/BIC retained as inactive forward-state in sanctions register §5.1). Rule 3 refactored from invoice-variance to rolling-90-day baseline variance using `historical_transactions_v2.csv`. Added Rule 4 (counterparty risk score threshold). Updated §1 scope to reference the three `transaction_type` enums emitted by the source feed. |
