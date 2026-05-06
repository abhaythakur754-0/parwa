"""
PARWA Pricing Optimizer (Smart Router Logic)
Determines the most cost-effective LLM tier to use based on 
prompt complexity and client feature flags.
"""

from typing import Any, Dict


def select_llm_tier(prompt: str, feature_flags: Dict[str, Any]) -> str:
    """
    Analyzes a prompt and route it to either the Light or Heavy tier.
    
    Light Tier (Llama-3 8B): Used for short/simple queries and standard FAQs.
    Heavy Tier (GPT-4o/Claude-3.5): Used for complex reasoning, multi-part questions, and high-risk intents.
    
    Args:
        prompt: The user input string.
        feature_flags: The client's active tier flags (e.g., from parwa_flags.json).
        
    Returns:
        A string indicating the tier ('light' or 'heavy').
    """
    if not prompt or not isinstance(prompt, str):
        return "light"  # Default to cheapest model if invalid

    prompt_length = len(prompt)
    prompt_lower = prompt.lower()
    
    # 1. High Complexity Indicators (Force Heavy)
    heavy_keywords = [
        "refund", "cancel", "supervisor", "chargeback", 
        "discount", "manager", "broken", "angry", "legal"
    ]
    
    # Check if prompt contains heavy keywords
    has_heavy_intent = any(keyword in prompt_lower for keyword in heavy_keywords)
    
    # 2. Length-based complexity
    is_long_prompt = prompt_length > 250
    
    # 3. Analyze feature flag constraints
    # If the user is on Mini PARWA and doesn't have Agent Lightning/Heavy tier access,
    # we might restrict them, but for routing cost logic purely based on intent:
    
    if has_heavy_intent or is_long_prompt:
        return "heavy"
        
    # Default to cheapest, fastest model for simple queries
    return "light"
