# ADR 003: Agent Lightning Continuous Training Loop

## Status
Accepted

## Context
Deploying LLMs out-of-the-box for specialized customer service usually yields generic responses that fail to capture the specific tone, dialect, and precise policy nuances of a distinct brand. To solve this, models must be fine-tuned continually on the live interactions between the human support agents and the customers.

## Decision
We will develop "Agent Lightning," a closed-loop training pipeline integrating directly into the PARWA dashboard.

1. **The Correction UI**: Human agents working in the PARWA dashboard will be able to edit and rewrite poor AI drafts before sending them to the customer. 
2. **Data Export**: Upon an AI draft being corrected and sent, the original prompt and the newly approved, perfect response will be aggregated. Once a threshold is met (e.g., 50 corrections per tenant), the data will be exported as pairs in JSONL format.
3. **Fine-Tuning Execution**: We will utilize Google Colab (or similar managed notebook infrastructure) with the `Unsloth` library to programmatically launch a PEFT (LoRA) fine-tuning job on the foundational model using the JSONL dataset.
4. **Adapter Deployment**: After fine-tuning converges, the resulting PEFT adapter will be automatically pulled down via API and mounted onto our inference server instance (e.g., vLLM or Ollama), immediately improving the baseline model's performance on that brand's specific tone and policy.

## Consequences
### Positive
- **Self-Improving System**: The platform's accuracy and deflection rates will continuously improve over time simply by humans doing their normal work.
- **Tone Adherence**: The model naturally acquires the exact vernacular and formatting preferences of the brand without complex prompt engineering.

### Negative
- Computing costs for consistent fine-tuning runs.
- Complexity mapping and loading dozens/hundreds of different LoRA adapters per tenant memory efficiently.
