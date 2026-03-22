# Formatted BDD Scenarios: PARWA (Standard)

**Feature:** PARWA Standard Automation
**As a** Customer Support Manager using the standard PARWA tier
**I want** an AI agent that learns from our responses and makes intelligent product recommendations
**So that** we can drive revenue and automate 80%+ of our ticket volume.

## Scenario 1: Product Recommendations
**Given** a user is interacting with the PARWA agent
**And** the user asks "What running shoes do you recommend for flat feet?"
**When** the agent processes the query
**Then** the agent retrieves user history and standard recommendation guidelines
**And** the agent suggests "The CloudStrider Pro is excellent for flat feet. Would you like me to add it to your cart?"
**And** the intent is logged as an upsell attempt.

## Scenario 2: Agent Lightning (Continuous Learning Loop)
**Given** a human manager is reviewing past AI agent tickets in the dashboard
**When** the manager corrects an AI response from "We don't sell that" to "We will have that in stock next week"
**And** the manager clicks "Approve Correction"
**Then** the `training_threshold` counter increments by 1
**And** when the threshold hits 50, the dataset is exported to JSONL
**And** a webhook is fired to Colab/Unsloth for Lora Fine-Tuning
**And** on Week 6 (Integration Day), the newly fine-tuned adapter is deployed to production.

## Scenario 3: Peer Review System
**Given** the Smart Router marks a user's query as having a 'medium' confidence score
**When** the Light Model generates a draft response
**Then** the Heavy Model (Llama-3 400B) silently reviews the response
**And** if the Heavy Model approves, the response is sent to the user
**And** if the Heavy Model rejects, the Heavy Model rewrites the response and sends it to the user.
