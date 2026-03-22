# Formatted BDD Scenarios: Mini PARWA

**Feature:** Mini PARWA Support Automation
**As a** Customer Support Manager using the Mini PARWA tier
**I want** an AI agent to automatically resolve FAQs and deflect basic queries
**So that** my human team can focus on complex issues while keeping costs low.

## Scenario 1: FAQ Deflection
**Given** the Mini PARWA agent is active on the website chat
**And** the knowledge base contains an article titled "Shipping Times"
**When** a user asks "How long does shipping take to New York?"
**Then** the agent should query the knowledge base
**And** the agent should respond with "Standard shipping to New York takes 3-5 business days."
**And** the ticket should be marked as "Resolved by AI".

## Scenario 2: Strict Blocking of Autonomous Refunds (Refund Gate)
**Given** a user is interacting with the Mini PARWA agent
**When** the user says "I want a refund for my last order"
**Then** the Smart Router should classify the intent as `REFUND`
**And** the `ai_safety` rules should intercept the request
**And** the agent should respond "I can help you with that, but I need to transfer you to a human agent to process the refund."
**And** the agent should stage the refund context in the dashboard
**And** the ticket should be placed in the "Needs Manager Approval" queue.

## Scenario 3: Usage Limits Enforcement
**Given** the tenant is subscribed to Mini PARWA
**And** the tenant has reached their maximum of 2 concurrent Voice slots
**When** a 3rd user dials the support number
**Then** the Twilio webhook should reject the AI handover
**And** the call should be routed to the fallback human queue or voicemail.
