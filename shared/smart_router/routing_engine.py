import time
import logging
from typing import Dict, Any, List, Optional
from shared.smart_router.provider_config import Provider, PROVIDER_STATS, get_active_providers
from shared.smart_router.cost_optimizer import calculate_best_provider
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger("smart_router")

class SmartRouter:
    """
    Main routing class that executes LLM calls and handles failover.
    Provides multi-LLM orchestration for PARWA.
    """

    def __init__(self):
        settings = get_settings()
        self.active_providers = get_active_providers(settings)

    def route_request(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Routes an LLM request to the best available provider with failover logic.
        
        Args:
            prompt: The user or system prompt.
            context: Optional dictionary for tracking priority, token counts, etc.
            
        Returns:
            Dict containing the LLM response, metadata, and the provider used.
        """
        context = context or {}
        priority = context.get("priority", "cost")
        token_count_est = context.get("token_count", 500)
        
        # Get the primary provider based on optimizer
        primary_provider = calculate_best_provider(token_count_est, priority)
        
        # Build the sequence of providers for failover
        # We start with the primary, then append others as fallback
        failover_list = [primary_provider]
        for p in self.active_providers:
            if p not in failover_list:
                failover_list.append(p)

        last_error = None
        for attempt, provider in enumerate(failover_list):
            try:
                start_time = time.time()
                logger.info(f"Routing request to {provider} (Attempt {attempt + 1})")
                
                # EXECUTE LLM CALL (Placeholder for real integration)
                response = self._execute_call(provider, prompt, context)
                
                latency = time.time() - start_time
                logger.info(f"Request successful on {provider} in {latency:.2f}s")
                
                return {
                    "response": response,
                    "provider": provider,
                    "latency": latency,
                    "attempts": attempt + 1,
                    "status": "success"
                }

            except Exception as e:
                last_error = e
                # Check if it's a retryable error (e.g., 429 Rate Limit, 503 Unavailable)
                # In a real app, we would check status codes from the LLM provider SDK
                error_msg = str(e)
                logger.warning(f"Provider {provider} failed: {error_msg}. Failing over...")
                
                # If we've exhausted all providers
                if attempt == len(failover_list) - 1:
                    logger.error("All LLM providers failed.")
                    raise RuntimeError(f"All LLM providers failed. Last error: {error_msg}") from e

        # Should never reach here due to the raise inside the loop
        return {"status": "error", "error": str(last_error)}

    def _execute_call(self, provider: Provider, prompt: str, context: Dict[str, Any]) -> str:
        """
        Internal method to simulate/execute the actual provider call.
        """
        prompt_lower = prompt.lower()
        if "force_fail everything" in prompt_lower:
            raise Exception(f"Mock 500: Total System Failure ({provider})")

        if "force_fail" in prompt_lower and provider == Provider.OPENAI:
            raise Exception("Mock 503: Service Unavailable (OpenAI)")
            
        if "force_rate_limit" in prompt_lower and provider == Provider.OPENAI:
            raise Exception("Mock 429: Rate Limit Exceeded (OpenAI)")

        return f"Response from {provider.value}: {prompt[:20]}..."
