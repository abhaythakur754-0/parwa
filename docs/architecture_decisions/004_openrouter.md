# ADR-004: OpenRouter Integration for Multi-Model AI Access

## Status

**Accepted** - 2025-01-15

## Context

PARWA requires access to multiple LLM providers (OpenAI GPT-4, Anthropic Claude, Google Gemini, Meta Llama) to implement the Smart Router tier system. Managing individual API integrations for each provider creates several challenges:

1. **Vendor Lock-in Risk**: Direct integration with a single provider limits flexibility and negotiating power
2. **Integration Complexity**: Each provider has different authentication, rate limiting, and API patterns
3. **Cost Optimization**: Switching between models for cost optimization requires separate billing relationships
4. **Failover Complexity**: Implementing cross-provider failover requires maintaining multiple active connections
5. **Unified Monitoring**: Logging and monitoring across providers requires custom aggregation

## Decision

We will use **OpenRouter** as a unified API gateway for all LLM access in PARWA.

### What is OpenRouter?

OpenRouter is an API aggregator that provides:
- Single API endpoint for 100+ LLM models
- OpenAI-compatible API format
- Automatic failover between providers
- Unified billing and usage tracking
- Cost optimization through price-aware routing

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PARWA System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌────────────────┐     ┌───────────────┐  │
│  │   Smart     │────▶│   OpenRouter   │────▶│  GPT-4o       │  │
│  │   Router    │     │   Gateway      │     │  Claude 3.5   │  │
│  │             │     │                │     │  Gemini Pro   │  │
│  └─────────────┘     │  - Failover    │     │  Llama 3      │  │
│                      │  - Load Bal.   │     │  ...          │  │
│                      │  - Cost Track  │     └───────────────┘  │
│                      └────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Tier Model Mapping

| PARWA Tier | Primary Model | Fallback Model | Use Case |
|------------|---------------|----------------|----------|
| Light | llama-3-8b | gemini-flash | FAQ, simple queries, greetings |
| Medium | gpt-4o-mini | claude-haiku | Standard support, multi-turn |
| Heavy | gpt-4o | claude-3.5-sonnet | Refunds, escalations, complex |

### Configuration

```python
# shared/smart_router/provider_config.py
OPENROUTER_CONFIG = {
    "base_url": "https://openrouter.ai/api/v1",
    "models": {
        "light": {
            "primary": "meta-llama/llama-3-8b-instruct",
            "fallback": "google/gemini-flash-1.5",
            "max_tokens": 1024,
            "temperature": 0.3,
        },
        "medium": {
            "primary": "openai/gpt-4o-mini",
            "fallback": "anthropic/claude-3-haiku",
            "max_tokens": 2048,
            "temperature": 0.5,
        },
        "heavy": {
            "primary": "openai/gpt-4o",
            "fallback": "anthropic/claude-3.5-sonnet",
            "max_tokens": 4096,
            "temperature": 0.7,
        },
    },
    "headers": {
        "HTTP-Referer": "https://parwa.ai",
        "X-Title": "PARWA Customer Support AI",
    }
}
```

## Consequences

### Positive

1. **Single Integration Point**: One API key, one SDK, one billing relationship
2. **Automatic Failover**: OpenRouter handles provider outages transparently
3. **Cost Optimization**: Access to cheaper models without separate contracts
4. **Flexibility**: Add or remove models without code changes
5. **OpenAI Compatibility**: Existing OpenAI SDK works with minimal changes
6. **Usage Analytics**: Unified dashboard for all model usage

### Negative

1. **Additional Latency**: One extra hop in the request path (~10-50ms)
2. **Dependency Risk**: OpenRouter outage affects all LLM access
3. **Cost Markup**: Small margin on top of provider pricing
4. **Feature Lag**: New provider features may not be immediately available

### Mitigations

1. **Latency**: OpenRouter has edge locations; impact is minimal for chat use cases
2. **Dependency**: Maintain emergency direct API keys for critical providers
3. **Cost**: The markup (~5%) is offset by simplified billing and reduced integration costs
4. **Features**: Monitor OpenRouter updates; contribute to their roadmap

## Implementation

### Phase 1: Core Integration (Week 5)

1. Add OpenRouter API key to environment configuration
2. Update `tier_config.py` to use OpenRouter model identifiers
3. Implement OpenRouter-specific headers for tracking
4. Update Smart Router to route through OpenRouter

### Phase 2: Cost Optimization (Week 6)

1. Implement price-aware model selection
2. Add budget tracking per company
3. Create cost alerts and throttling

### Phase 3: Advanced Features (Week 7+)

1. Implement custom routing rules
2. Add provider-specific parameters
3. Integrate OpenRouter analytics into PARWA dashboard

## Monitoring

Key metrics to track:

| Metric | Alert Threshold | Action |
|--------|-----------------|--------|
| OpenRouter API latency | > 500ms p99 | Investigate routing |
| Error rate | > 1% | Check failover status |
| Cost per query | > $0.05 | Review tier selection |
| Rate limit hits | > 10/hour | Request limit increase |

## Security Considerations

1. **API Key Storage**: OpenRouter API key stored in environment variables, never in code
2. **Request Logging**: PII is masked in all logs
3. **Cost Controls**: Maximum daily spend limits per company
4. **Rate Limiting**: Per-company rate limits enforced before OpenRouter call

## References

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [PARWA Smart Router Design](./002_smart_router_design.md)
- [PARWA Architecture Overview](../product/PARWA_Complete_Documentation_v6_Readable.md)

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-15 | Builder 5 | Initial ADR creation |
