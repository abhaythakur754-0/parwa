"""
Configuration for LLM providers used by the Smart Router.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from shared.core_functions.config import Settings

class Provider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"

# Estimated cost and latency weights for routing decisions.
# cost_per_1k_tokens: approximate cost in cents.
# latency_weight: multiplier (lower is better/faster).
PROVIDER_STATS: Dict[Provider, Dict[str, Any]] = {
    Provider.OPENAI: {
        "cost_per_1k_tokens": 30, # GPT-4o estimate
        "latency_weight": 0.5 # Fastest
    },
    Provider.ANTHROPIC: {
        "cost_per_1k_tokens": 45, # Claude 3.5 Sonnet estimate
        "latency_weight": 1.5
    },
    Provider.GEMINI: {
        "cost_per_1k_tokens": 10, # Gemini 1.5 Flash estimate (very cheap)
        "latency_weight": 0.8 # Good, but not as fast as OpenAI for this mock
    }
}

def get_active_providers(settings: Optional[Settings] = None) -> List[Provider]:
    """
    Determines which providers are active based on the application settings.
    """
    if settings:
        try:
            val = settings.openrouter_api_key.get_secret_value()
            if not val:
                return []
        except AttributeError:
            # Handle mock objects or cases where secret_value isn't accessible
            pass
            
    return [Provider.OPENAI, Provider.ANTHROPIC, Provider.GEMINI]
