"""
Optimization logic to select the cheapest or fastest provider.
"""
from typing import Optional
from shared.smart_router.provider_config import Provider, PROVIDER_STATS, get_active_providers
from shared.core_functions.config import get_settings

def calculate_best_provider(token_count: int, priority: str) -> Provider:
    """
    Selects the best provider based on cost or latency, considering only active ones.
    """
    settings = get_settings()
    active_providers = get_active_providers(settings)
    
    if not active_providers:
        # Fallback to a default if nothing is active (should be handled by router)
        return Provider.GEMINI

    best_provider = active_providers[0]
    
    if priority == "cost":
        min_cost = float('inf')
        for p in active_providers:
            cost = PROVIDER_STATS.get(p, {}).get("cost_per_1k_tokens", 999)
            if cost < min_cost:
                min_cost = cost
                best_provider = p
    else:
        # Latency priority
        min_latency = float('inf')
        for p in active_providers:
            latency = PROVIDER_STATS.get(p, {}).get("latency_weight", 999)
            if latency < min_latency:
                min_latency = latency
                best_provider = p
                
    return best_provider
