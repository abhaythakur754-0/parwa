# 🤖 PARWA Tiered LLM Routing System

## 📊 System Overview

The Smart Router routes AI requests based on task complexity using **4 tiers** across **3 providers** (all FREE tiers):

- **File Location:** `backend/app/core/smart_router.py`
- **Failover System:** `backend/app/core/model_failover.py`
- **Config:** `backend/app/config.py`

---

## 🎯 TIER 1: LIGHT (90% of calls)

**Use Case:** Small, fast tasks

| Priority | Model | Provider | Daily Limit | TPM | Context |
|----------|-------|----------|-------------|-----|---------|
| **1** | **Llama 3.1 8B** | Cerebras | 14,400 | 60,000 | 8K |
| 2 | Llama 3.1 8B | Groq | 14,400 | 6,000 | 8K |
| 3 | Gemma 3 27B IT | Google | 14,400 | 15,000 | 8K |

**API Endpoints:**
- Cerebras: `https://api.cerebras.ai/v1/chat/completions`
- Groq: `https://api.groq.com/openai/v1/chat/completions`
- Google: `https://generativelanguage.googleapis.com/v1beta/models`

**Tasks Handled:**
- Intent Classification
- PII Redaction
- Sentiment Analysis
- CLARA Quality Gate
- CRP Token Trim
- GSD State Steps
- MAD Decompose (Simple)
- Chain-of-Thought Reasoning
- Fake Voting
- Consensus Analysis
- Simple Draft Responses
- Human Escalation

---

## 🎯 TIER 2: MEDIUM (8% of calls)

**Use Case:** Medium complexity reasoning and response generation

| Priority | Model | Provider | Daily Limit | TPM | RPM | Context |
|----------|-------|----------|-------------|-----|-----|---------|
| **1** | **Gemini 3.1 Flash-Lite** ⭐ | Google | 500 | 250,000 | 15 | **1M** |
| 2 | Gemini 2.5 Flash | Google | 1,500 | 1,000,000 | - | 1M |
| 3 | Llama 3.3 70B Versatile | Groq | 1,000 | 12,000 | - | 32K |
| 4 | Qwen3 32B | Groq | 1,000 | 6,000 | - | 32K |

**Primary Model: Gemini 3.1 Flash-Lite**
- **Daily Requests:** 500
- **Tokens per Minute:** 250,000
- **Requests per Minute:** 15
- **Context Window:** 1M tokens

**Tasks Handled:**
- MAD Atom Reasoning
- Draft Response (Moderate)
- Draft Response (Complex)
- Reflexion Cycle

---

## 🎯 TIER 3: HEAVY (2% of calls)

**Use Case:** Complex reasoning, advanced tasks

| Priority | Model | Provider | Daily Limit | TPM | Context |
|----------|-------|----------|-------------|-----|---------|
| 1 | GPT-OSS 120B | Groq | 1,000 | 8,000 | 64K |
| **2** | **GPT-OSS 120B** | Cerebras | **14,400** | 60,000 | 64K |
| 3 | Llama 4 Scout Instruct | Groq | 1,000 | 30,000 | 64K |

**Tasks Handled:**
- Complex Draft Responses
- Advanced Reflexion Cycles

---

## 🎯 TIER 4: GUARDRAIL (Safety Layer)

**Use Case:** Safety & content filtering

| Priority | Model | Provider | Daily Limit | TPM | Context |
|----------|-------|----------|-------------|-----|---------|
| **1** | **Llama Guard 4 12B** | Groq | 14,400 | 30,000 | 8K |

**Tasks Handled:**
- Guardrail Safety Checks
- Content Filtering
- Prompt Injection Detection

---

## 🔄 Failover Chains

When a model fails or gets rate-limited, the system automatically falls to the next provider:

### LIGHT Tier Failover
```
Cerebras (Llama 3.1 8B) → Groq (Llama 3.1 8B) → Google (Gemma 3 27B)
```

### MEDIUM Tier Failover
```
Gemini 3.1 Flash-Lite → Gemini 2.5 Flash → Llama 3.3 70B → Qwen3 32B → LIGHT Tier
```

### HEAVY Tier Failover
```
Groq (GPT-OSS 120B) → Cerebras (GPT-OSS 120B) → Llama 4 Scout → MEDIUM Tier → LIGHT Tier
```

### GUARDRAIL Tier Failover
```
Groq (Llama Guard 4 12B) → Cerebras (Llama 3.1 8B - fallback)
```

---

## 👥 Variant Access Control (SG-03)

Different PARWA variants have access to different model tiers:

| Variant | Allowed Tiers | Use Case | Price Point |
|---------|--------------|----------|-------------|
| **Mini PARWA** | LIGHT + GUARDRAIL | Basic plan | Budget |
| **PARWA** | LIGHT + MEDIUM + GUARDRAIL | Standard plan | Mid-tier |
| **PARWA High** | ALL TIERS (Light + Medium + Heavy + Guardrail) | Premium plan | Enterprise |

---

## 📈 Daily Capacity Summary (FREE Tier)

| Provider | Models Available | Total Daily Requests | Notes |
|----------|-----------------|---------------------|-------|
| **Google** | Gemini 3.1 + 2.5 Flash | 2,000+ | High TPM limits |
| **Cerebras** | Llama 3.1 + GPT-OSS | 28,800+ | Fast inference |
| **Groq** | Llama + Qwen + Guard | 30,000+ | Multiple models |
| **TOTAL** | **10+ Models** | **60,000+** | Combined capacity |

---

## 🔧 Configuration

### Environment Variables Required

```bash
# AI Provider API Keys
GOOGLE_AI_API_KEY=your_google_ai_key
CEREBRAS_API_KEY=your_cerebras_key
GROQ_API_KEY=your_groq_key

# Provider Priority
LLM_PRIMARY_PROVIDER=google
LLM_FALLBACK_PROVIDER=groq
```

### Model Registry Keys

```python
# LIGHT Tier
"llama-3.1-8b-cerebras"
"llama-3.1-8b-groq"
"gemma-3-27b-it-google"

# MEDIUM Tier
"gemini-3.1-flash-lite-google"  # Primary
"gemini-2.5-flash-google"
"llama-3.3-70b-versatile-groq"
"qwen3-32b-groq"

# HEAVY Tier
"gpt-oss-120b-groq"
"gpt-oss-120b-cerebras"
"llama-4-scout-instruct-groq"

# GUARDRAIL Tier
"llama-guard-4-12b-groq"
```

---

## 🚀 Usage for Startup (2-3 Clients)

With this FREE tier setup, you can handle approximately:

- **500+ conversations/day** per client
- **All FREE** - no paid APIs needed
- **Automatic failover** - never drop a conversation
- **Smart routing** - small tasks use cheap models, complex tasks use powerful ones

### Estimated Monthly Capacity

| Scenario | Requests/Day | Feasibility |
|----------|--------------|-------------|
| 2 clients (basic usage) | ~300/day | ✅ Well within limits |
| 3 clients (moderate usage) | ~500/day | ✅ Within limits |
| 3 clients (heavy usage) | ~1,000/day | ⚠️ Need monitoring |

---

## 🛡️ Safety Features

1. **Circuit Breaker Pattern** - Prevents cascading failures
2. **Rate Limit Tracking** - Monitors daily/minute limits
3. **Graceful Degradation** - Falls back to lower tiers
4. **Health Monitoring** - Tracks provider health status
5. **Automatic Recovery** - Self-healing after failures

---

## 📁 Related Files

| File | Purpose |
|------|---------|
| `backend/app/core/smart_router.py` | Main routing logic |
| `backend/app/core/model_failover.py` | Failover chains & circuit breakers |
| `backend/app/config.py` | API keys and configuration |
| `backend/app/services/ai_service.py` | AI service integration |

---

## 📝 Changelog

| Date | Change |
|------|--------|
| 2025-04-12 | Added Gemini 3.1 Flash-Lite as primary MEDIUM tier model |
| 2025-04-12 | Updated failover chains for optimal free tier usage |
| 2025-04-12 | Added max_requests_per_minute tracking |

---

*Last Updated: April 12, 2025*
