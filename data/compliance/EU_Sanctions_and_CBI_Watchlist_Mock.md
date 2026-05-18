# EU Consolidated Financial Sanctions List & CBI Watchlist (Mock Extract)

**Document ID:** CATAS-RAG-SANCT-001
**Issuing Authorities (Referenced):** Council of the European Union; Central Bank of Ireland (CBI); Financial Intelligence Unit Ireland (FIU-IE)
**Legal Basis:** Council Regulation (EU) No 2580/2001; Council Regulation (EC) No 881/2002; Criminal Justice (Money Laundering and Terrorist Financing) Act 2010, as amended.
**Effective Date:** 2026-04-01
**Last Revised:** 2026-05-18 (v1.1)
**Review Cycle:** Weekly (Mondays, 08:00 IST)
**Classification:** RESTRICTED — Internal Compliance Use Only

---

## 1. Purpose

This document provides a consolidated extract of designated persons, entities, and jurisdictions subject to restrictive financial measures under EU sanctions regimes and supplementary Central Bank of Ireland (CBI) advisories. It is the authoritative reference list for screening by the CATAS Compliance Agent.

Each designated entry carries a `counterparty_id` (format `CP-9xxx`) that maps directly to identifiers used in the source bank feed (`data/bank_transactions_input_v2.json`) and the master historical record (`data/historical_transactions_v2.csv`).

**Any pattern match against the identifiers below MUST trigger an automatic transaction block and escalation per [[Internal_AML_Treasury_Policy_Ireland]] Rule 2.**

---

## 2. Designated Sanctioned Entities (Corporate / Shell Companies)

### 2.1 Entity: BoreasTrade Holdings LLP
- **Entity ID (CATAS):** SANCT-ENT-00471
- **counterparty_id (active match key):** `CP-9471`
- **EU Reference:** EU.CFSP.2025.0991
- **Jurisdiction of Registration:** Nicosia, Cyprus (front company; ultimate beneficial owner located in high-risk jurisdiction)
- **Listing Reason:** Funnelling proceeds linked to dual-use export evasion.
- **IBAN Prefix (future ISO 20022 match key):** `CY17 0030 0014 0000`
- **BIC (future):** `BRSTCY2NXXX`
- **Aliases:** "Boreas Trading Ltd.", "BT Holdings Cyprus"

### 2.2 Entity: Volkov Maritime Services AG
- **Entity ID (CATAS):** SANCT-ENT-00488
- **counterparty_id (active match key):** `CP-9488`
- **EU Reference:** EU.CFSP.2025.1107
- **Jurisdiction of Registration:** Zug, Switzerland (shell)
- **Listing Reason:** Provision of logistical support to sanctioned shipping operators.
- **IBAN Prefix (future):** `CH93 0076 2011 6238`
- **BIC (future):** `VLKMCHZZXXX`
- **Aliases:** "Volkov Marine", "VMS Holdings"

### 2.3 Entity: Crescent Star Petrochemicals FZE
- **Entity ID (CATAS):** SANCT-ENT-00502
- **counterparty_id (active match key):** `CP-9502`
- **EU Reference:** EU.CFSP.2026.0044
- **Jurisdiction of Registration:** Fujairah Free Zone, UAE
- **Listing Reason:** Sanctions circumvention via opaque petroleum cargo re-flagging.
- **IBAN Prefix (future):** N/A (non-IBAN jurisdiction)
- **BIC (future):** `CSPCAEFJXXX`
- **Aliases:** "Crescent Star Petrochem", "CSP FZE"

### 2.4 Entity: Atlas Northern Commodities OÜ
- **Entity ID (CATAS):** SANCT-ENT-00519
- **counterparty_id (active match key):** `CP-9519`
- **EU Reference:** EU.CFSP.2026.0118
- **Jurisdiction of Registration:** Tallinn, Estonia (registered address vacated; presumed shell)
- **Listing Reason:** Layering of funds linked to ransomware proceeds.
- **IBAN Prefix (future):** `EE38 2200 2210 2014`
- **BIC (future):** `ATNCEE22XXX`
- **Aliases:** "Atlas North Commodities"

---

## 3. Designated Sanctioned Individuals

### 3.1 Individual: Dmitri A. Ostrovsky
- **Entity ID (CATAS):** SANCT-IND-00211
- **counterparty_id (active match key):** `CP-9211`
- **EU Reference:** EU.CFSP.2025.1042
- **DOB:** 1971-08-14
- **Nationality:** Russian Federation
- **Listing Reason:** Beneficial owner of multiple shell entities (incl. Volkov Maritime Services AG).
- **Known Account Identifiers (future):** Personal IBAN `CH93 0076 2011 6238 4427 1` (also matches §2.2 prefix).

### 3.2 Individual: Layla H. Mansoor
- **Entity ID (CATAS):** SANCT-IND-00238
- **counterparty_id (active match key):** `CP-9238`
- **EU Reference:** EU.CFSP.2026.0091
- **DOB:** 1983-02-26
- **Nationality:** Iranian / dual UAE residency
- **Listing Reason:** Director of Crescent Star Petrochemicals FZE; sanctions evasion.
- **Known Account Identifiers (future):** No EU-domiciled accounts on file; screen by name + DOB.

### 3.3 Individual: Sergei V. Pavlenko
- **Entity ID (CATAS):** SANCT-IND-00247
- **counterparty_id (active match key):** `CP-9247`
- **EU Reference:** EU.CFSP.2026.0133
- **DOB:** 1968-11-03
- **Nationality:** Belarusian
- **Listing Reason:** Facilitator of cross-border cash smuggling; designated under terrorism-financing provisions.
- **Known Account Identifiers (future):** Personal IBAN `EE38 2200 2210 2014 0096 3`

---

## 4. High-Risk Jurisdictions (Non-SEPA Banking Corridors)

The following corridors are documented as **advisory context**. They are not currently actionable on the source bank feed, because the feed does not yet emit jurisdiction-of-routing or correspondent-bank fields. They become active once ISO 20022 enrichment lands (planned FY27). Until then, jurisdiction risk is captured indirectly via `counterparty_risk_score` ([[Internal_AML_Treasury_Policy_Ireland]] Rule 4).

### 4.1 Corridor: Caspian Transit Corridor (CTC)
- **Corridor Code (CATAS):** HRJ-CTC-01
- **Countries Covered:** Turkmenistan, Uzbekistan, Azerbaijan, Tajikistan
- **SWIFT BIC Country Prefixes (future):** `TM*`, `UZ*`, `AZ*`, `TJ*`
- **Risk Drivers:** Opaque beneficial ownership registers; weak AML supervision (FATF grey-list adjacent); historic exposure to oil-and-gas sanctions evasion.
- **Required Action (when active):** Hold for MLRO review; complete EDD questionnaire CBI-EDD-04 before release.

### 4.2 Corridor: West Balkan Shadow Corridor (WBSC)
- **Corridor Code (CATAS):** HRJ-WBSC-02
- **Countries Covered:** Republic of North Macedonia (high-risk segments), Kosovo, Montenegro, Bosnia and Herzegovina (designated regions)
- **SWIFT BIC Country Prefixes (future):** `MK*`, `XK*`, `ME*`, `BA*`
- **Risk Drivers:** Cash-economy concentration; documented trade-based money laundering (TBML) typologies; correspondent-bank de-risking gaps.
- **Required Action (when active):** Mandatory source-of-funds documentation; MLRO sign-off prior to settlement.

---

## 5. Pattern-Matching Index (Active Keys — Primary for RAG Retrieval)

These are the keys the Compliance Agent uses **today**, against the fields present in `bank_transactions_input_v2.json` and `historical_transactions_v2.csv`:

| Pattern Type | Value | Linked Entry | Action |
|---|---|---|---|
| `counterparty_id` exact | `CP-9471` | SANCT-ENT-00471 (BoreasTrade Holdings LLP) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9488` | SANCT-ENT-00488 (Volkov Maritime Services AG) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9502` | SANCT-ENT-00502 (Crescent Star Petrochemicals FZE) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9519` | SANCT-ENT-00519 (Atlas Northern Commodities OÜ) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9211` | SANCT-IND-00211 (Ostrovsky, Dmitri A.) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9238` | SANCT-IND-00238 (Mansoor, Layla H.) | BLOCK + MLRO |
| `counterparty_id` exact | `CP-9247` | SANCT-IND-00247 (Pavlenko, Sergei V.) | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "BoreasTrade Holdings LLP" + aliases | SANCT-ENT-00471 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Volkov Maritime Services AG" + aliases | SANCT-ENT-00488 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Crescent Star Petrochemicals FZE" + aliases | SANCT-ENT-00502 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Atlas Northern Commodities OÜ" + aliases | SANCT-ENT-00519 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Ostrovsky, Dmitri A." | SANCT-IND-00211 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Mansoor, Layla H." | SANCT-IND-00238 | BLOCK + MLRO |
| `counterparty_name` fuzzy ≥ 0.92 | "Pavlenko, Sergei V." | SANCT-IND-00247 | BLOCK + MLRO |
| `reference` substring | Any alias from §2–§3 | (entity-dependent) | BLOCK + MLRO |

### 5.1 Pattern-Matching Index (Future Keys — Inactive)

Documented for forward compatibility; activated when the source feed begins emitting IBAN/BIC fields under ISO 20022:

| Pattern Type | Value | Linked Entry |
|---|---|---|
| IBAN Prefix | `CY17 0030 0014 0000` | SANCT-ENT-00471 |
| IBAN Prefix | `CH93 0076 2011 6238` | SANCT-ENT-00488 / SANCT-IND-00211 |
| IBAN Prefix | `EE38 2200 2210 2014` | SANCT-ENT-00519 / SANCT-IND-00247 |
| BIC | `BRSTCY2NXXX` | SANCT-ENT-00471 |
| BIC | `VLKMCHZZXXX` | SANCT-ENT-00488 |
| BIC | `CSPCAEFJXXX` | SANCT-ENT-00502 |
| BIC | `ATNCEE22XXX` | SANCT-ENT-00519 |
| BIC Country Prefix | `TM*`, `UZ*`, `AZ*`, `TJ*` | HRJ-CTC-01 |
| BIC Country Prefix | `MK*`, `XK*`, `ME*`, `BA*` | HRJ-WBSC-02 |

---

## 6. Update Provenance

- **Source:** Synthesised mock list derived from public EU Council Implementing Regulations and CBI Financial Sanctions notices for the purpose of demonstrating CATAS compliance screening. No real natural persons are designated.
- **Next Scheduled Review:** 2026-05-25
- **Owner:** Head of Financial Crime Compliance, CATAS Demo Tenant

---

## 7. Document Control

| Version | Date | Author | Change Summary |
|---|---|---|---|
| 1.0 | 2026-04-01 | Head of Financial Crime Compliance | Initial issuance. |
| 1.1 | 2026-05-18 | Head of Financial Crime Compliance | Added `counterparty_id` (CP-9xxx range) as the **active** primary match key against the v2 mock dataset. Demoted IBAN/BIC matching to forward-state (new §5.1). Restructured §5 into active vs inactive index tables. Reclassified §4 corridors as advisory pending ISO 20022 enrichment. |
