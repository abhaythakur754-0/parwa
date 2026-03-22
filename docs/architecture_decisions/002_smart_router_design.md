# ADR 002: Smart Router Design for Cost Optimization

## Status
Accepted

## Context
Operating large language models (LLMs) at scale for customer support runs a high risk of catastrophic API fatigue and exorbitant costs. A significant percentage of customer inquiries (roughly 60%) are simple FAQs ("Where is my order?", "How do I reset my password?") that do not require the reasoning capabilities of an expensive, heavy model like GPT-4o or Claude 3.5 Sonnet.

## Decision
We will implement a "Smart Router" component (`pricing_optimizer.py`) at the very edge of our AI pipeline. 

The Smart Router will evaluate incoming prompts based on:
1. **Tenant Feature Flags:** (e.g., Mini PARWA tier might be forced to use Light models as much as possible).
2. **Prompt Complexity:** Checking prompt length and specific intent keywords (e.g., "analyze", "refund", "supervisor").

Based on this evaluation, the router returns a tier designation:
- **Light Tier:** Routes to a highly-quantized, fast, and cheap model (e.g., Llama-3 8B hosted on OpenRouter).
- **Heavy Tier:** Routes to a premium model for complex reasoning or high-risk financial actions.

## Consequences
### Positive
- **Drastic Cost Reduction:** Expected 60-80% savings on LLM inference costs compared to routing all queries to a Heavy model.
- **Lower Latency:** Light models return tokens significantly faster, improving the user experience for simple queries.

### Negative
- **Routing Errors:** A heuristic-based router may occasionally misclassify a complex query as "Light", leading to a subpar response. This requires continuous tuning of the `pricing_optimizer` criteria.
