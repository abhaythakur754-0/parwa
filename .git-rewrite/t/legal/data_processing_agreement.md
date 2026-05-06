# Data Processing Agreement (DPA)

This Data Processing Agreement ("DPA") supplements the Terms of Service and Privacy Policy of PARWA ("Processor") and is entered into by and between PARWA and the client using our autonomous AI customer support services ("Controller").

## 1. Roles and Responsibilities
For the purposes of the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and similar applicable data protection laws:
*   **Controller**: The Client, who determines the purposes and means of the processing of personal data.
*   **Processor**: PARWA, which processes personal data on behalf of the Controller to provide AI-driven customer support automation.

## 2. Standard Contractual Clauses (SCCs)
To the extent that the processing of personal data involves a transfer of data outside of the European Economic Area (EEA), the UK, or Switzerland to a country that does not ensure an adequate level of data protection, the parties agree that the Standard Contractual Clauses (SCCs) as approved by the European Commission are incorporated by reference and form an integral part of this DPA.

## 3. Sub-Processor Authorization
The Controller grants PARWA general authorization to engage sub-processors to fulfill its contractual obligations. PARWA utilizes the following critical sub-processors:
*   **OpenRouter**: For routing and executing Large Language Model (LLM) queries for the AI agents.
*   **Stripe**: For secure payment processing and subscription billing.
*   **Twilio**: For SMS and voice communication functionalities.
*   **Supabase**: For secure PostgreSQL database hosting and vector storage.

PARWA will notify the Controller of any intended changes concerning the addition or replacement of sub-processors, granting the Controller the opportunity to object to such changes.

## 4. Data Breach Notification
In the event of a confirmed personal data breach affecting the Controller's data, the Processor (PARWA) shall notify the Controller without undue delay, and strictly within **72 hours** of becoming aware of the breach. The notification will include, to the extent capable of being determined:
*   The nature of the personal data breach.
*   The estimated number of data subjects and records concerned.
*   The likely consequences of the breach.
*   The measures taken or proposed to be taken to address the breach and mitigate its adverse effects.

## 5. Security Measures
PARWA implements robust technical and organizational measures to ensure the security of data, including Row-Level Security (RLS) for absolute cross-tenant isolation, AES-256 encryption at rest, and TLS 1.2+ for data in transit, in adherence with SOC 2 compliance standards.

## 6. Return and Deletion of Data
Upon termination of the services, PARWA will, at the choice of the Controller, delete or return all personal data. Our active data deletion protocol involves soft-deletion and automated PII anonymization to strip identifiable data while preserving metrics required for training, in compliance with standard operating procedures.
