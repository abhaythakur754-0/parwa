# PARWA — Limitations of Liability & AI Indemnification
**Last Updated:** 2026-03-12

This document ("Liability Limitations") constitutes an addendum to the PARWA Terms of Service and outlines the explicit limits of liability regarding the autonomous actions performed by PARWA AI agents (including Mini PARWA, PARWA, and PARWA High).

---

## 1. Acknowledgment of AI Autonomy and Hallucinations

By deploying PARWA agents, the Client acknowledges that Large Language Models (LLMs) and autonomous AI systems may occasionally produce inaccurate, unexpected, or unintended outputs (commonly referred to as "hallucinations"). While PARWA employs extensive techniques (such as the TRIVYA orchestrator and GSD State Engine) to minimize these occurrences, they cannot be entirely eliminated.

## 2. General Liability Cap

Except where explicitly agreed upon in a custom Enterprise Agreement, PARWA’s total aggregate liability arising out of or related to errors, hallucinations, or unauthorized autonomous actions taken by the AI agents is strictly capped at **$50.00 USD per transaction** or individual customer interaction.

## 3. High-Risk Action Guardrails

To protect against severe financial exposure, PARWA is architected with strict, hardcoded guardrails for "High-Risk Actions." We assume **zero liability** if the Client attempts to bypass or disable these safeguards.

### A. Refunds and Financial Transactions
- **Human-In-The-Loop (HITL) Requirement:** PARWA agents are functionally restricted from directly executing refunds via Stripe or any other payment processor. The agents may only verify refund eligibility and generate a `pending_approval` recommendation (Approve, Review, Deny).
- **Final Execution:** A human agent (Controller) MUST approve all refunds. PARWA holds no liability for refunds approved by the Client's human staff, regardless of the AI's recommendation.

### B. Discounts and Price Alterations
- Any automated discount allocation exceeding **20% of the base transaction value** strictly requires human approval.
- Any attempt by an end-user to manipulate the AI (Prompt Injection / Jailbreaking) into offering unauthorized discounts falls outside our liability scope.

## 4. Client Configurations and Custom Workflows

PARWA provides a Knowledge Base (RAG) and BDD-driven business workflows. We are not liable for:
- Errors resulting from inaccurate, outdated, or legally non-compliant data uploaded to the Knowledge Base by the Client.
- Violations of law (such as TCPA or GDPR) resulting from custom prompt instructions or workflows authored by the Client.

## 5. Enterprise Waiver Process

Clients requiring liability coverage exceeding the standard $50 per-transaction cap may apply for an Enterprise Liability Waiver.
- **Process:** Requires a comprehensive audit of the Client’s RAG Knowledge Base, implemented feature flags, and a mandatory 14-day observation period running PARWA in "Simulation Mode."
- **Approval:** Only granted via a distinct, physically signed addendum specifying the customized liability ceiling.

---

**By using the PARWA platform, you expressly agree to these technical and financial limitations.**
