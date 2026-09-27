"""
PARWA Demo Output Filter — Shadow Mode Output Sanitizer

Strips internal AI details from responses before showing to demo users.
Hides: model names, confidence scores, pipeline steps, routing info.
"""

import re
from typing import Any, Dict, List, Optional


# Patterns to redact from demo output
REDACT_PATTERNS = [
    # Model names
    (r'\b(GPT-4|GPT-3\.5|Claude|Gemini|Llama|Mixtral|Cerebras|Groq|OpenAI|Anthropic)\b', '[AI Model]'),
    # Confidence scores
    (r'confidence[:\s]*\d+\.?\d*%?', '[Confidence Score]'),
    # Pipeline steps
    (r'pipeline[_ ]step[:\s]*\d+', '[Pipeline Step]'),
    # Internal routing
    (r'route[d]?\s*(via|through|to)\s*\w+_pipeline', '[Routed]'),
    # Internal service names
    (r'\b(mini_parwa|parwa_high|smart_router|agent_lightning)\b', 'PARWA Agent'),
    # Score values
    (r'score[:\s]*\d+\.?\d*', '[Score]'),
    # Latency info
    (r'latency[:\s]*\d+\s*ms', '[Latency]'),
]


def filter_demo_output(response: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Filter demo output to remove internal AI details.
    
    Args:
        response: The raw AI response text
        metadata: Optional metadata about the response (model, score, etc.)
    
    Returns:
        Filtered response safe for demo users
    """
    filtered = response
    
    for pattern, replacement in REDACT_PATTERNS:
        filtered = re.sub(pattern, replacement, filtered, flags=re.IGNORECASE)
    
    return filtered


def filter_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter metadata to remove sensitive internal details.
    
    Args:
        metadata: Raw metadata dict from the AI pipeline
    
    Returns:
        Filtered metadata safe for demo users
    """
    safe_keys = {
        'variant_id', 'variant_tier', 'industry', 'timestamp',
        'message_type', 'session_id', 'status', 'features',
        'tagline', 'best_for', 'integrations', 'price_per_month',
        'tickets_per_month',
    }
    
    return {k: v for k, v in metadata.items() if k in safe_keys}


def create_demo_safe_response(
    raw_response: str,
    raw_metadata: Dict[str, Any],
    variant_tier: str = 'starter',
) -> Dict[str, Any]:
    """
    Create a demo-safe response by filtering output and metadata.
    
    Args:
        raw_response: The raw AI response text
        raw_metadata: Raw metadata from the pipeline
        variant_tier: The variant tier for context
    
    Returns:
        Demo-safe response dict
    """
    return {
        'content': filter_demo_output(raw_response),
        'metadata': filter_metadata(raw_metadata),
        'variant_tier': variant_tier,
        'demo_mode': True,
    }
