# TCPA Compliance Guide for PARWA Voice Agents

**Last Updated:** March 12, 2026

When deploying PARWA's voice and SMS capabilities, compliance with the Telephone Consumer Protection Act (TCPA) and related regulations is mandatory. This guide outlines the requirements for utilizing the PARWA platform for autonomous communications.

## 1. Prior Express Written Consent

Before PARWA initiates any outbound AI-driven SMS or Voice outreach, you must obtain prior express written consent from the consumer. 

*   **Requirement:** The consent must clearly authorize you to use an artificial or prerecorded voice and/or automated text messages to contact them.
*   **Documentation:** You must maintain a record of this consent (e.g., a timestamped opt-in from a web form) and make it available upon request.
*   **No Purchase Necessary:** Consent must not be required as a condition of purchasing any property, goods, or services.

## 2. Call Recording and AI Disclosure

Many jurisdictions (including several US states and international regions) require all parties to consent to a recorded call. Furthermore, transparency regarding the use of AI is a core PARWA policy.

*   **Mandatory Disclosure Script:** Every inbound or outbound voice call handled by PARWA **must** begin with the following disclosure before any substantive interaction occurs:
    > *"This call is being recorded for quality and training purposes, and you are speaking with an AI assistant."*
*   **Configuration:** This script must be explicitly configured in the Twilio integration payload for the Voice agent.

## 3. Opt-Out Mechanisms ("STOP")

Consumers must have an immediate, simple, and reliable way to revoke consent and opt out of future automated communications.

*   **SMS Opt-Out:**
    *   PARWA will automatically honor standard opt-out keywords (e.g., "STOP", "QUIT", "CANCEL", "UNSUBSCRIBE").
    *   Upon receiving an opt-out word, the PARWA agent will immediately cease messaging the number and log the opt-out in the database. No further messages will be sent unless the user explicitly opts back in (e.g., "START").
*   **Voice Opt-Out:**
    *   If a user requests to be placed on a "Do Not Call" list during a voice interaction (e.g., "stop calling me", "put me on your do not call list"), PARWA is programmed to acknowledge the request, immediately terminate the call, and flag the number in the database as DNC.

## 4. Time of Day Restrictions

Automated outbound calls and texts managed by PARWA must only be made between the hours of **8:00 AM and 9:00 PM** (local time of the called party), in accordance with TCPA rules. The PARWA `notification_service` enforces these windows automatically based on the user's registered area code or provided timezone.

## 5. Violation and Liability

Failure to adhere to these guidelines may result in severe TCPA penalties (ranging from $500 to $1,500 per violation). As outlined in our Terms of Service, the client deploying the PARWA instance is solely responsible for ensuring that all consent and opt-out mechanisms are legally sound and properly configured.

--- 
*For additional compliance integration questions, consult the Twilio Integration Docs or contact legal@parwa.ai.*
