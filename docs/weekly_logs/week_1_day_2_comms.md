# AGENT_COMMS.md — Week 1 Day 2
# Last updated: 2026-03-11 17:41 IST
# Current status: IN PROGRESS

═══════════════════════════════════════════════════════════
## MANAGER → DAY 2 PLAN
═══════════════════════════════════════════════════════════
Written by: Manager Agent (Antigravity)
Date: 2026-03-11

> NOTE: This is the first parallel day. 4 Builders are assigned.
> Builders: Do NOT push unless your unit tests pass. 

---

### AGENT 1 TASK — config.py

File to Build:          `shared/core_functions/config.py`
What Is This File?:     Central configuration manager that loads environment variables and provides them as a typed Pydantic Settings object
Responsibilities:
  - Load variables from `.env` using `pydantic-settings`
  - Define `Settings` model with robust validation
  - Group settings (Database, Redis, AI APIs, Third Party, Security, Feature Flags)
  - Provide a cached singleton instance `get_settings()` via `@lru_cache()`
Depends On:             None (Day 1 structure exists)
Expected Output:        A `get_settings()` function that safely returning env configurations
Unit Test File:         `tests/unit/test_config.py` (Must create and pass)
BDD Scenario:           N/A
Error Handling:         Raise `ValueError` if strictly required variables (like JWT_SECRET) are missing and `ENVIRONMENT=production`
Security Requirements:  Secrets must be loaded securely. No defaults for production secrets.
Integration Points:     Every backend API file will depend on this.
Code Quality:           Strict type hints, docstrings on all classes/methods, max 40 lines/func.
Pass Criteria:          Unit test passes achieving 100% coverage on config loading logic. Model strictly validates variables mapping to `.env.example`.

---

### AGENT 2 TASK — privacy_policy.md

File to Build:          `legal/privacy_policy.md`
What Is This File?:     The official legal privacy policy for the PARWA platform
Responsibilities:
  - Detail data collection methods (voice recordings, chat logs, user data)
  - Outline GDPR and CCPA rights (Access, Erasure, Portability)
  - Specify retention policies (chat logs kept for Agent Lightning)
  - Name key sub-processors (OpenRouter, Stripe, Twilio)
Depends On:             None
Expected Output:        A complete, formatted Markdown privacy policy document
Unit Test File:         N/A
BDD Scenario:           N/A
Error Handling:         N/A
Security Requirements:  Must accurately reflect our AI data usage.
Integration Points:     Will be linked in the Next.js frontend footer
Code Quality:           Clear, professional legal markdown formatting
Pass Criteria:          Document is completely written, no placeholder text, covers all required areas.

---

### AGENT 3 TASK — terms_of_service.md

File to Build:          `legal/terms_of_service.md`
What Is This File?:     The official Terms of Service governing the use of the PARWA platform
Responsibilities:
  - Define permitted uses and prohibited AI manipulation (jailbreaking)
  - Detail billing terms (Stripe) and subscription tiers
  - Outline SLA terms and limitations of liability regarding autonomous AI actions
  - Define account suspension metrics
Depends On:             None
Expected Output:        A complete, formatted Markdown ToS document
Unit Test File:         N/A
BDD Scenario:           N/A
Error Handling:         N/A
Security Requirements:  Must explicitly waive liability for AI hallucinations/errors
Integration Points:     Will be linked in the frontend footer and Privacy Policy
Code Quality:           Clear, professional legal markdown formatting
Pass Criteria:          Document is completely written, no placeholder text, covers all required areas.

---

### AGENT 4 TASK — data_processing_agreement.md

File to Build:          `legal/data_processing_agreement.md`
What Is This File?:     The Data Processing Agreement for enterprise compliance (GDPR/SOC2)
Responsibilities:
  - Define PARWA as the Processor and the Client as the Controller
  - Detail standard contractual clauses
  - Detail sub-processor authorization (OpenRouter, Stripe, Twilio)
  - Outline data breach notification timelines (72 hours)
Depends On:             None
Expected Output:        A complete, formatted Markdown DPA document
Unit Test File:         N/A
BDD Scenario:           N/A
Error Handling:         N/A
Security Requirements:  Critical for SOC2 compliance setup
Integration Points:     Available for download or electronic signature via the dashboard
Code Quality:           Clear, professional legal markdown formatting
Pass Criteria:          Document is completely written, no placeholder text, covers all required areas.

═══════════════════════════════════════════════════════════
## AGENT 1 → DAY 2 STATUS
═══════════════════════════════════════════════════════════
File:              shared/core_functions/config.py
Status:            DONE
Unit Test:         PASS (test_config.py)
Pushed:            YES
Commit:            [verified present]
Initiative Files:  NONE
Notes:             Implemented get_settings() with pydantic-settings and strict validation. Passes all tests.

═══════════════════════════════════════════════════════════
## AGENT 2 → DAY 2 STATUS
═══════════════════════════════════════════════════════════
File:              legal/privacy_policy.md
Status:            DONE
Unit Test:         N/A
Pushed:            YES
Commit:            [verified present]
Initiative Files:  NONE
Notes:             Privacy policy properly detailed. Covers voice & chat logs for Agent Lightning, explicit data retention outlines, and lists Sub-Processors (Stripe, Twilio, Supabase, OpenRouter).

═══════════════════════════════════════════════════════════
## AGENT 3 → DAY 2 STATUS
═══════════════════════════════════════════════════════════
File:              legal/terms_of_service.md
Status:            DONE
Unit Test:         N/A (Markdown document)
Pushed:            YES
Commit:            [verified present]
Initiative Files:  NONE
Notes:             ToS covers permitted AI uses, Stripe billing, SLA limitations/waiver of liability for AI actions, and account suspension policies.
═══════════════════════════════════════════════════════════
## AGENT 4 → DAY 2 STATUS
═══════════════════════════════════════════════════════════
File:              legal/data_processing_agreement.md
Status:            DONE
Unit Test:         N/A
Pushed:            YES
Commit:            [Pending commit hash]
Initiative Files:  NONE
Notes:             Completed DPA addressing PARWA as Processor, SCCs, Sub-processors (OpenRouter, Stripe, Twilio), and 72-hour data breach notification timeline as specified in task.

═══════════════════════════════════════════════════════════
## TESTER → DAY 2 REPORT
═══════════════════════════════════════════════════════════
Verified by: Tester Agent (Antigravity)
Date: 2026-03-11

### Individual File Results
shared/core_functions/config.py → PASS
legal/privacy_policy.md → PASS
legal/terms_of_service.md → PASS
legal/data_processing_agreement.md → PASS

### Daily Integration Test
Command: N/A - Day 2 has no integration test defined
Result: N/A
Failures: None

### Observations (initiative)
All 4 builders completed their files correctly. `config.py` correctly validates missing variables and prevents `your-` default secrets in production environments.
Overall Day 2: PASS

═══════════════════════════════════════════════════════════
## ASSISTANCE → USER REPORT
═══════════════════════════════════════════════════════════
DAILY REPORT — Week 1 Day 2 — 2026-03-11
WHAT WAS BUILT TODAY:    [Pending]
UNIT TESTS:              [Pending]
INTEGRATION TEST:        N/A
ERRORS TODAY:            0
SCHEDULE STATUS:         ON TRACK
INITIATIVE ACTIONS:      NONE YET
NEEDS YOUR ATTENTION:    NOTHING TODAY
TOMORROW:                logger.py + liability_limitations.md + TCPA guide + feature_flags
