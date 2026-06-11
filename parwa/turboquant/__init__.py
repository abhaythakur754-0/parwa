"""TurboQuant — PARWA's Token Optimization Engine.

Accuracy FIRST, tokens are a side effect. TurboQuant dynamically manages
LLM token usage across the 22-node pipeline to minimize cost while
maintaining accuracy.

Core Philosophy:
- Mini PARWA: Smaller token budgets (cost-sensitive)
- PARWA: Balanced token budgets (cost-accuracy trade-off)
- PARWA High: Unlimited tokens (accuracy-focused)
- ALL variants THINK identically — TurboQuant just makes it efficient

Components:
- TokenBudget: Per-node token budget allocation with variant awareness
- TokenTracker: Track actual token usage per node, per ticket, per variant
- PromptCompressor: Compress prompts to fit within budgets
- AdaptiveBudget: Reallocate unused tokens from simple to complex nodes
- CostReporter: Per-ticket and per-variant cost analysis
"""

from parwa.turboquant.token_budget import (
    TokenBudget,
    NodeBudget,
    get_node_budget,
    get_ticket_budget,
    VARIANT_TOKEN_MULTIPLIERS,
)
from parwa.turboquant.token_tracker import TokenTracker, TokenUsage, get_token_tracker
from parwa.turboquant.prompt_compressor import PromptCompressor, compress_prompt
from parwa.turboquant.adaptive_budget import AdaptiveBudgetManager
from parwa.turboquant.cost_reporter import CostReporter, CostReport, get_cost_reporter

__all__ = [
    "TokenBudget",
    "NodeBudget",
    "get_node_budget",
    "get_ticket_budget",
    "VARIANT_TOKEN_MULTIPLIERS",
    "TokenTracker",
    "TokenUsage",
    "get_token_tracker",
    "PromptCompressor",
    "compress_prompt",
    "AdaptiveBudgetManager",
    "CostReporter",
    "CostReport",
    "get_cost_reporter",
]
