# AGENT_COMMS.md — Week 4 Day 6
# Last updated: 2026-04-01
# Current status: WEEK 4 DAY 6 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 6 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-04-01

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 COMPLETE ✅ — Auth API, License API, Auth Core, License Manager. 138 tests.
> Day 2 COMPLETE ✅ — Support API, Dashboard API, Billing API, Compliance API. 106 tests.
> Day 3 COMPLETE ✅ — Support Service, Analytics Service, Billing Service, Onboarding Service. 136 tests.
> Day 4 COMPLETE ✅ — Jarvis API, Analytics API, Integrations API, Notification Service. 137 tests.
> Day 5 COMPLETE ✅ — Shopify/Stripe Webhooks, Compliance Service, SLA/License/User Services. 132 tests.
> **Total: 649+ tests passing.**
>
> Day 6: Building AI/ML integration layer — Smart Router, AI Tier Manager, Prompt Templates, Conversation Manager.
> All 4 files are INDEPENDENT — build in PARALLEL.
>
> **CRITICAL RULES:**
> 1. You CANNOT use Docker locally — write tests with MOCKED databases
> 2. Build → Unit Test passes → THEN push (ONE push only)
> 3. NEVER push before test passes
> 4. Type hints on ALL functions, docstrings on ALL classes/functions
> 5. AI safety checks REQUIRED before any LLM call

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/ai/smart_router.py`

**Purpose:** Smart Router — Routes customer queries to appropriate AI tier based on complexity, sentiment, and company settings.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/support_ticket.py` — SupportTicket model with AITierEnum
- `shared/core_functions/config.py` — Configuration with LLM providers
- `shared/core_functions/logger.py` — Logger
- `backend/services/analytics_service.py` — Analytics for routing metrics

**Step 3: Create the AI Directory**
```bash
mkdir -p backend/ai
touch backend/ai/__init__.py
```

**Step 4: Create the Smart Router File**

Create `backend/ai/smart_router.py` with:

```python
"""
PARWA Smart Router.

Routes customer queries to appropriate AI tier based on complexity,
sentiment, and company settings. Implements cost-optimized AI routing.
"""
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime
from enum import Enum
import re

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class QueryComplexity(str, Enum):
    """Query complexity levels."""
    SIMPLE = "simple"      # FAQ, basic questions
    MEDIUM = "medium"      # Multi-step, context needed
    COMPLEX = "complex"    # Requires reasoning, multi-turn
    CRITICAL = "critical"  # Escalation, sensitive topics


class SentimentScore(str, Enum):
    """Sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    ESCALATION_NEEDED = "escalation_needed"


class AITier(str, Enum):
    """AI tier levels."""
    LIGHT = "light"    # Fast, cheap - for simple queries
    MEDIUM = "medium"  # Balanced - for moderate queries
    HEAVY = "heavy"    # Powerful - for complex queries


# Complexity indicators
SIMPLE_INDICATORS = [
    r"\bwhat is\b", r"\bhow do i\b", r"\bwhere can i\b",
    r"\bhours\b", r"\bcontact\b", r"\bprice\b", r"\bcost\b",
    r"\bfaq\b", r"\bhelp\b", r"\bsimple\b"
]

COMPLEX_INDICATORS = [
    r"\brefund\b", r"\bdispute\b", r"\bescalat\b", r"\bmanager\b",
    r"\bcomplaint\b", r"\blegal\b", r"\battorney\b", r"\bsue\b",
    r"\bproblem\b", r"\bissue\b", r"\bnot working\b", r"\bbroken\b"
]

ESCALATION_INDICATORS = [
    r"\bspeak to.*human\b", r"\breal person\b", r"\bagent\b",
    r"\bsupervisor\b", r"\bmanager\b", r"\bcomplaint\b",
    r"\bnever.*again\b", r"\bcancel.*subscription\b", r"\bdelete.*account\b"
]


class SmartRouter:
    """
    Smart Router for AI tier selection.
    
    Routes queries to appropriate AI tier based on:
    - Query complexity analysis
    - Sentiment detection
    - Customer tier/subscription level
    - Company AI settings and budget
    """
    
    # Tier cost multipliers (relative cost per query)
    TIER_COSTS = {
        AITier.LIGHT: 1.0,
        AITier.MEDIUM: 3.0,
        AITier.HEAVY: 10.0,
    }
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        company_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize Smart Router.
        
        Args:
            company_id: Company UUID for settings lookup
            company_settings: Company-specific routing settings
        """
        self.company_id = company_id
        self.company_settings = company_settings or {}
    
    def analyze_complexity(self, query: str) -> QueryComplexity:
        """
        Analyze query complexity.
        
        Args:
            query: Customer query text
            
        Returns:
            QueryComplexity level
        """
        if not query:
            return QueryComplexity.SIMPLE
        
        query_lower = query.lower()
        
        # Check for escalation indicators first
        for pattern in ESCALATION_INDICATORS:
            if re.search(pattern, query_lower):
                return QueryComplexity.CRITICAL
        
        # Check for complex indicators
        complex_count = sum(
            1 for pattern in COMPLEX_INDICATORS
            if re.search(pattern, query_lower)
        )
        if complex_count >= 2:
            return QueryComplexity.COMPLEX
        elif complex_count == 1:
            return QueryComplexity.MEDIUM
        
        # Check for simple indicators
        for pattern in SIMPLE_INDICATORS:
            if re.search(pattern, query_lower):
                return QueryComplexity.SIMPLE
        
        # Check query length as fallback
        word_count = len(query.split())
        if word_count <= 10:
            return QueryComplexity.SIMPLE
        elif word_count <= 30:
            return QueryComplexity.MEDIUM
        else:
            return QueryComplexity.COMPLEX
    
    def detect_sentiment(self, query: str) -> SentimentScore:
        """
        Detect sentiment from query.
        
        Args:
            query: Customer query text
            
        Returns:
            SentimentScore classification
        """
        if not query:
            return SentimentScore.NEUTRAL
        
        query_lower = query.lower()
        
        # Escalation sentiment
        escalation_words = ["angry", "furious", "unacceptable", "terrible", 
                           "worst", "hate", "never again", "lawyer", "sue"]
        for word in escalation_words:
            if word in query_lower:
                return SentimentScore.ESCALATION_NEEDED
        
        # Negative sentiment
        negative_words = ["disappointed", "frustrated", "upset", "annoyed",
                         "problem", "issue", "wrong", "bad", "poor"]
        negative_count = sum(1 for word in negative_words if word in query_lower)
        if negative_count >= 2:
            return SentimentScore.NEGATIVE
        
        # Positive sentiment
        positive_words = ["thank", "great", "excellent", "amazing", 
                         "wonderful", "helpful", "appreciate"]
        for word in positive_words:
            if word in query_lower:
                return SentimentScore.POSITIVE
        
        return SentimentScore.NEUTRAL
    
    def select_tier(
        self,
        query: str,
        customer_tier: Optional[str] = None,
        budget_remaining: Optional[float] = None
    ) -> Tuple[AITier, Dict[str, Any]]:
        """
        Select appropriate AI tier for query.
        
        Args:
            query: Customer query text
            customer_tier: Customer subscription tier (affects priority)
            budget_remaining: Remaining AI budget for period
            
        Returns:
            Tuple of (AITier, routing_metadata dict)
        """
        complexity = self.analyze_complexity(query)
        sentiment = self.detect_sentiment(query)
        
        routing_metadata = {
            "complexity": complexity.value,
            "sentiment": sentiment.value,
            "customer_tier": customer_tier,
            "budget_remaining": budget_remaining,
            "routed_at": datetime.utcnow().isoformat(),
        }
        
        # Critical complexity or escalation sentiment -> Heavy tier
        if complexity == QueryComplexity.CRITICAL or sentiment == SentimentScore.ESCALATION_NEEDED:
            selected_tier = AITier.HEAVY
            routing_metadata["reason"] = "critical_or_escalation"
        
        # Complex queries -> Heavy tier
        elif complexity == QueryComplexity.COMPLEX:
            selected_tier = AITier.HEAVY
            routing_metadata["reason"] = "complex_query"
        
        # Medium complexity or negative sentiment -> Medium tier
        elif complexity == QueryComplexity.MEDIUM or sentiment == SentimentScore.NEGATIVE:
            selected_tier = AITier.MEDIUM
            routing_metadata["reason"] = "moderate_complexity_or_negative"
        
        # Simple queries -> Light tier
        else:
            selected_tier = AITier.LIGHT
            routing_metadata["reason"] = "simple_query"
        
        # Budget check - downgrade if necessary
        if budget_remaining is not None and budget_remaining < 10.0:
            if selected_tier == AITier.HEAVY:
                selected_tier = AITier.MEDIUM
                routing_metadata["budget_downgrade"] = True
            elif selected_tier == AITier.MEDIUM:
                selected_tier = AITier.LIGHT
                routing_metadata["budget_downgrade"] = True
        
        routing_metadata["selected_tier"] = selected_tier.value
        routing_metadata["estimated_cost"] = self.TIER_COSTS[selected_tier]
        
        logger.info({
            "event": "smart_router_tier_selected",
            "company_id": str(self.company_id) if self.company_id else None,
            "selected_tier": selected_tier.value,
            "complexity": complexity.value,
            "sentiment": sentiment.value,
        })
        
        return selected_tier, routing_metadata
    
    def get_model_for_tier(self, tier: AITier, provider: Optional[str] = None) -> str:
        """
        Get the model name for a given tier and provider.
        
        Args:
            tier: AI tier level
            provider: LLM provider (google, cerebras, groq)
            
        Returns:
            Model name string
        """
        provider = provider or settings.llm_primary_provider
        llm_config = settings.get_llm_config(provider)
        
        tier_model_map = {
            AITier.LIGHT: "light",
            AITier.MEDIUM: "medium",
            AITier.HEAVY: "heavy",
        }
        
        model_key = tier_model_map.get(tier, "medium")
        return llm_config["models"].get(model_key, "gemma-2-9b-it")
    
    def estimate_cost(
        self,
        query: str,
        tier: Optional[AITier] = None
    ) -> float:
        """
        Estimate cost for processing query.
        
        Args:
            query: Customer query text
            tier: AI tier (auto-selected if not provided)
            
        Returns:
            Estimated cost in credits
        """
        if tier is None:
            tier, _ = self.select_tier(query)
        
        # Base cost by tier
        base_cost = self.TIER_COSTS[tier]
        
        # Adjust for query length (token estimate)
        token_estimate = len(query.split()) / 4  # Rough estimate
        length_multiplier = max(1.0, token_estimate / 100)
        
        return base_cost * length_multiplier
```

**Step 5: Create the Test File**

Create `tests/unit/test_smart_router_new.py`:

```python
"""
Unit tests for Smart Router.
"""
import os
import uuid
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.ai.smart_router import (
    SmartRouter,
    QueryComplexity,
    SentimentScore,
    AITier,
)


class TestQueryComplexity:
    """Tests for query complexity analysis."""
    
    def test_simple_query(self):
        """Test simple query detection."""
        router = SmartRouter()
        
        result = router.analyze_complexity("What are your hours?")
        assert result == QueryComplexity.SIMPLE
    
    def test_complex_query(self):
        """Test complex query detection."""
        router = SmartRouter()
        
        result = router.analyze_complexity("I want a refund and I need to speak to a manager about this terrible issue")
        assert result == QueryComplexity.CRITICAL
    
    def test_empty_query(self):
        """Test empty query returns simple."""
        router = SmartRouter()
        
        result = router.analyze_complexity("")
        assert result == QueryComplexity.SIMPLE


class TestSentimentDetection:
    """Tests for sentiment detection."""
    
    def test_positive_sentiment(self):
        """Test positive sentiment detection."""
        router = SmartRouter()
        
        result = router.detect_sentiment("Thank you so much for your help!")
        assert result == SentimentScore.POSITIVE
    
    def test_negative_sentiment(self):
        """Test negative sentiment detection."""
        router = SmartRouter()
        
        result = router.detect_sentiment("I am very frustrated and disappointed with this service")
        assert result == SentimentScore.NEGATIVE
    
    def test_escalation_sentiment(self):
        """Test escalation sentiment detection."""
        router = SmartRouter()
        
        result = router.detect_sentiment("I am furious! I want to speak to a lawyer!")
        assert result == SentimentScore.ESCALATION_NEEDED
    
    def test_neutral_sentiment(self):
        """Test neutral sentiment detection."""
        router = SmartRouter()
        
        result = router.detect_sentiment("What is the status of my order?")
        assert result == SentimentScore.NEUTRAL


class TestTierSelection:
    """Tests for AI tier selection."""
    
    def test_simple_query_light_tier(self):
        """Test simple query gets light tier."""
        router = SmartRouter()
        
        tier, metadata = router.select_tier("What are your hours?")
        assert tier == AITier.LIGHT
    
    def test_critical_query_heavy_tier(self):
        """Test critical query gets heavy tier."""
        router = SmartRouter()
        
        tier, metadata = router.select_tier("I need to speak to a manager immediately!")
        assert tier == AITier.HEAVY
    
    def test_budget_downgrade(self):
        """Test budget constraint causes downgrade."""
        router = SmartRouter()
        
        tier, metadata = router.select_tier(
            "This is a complex problem that needs attention",
            budget_remaining=5.0
        )
        assert metadata.get("budget_downgrade") == True


class TestModelSelection:
    """Tests for model selection."""
    
    def test_get_model_for_tier(self):
        """Test getting model for tier."""
        router = SmartRouter()
        
        model = router.get_model_for_tier(AITier.LIGHT)
        assert isinstance(model, str)
        assert len(model) > 0


class TestCostEstimation:
    """Tests for cost estimation."""
    
    def test_estimate_cost_light(self):
        """Test cost estimation for light tier."""
        router = SmartRouter()
        
        cost = router.estimate_cost("Simple query", AITier.LIGHT)
        assert cost > 0
    
    def test_estimate_cost_heavy(self):
        """Test cost estimation for heavy tier."""
        router = SmartRouter()
        
        cost = router.estimate_cost("Complex query", AITier.HEAVY)
        assert cost > 0
    
    def test_estimate_cost_auto_tier(self):
        """Test cost estimation with auto tier selection."""
        router = SmartRouter()
        
        cost = router.estimate_cost("What are your hours?")
        assert cost > 0
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_smart_router_new.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/ai/__init__.py backend/ai/smart_router.py tests/unit/test_smart_router_new.py
git commit -m "Week 4 Day 6: Builder 1 - Smart Router with complexity and sentiment analysis"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/ai/tier_manager.py`

**Purpose:** AI Tier Manager — Manages AI model configurations, health checks, and failover between providers.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/ai/smart_router.py` — Smart Router (Builder 1)
- `shared/core_functions/config.py` — LLM provider config
- `shared/core_functions/logger.py` — Logger

**Step 3: Create the Tier Manager File**

Create `backend/ai/tier_manager.py` with:

```python
"""
PARWA AI Tier Manager.

Manages AI model configurations, health checks, and provider failover.
Ensures reliable AI service with automatic fallback.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ProviderStatus(str, Enum):
    """LLM Provider status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AITierManager:
    """
    AI Tier Manager for model configuration and failover.
    
    Features:
    - Model configuration per provider and tier
    - Health monitoring for providers
    - Automatic failover to backup providers
    - Rate limiting and quota management
    """
    
    # Provider health tracking
    _provider_health: Dict[str, ProviderStatus] = {}
    _provider_last_check: Dict[str, datetime] = {}
    _provider_error_count: Dict[str, int] = {}
    
    # Rate limiting
    _request_counts: Dict[str, int] = {}
    _request_windows: Dict[str, datetime] = {}
    
    HEALTH_CHECK_INTERVAL = 60  # seconds
    ERROR_THRESHOLD = 5  # errors before marking unhealthy
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX = 100  # requests per window
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        default_provider: Optional[str] = None
    ) -> None:
        """
        Initialize AI Tier Manager.
        
        Args:
            company_id: Company UUID
            default_provider: Default LLM provider
        """
        self.company_id = company_id
        self.default_provider = default_provider or settings.llm_primary_provider
    
    def get_provider_config(
        self,
        provider: Optional[str] = None,
        tier: str = "medium"
    ) -> Dict[str, Any]:
        """
        Get configuration for a specific provider and tier.
        
        Args:
            provider: LLM provider name
            tier: AI tier (light, medium, heavy)
            
        Returns:
            Dict with provider configuration
        """
        provider = provider or self.default_provider
        llm_config = settings.get_llm_config(provider)
        
        return {
            "provider": provider,
            "model": llm_config["models"].get(tier, "gemma-2-9b-it"),
            "base_url": llm_config["base_url"],
            "api_key": llm_config["api_key"],
        }
    
    def get_healthy_provider(self) -> str:
        """
        Get a healthy provider, with fallback.
        
        Returns:
            Provider name that is healthy
        """
        # Check primary provider
        if self._is_provider_healthy(self.default_provider):
            return self.default_provider
        
        # Fallback to secondary provider
        fallback = settings.llm_fallback_provider
        if self._is_provider_healthy(fallback):
            logger.warning({
                "event": "provider_failover",
                "primary": self.default_provider,
                "fallback": fallback,
            })
            return fallback
        
        # All providers potentially unhealthy - return primary anyway
        logger.error({
            "event": "all_providers_unhealthy",
            "returning_primary": self.default_provider,
        })
        return self.default_provider
    
    def _is_provider_healthy(self, provider: str) -> bool:
        """Check if a provider is healthy."""
        status = self._provider_health.get(provider, ProviderStatus.UNKNOWN)
        return status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED, ProviderStatus.UNKNOWN)
    
    def record_success(self, provider: str) -> None:
        """
        Record a successful request to a provider.
        
        Args:
            provider: Provider name
        """
        self._provider_health[provider] = ProviderStatus.HEALTHY
        self._provider_error_count[provider] = 0
        self._provider_last_check[provider] = datetime.utcnow()
        
        logger.debug({
            "event": "provider_success",
            "provider": provider,
        })
    
    def record_error(self, provider: str, error: str) -> None:
        """
        Record an error with a provider.
        
        Args:
            provider: Provider name
            error: Error message
        """
        error_count = self._provider_error_count.get(provider, 0) + 1
        self._provider_error_count[provider] = error_count
        
        if error_count >= self.ERROR_THRESHOLD:
            self._provider_health[provider] = ProviderStatus.UNHEALTHY
        else:
            self._provider_health[provider] = ProviderStatus.DEGRADED
        
        logger.warning({
            "event": "provider_error",
            "provider": provider,
            "error": error,
            "error_count": error_count,
            "status": self._provider_health[provider].value,
        })
    
    def check_rate_limit(self, provider: str) -> bool:
        """
        Check if we're within rate limits for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            True if within limits, False if exceeded
        """
        now = datetime.utcnow()
        window_start = self._request_windows.get(provider)
        
        # Reset window if expired
        if window_start is None or (now - window_start).total_seconds() > self.RATE_LIMIT_WINDOW:
            self._request_windows[provider] = now
            self._request_counts[provider] = 0
        
        # Check count
        count = self._request_counts.get(provider, 0)
        if count >= self.RATE_LIMIT_MAX:
            logger.warning({
                "event": "rate_limit_exceeded",
                "provider": provider,
                "count": count,
                "limit": self.RATE_LIMIT_MAX,
            })
            return False
        
        # Increment count
        self._request_counts[provider] = count + 1
        return True
    
    def get_provider_status(self, provider: str) -> Dict[str, Any]:
        """
        Get status information for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Dict with status information
        """
        return {
            "provider": provider,
            "status": self._provider_health.get(provider, ProviderStatus.UNKNOWN).value,
            "error_count": self._provider_error_count.get(provider, 0),
            "last_check": self._provider_last_check.get(provider, None),
            "request_count": self._request_counts.get(provider, 0),
        }
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """
        Get status for all configured providers.
        
        Returns:
            List of provider status dicts
        """
        providers = [self.default_provider, settings.llm_fallback_provider]
        return [self.get_provider_status(p) for p in providers if p]
```

**Step 5: Create the Test File**

Create `tests/unit/test_tier_manager.py`:

```python
"""
Unit tests for AI Tier Manager.
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.ai.tier_manager import (
    AITierManager,
    ProviderStatus,
)


class TestAITierManager:
    """Tests for AI Tier Manager."""
    
    def test_init(self):
        """Test initialization."""
        manager = AITierManager()
        assert manager.default_provider is not None
    
    def test_get_provider_config(self):
        """Test getting provider config."""
        manager = AITierManager()
        
        config = manager.get_provider_config(tier="light")
        assert "provider" in config
        assert "model" in config
    
    def test_get_healthy_provider(self):
        """Test getting healthy provider."""
        manager = AITierManager()
        
        provider = manager.get_healthy_provider()
        assert provider is not None
        assert isinstance(provider, str)
    
    def test_record_success(self):
        """Test recording success."""
        manager = AITierManager()
        
        manager.record_success("google")
        status = manager.get_provider_status("google")
        assert status["status"] == ProviderStatus.HEALTHY.value
    
    def test_record_error(self):
        """Test recording error."""
        manager = AITierManager()
        
        manager.record_error("google", "Test error")
        status = manager.get_provider_status("google")
        assert status["error_count"] == 1
    
    def test_error_threshold_unhealthy(self):
        """Test that errors make provider unhealthy."""
        manager = AITierManager()
        
        # Record errors up to threshold
        for i in range(manager.ERROR_THRESHOLD):
            manager.record_error("google", f"Error {i}")
        
        status = manager.get_provider_status("google")
        assert status["status"] == ProviderStatus.UNHEALTHY.value
    
    def test_rate_limit(self):
        """Test rate limiting."""
        manager = AITierManager()
        manager.RATE_LIMIT_MAX = 5
        
        # Should pass for first 5
        for i in range(5):
            assert manager.check_rate_limit("google") == True
        
        # Should fail on 6th
        assert manager.check_rate_limit("google") == False
    
    def test_get_all_status(self):
        """Test getting all provider status."""
        manager = AITierManager()
        
        statuses = manager.get_all_status()
        assert isinstance(statuses, list)
        assert len(statuses) > 0
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_tier_manager.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/ai/tier_manager.py tests/unit/test_tier_manager.py
git commit -m "Week 4 Day 6: Builder 2 - AI Tier Manager with provider failover"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/ai/prompt_templates.py`

**Purpose:** Prompt Templates — Reusable prompt templates for different conversation scenarios.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `shared/core_functions/logger.py` — Logger
- `shared/core_functions/config.py` — Configuration

**Step 3: Create the Prompt Templates File**

Create `backend/ai/prompt_templates.py` with:

```python
"""
PARWA Prompt Templates.

Reusable prompt templates for different conversation scenarios.
All templates include safety constraints and company context injection.
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from string import Template

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class PromptType(str, Enum):
    """Types of prompts."""
    CUSTOMER_SERVICE = "customer_service"
    TECHNICAL_SUPPORT = "technical_support"
    SALES_INQUIRY = "sales_inquiry"
    COMPLAINT_HANDLING = "complaint_handling"
    FAQ_RESPONSE = "faq_response"
    ESCALATION_SUMMARY = "escalation_summary"
    SENTIMENT_ANALYSIS = "sentiment_analysis"


class PromptTemplate:
    """
    Prompt template with variable substitution.
    
    Features:
    - Safe variable substitution
    - Safety constraint injection
    - Company context support
    """
    
    SAFETY_CONSTRAINTS = """
SAFETY CONSTRAINTS:
- Never share sensitive customer data from other companies
- Never process refunds without human approval
- Never make legal or medical claims
- Always escalate sensitive topics to human agents
- Maintain professional and helpful tone
"""
    
    def __init__(
        self,
        template: str,
        prompt_type: PromptType,
        variables: Optional[List[str]] = None,
        include_safety: bool = True
    ) -> None:
        """
        Initialize prompt template.
        
        Args:
            template: Template string with $variable placeholders
            prompt_type: Type of prompt
            variables: List of required variable names
            include_safety: Whether to include safety constraints
        """
        self.template = template
        self.prompt_type = prompt_type
        self.variables = variables or []
        self.include_safety = include_safety
    
    def render(
        self,
        context: Dict[str, Any],
        company_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render the prompt with context variables.
        
        Args:
            context: Variable values for substitution
            company_context: Company-specific context
            
        Returns:
            Rendered prompt string
        """
        # Build full context
        full_context = context.copy()
        
        if company_context:
            full_context["company_name"] = company_context.get("name", "our company")
            full_context["company_context"] = self._format_company_context(company_context)
        
        # Add safety constraints
        if self.include_safety:
            full_context["safety_constraints"] = self.SAFETY_CONSTRAINTS
        
        # Substitute variables
        try:
            rendered = Template(self.template).substitute(full_context)
        except KeyError as e:
            logger.error({
                "event": "prompt_template_missing_variable",
                "missing": str(e),
                "required": self.variables,
            })
            raise ValueError(f"Missing required variable: {e}")
        
        return rendered
    
    def _format_company_context(self, context: Dict[str, Any]) -> str:
        """Format company context for prompt."""
        parts = []
        if context.get("name"):
            parts.append(f"Company: {context['name']}")
        if context.get("industry"):
            parts.append(f"Industry: {context['industry']}")
        if context.get("support_hours"):
            parts.append(f"Support Hours: {context['support_hours']}")
        return "\n".join(parts)


# Pre-defined templates
TEMPLATES = {
    PromptType.CUSTOMER_SERVICE: PromptTemplate(
        template="""You are a helpful customer service assistant for $company_name.

$company_context

$safety_constraints

CUSTOMER MESSAGE:
$customer_message

Respond helpfully and professionally. If you cannot resolve the issue, offer to escalate to a human agent.""",
        prompt_type=PromptType.CUSTOMER_SERVICE,
        variables=["customer_message"],
    ),
    
    PromptType.TECHNICAL_SUPPORT: PromptTemplate(
        template="""You are a technical support specialist for $company_name.

$company_context

$safety_constraints

TECHNICAL ISSUE:
$customer_message

Provide step-by-step troubleshooting guidance. If the issue is complex or security-related, escalate immediately.""",
        prompt_type=PromptType.TECHNICAL_SUPPORT,
        variables=["customer_message"],
    ),
    
    PromptType.COMPLAINT_HANDLING: PromptTemplate(
        template="""You are handling a customer complaint for $company_name.

$company_context

$safety_constraints

CUSTOMER COMPLAINT:
$customer_message

Guidelines:
1. Acknowledge the customer's frustration
2. Apologize for the inconvenience
3. Offer a concrete solution or next step
4. Never promise refunds without approval
5. Escalate if customer remains dissatisfied after 2 attempts""",
        prompt_type=PromptType.COMPLAINT_HANDLING,
        variables=["customer_message"],
    ),
    
    PromptType.SENTIMENT_ANALYSIS: PromptTemplate(
        template="""Analyze the sentiment of this customer message.

CUSTOMER MESSAGE:
$customer_message

Respond with one of: POSITIVE, NEUTRAL, NEGATIVE, or ESCALATION_NEEDED
Then briefly explain why.""",
        prompt_type=PromptType.SENTIMENT_ANALYSIS,
        variables=["customer_message"],
        include_safety=False,
    ),
    
    PromptType.ESCALATION_SUMMARY: PromptTemplate(
        template="""Create a brief summary for escalation to a human agent.

$company_context

CUSTOMER ISSUE:
$customer_message

CONVERSATION HISTORY:
$conversation_history

Create a concise summary including:
1. Customer's main concern
2. Attempted solutions
3. Reason for escalation
4. Recommended actions""",
        prompt_type=PromptType.ESCALATION_SUMMARY,
        variables=["customer_message", "conversation_history"],
    ),
}


def get_template(prompt_type: PromptType) -> PromptTemplate:
    """
    Get a prompt template by type.
    
    Args:
        prompt_type: Type of prompt
        
    Returns:
        PromptTemplate instance
    """
    if prompt_type not in TEMPLATES:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    return TEMPLATES[prompt_type]


def render_prompt(
    prompt_type: PromptType,
    context: Dict[str, Any],
    company_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Render a prompt by type.
    
    Args:
        prompt_type: Type of prompt
        context: Variable values
        company_context: Company-specific context
        
    Returns:
        Rendered prompt string
    """
    template = get_template(prompt_type)
    return template.render(context, company_context)
```

**Step 5: Create the Test File**

Create `tests/unit/test_prompt_templates.py`:

```python
"""
Unit tests for Prompt Templates.
"""
import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.ai.prompt_templates import (
    PromptTemplate,
    PromptType,
    TEMPLATES,
    get_template,
    render_prompt,
)


class TestPromptTypeEnum:
    """Tests for PromptType enum."""
    
    def test_prompt_types_exist(self):
        """Test all prompt types are defined."""
        assert PromptType.CUSTOMER_SERVICE.value == "customer_service"
        assert PromptType.TECHNICAL_SUPPORT.value == "technical_support"
        assert PromptType.COMPLAINT_HANDLING.value == "complaint_handling"
        assert PromptType.SENTIMENT_ANALYSIS.value == "sentiment_analysis"


class TestPromptTemplate:
    """Tests for PromptTemplate class."""
    
    def test_render_basic(self):
        """Test basic template rendering."""
        template = PromptTemplate(
            template="Hello $name!",
            prompt_type=PromptType.FAQ_RESPONSE,
            variables=["name"],
            include_safety=False
        )
        
        result = template.render({"name": "World"})
        assert result == "Hello World!"
    
    def test_render_with_safety(self):
        """Test template with safety constraints."""
        template = PromptTemplate(
            template="Help with: $query",
            prompt_type=PromptType.CUSTOMER_SERVICE,
            variables=["query"],
            include_safety=True
        )
        
        result = template.render({"query": "test"})
        assert "SAFETY CONSTRAINTS" in result
        assert "test" in result
    
    def test_render_with_company_context(self):
        """Test template with company context."""
        template = PromptTemplate(
            template="Welcome to $company_name!",
            prompt_type=PromptType.CUSTOMER_SERVICE,
            variables=[],
            include_safety=False
        )
        
        result = template.render(
            {},
            company_context={"name": "TestCorp", "industry": "Tech"}
        )
        assert "TestCorp" in result
    
    def test_missing_variable_raises_error(self):
        """Test missing variable raises ValueError."""
        template = PromptTemplate(
            template="Hello $name!",
            prompt_type=PromptType.FAQ_RESPONSE,
            variables=["name"],
            include_safety=False
        )
        
        with pytest.raises(ValueError):
            template.render({})


class TestGetTemplate:
    """Tests for get_template function."""
    
    def test_get_customer_service_template(self):
        """Test getting customer service template."""
        template = get_template(PromptType.CUSTOMER_SERVICE)
        assert template.prompt_type == PromptType.CUSTOMER_SERVICE
    
    def test_get_invalid_template_raises_error(self):
        """Test invalid template type raises error."""
        # This should work for all defined types
        for pt in PromptType:
            template = get_template(pt)
            assert template is not None


class TestRenderPrompt:
    """Tests for render_prompt function."""
    
    def test_render_customer_service_prompt(self):
        """Test rendering customer service prompt."""
        result = render_prompt(
            PromptType.CUSTOMER_SERVICE,
            {"customer_message": "I need help with my order"}
        )
        assert "customer service" in result.lower()
        assert "I need help with my order" in result
    
    def test_render_sentiment_analysis(self):
        """Test rendering sentiment analysis prompt."""
        result = render_prompt(
            PromptType.SENTIMENT_ANALYSIS,
            {"customer_message": "This is terrible!"}
        )
        assert "terrible" in result
        assert "POSITIVE" in result or "NEGATIVE" in result


class TestTemplatesDict:
    """Tests for TEMPLATES dictionary."""
    
    def test_templates_exist(self):
        """Test that all expected templates exist."""
        assert PromptType.CUSTOMER_SERVICE in TEMPLATES
        assert PromptType.TECHNICAL_SUPPORT in TEMPLATES
        assert PromptType.COMPLAINT_HANDLING in TEMPLATES
        assert PromptType.SENTIMENT_ANALYSIS in TEMPLATES
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_prompt_templates.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/ai/prompt_templates.py tests/unit/test_prompt_templates.py
git commit -m "Week 4 Day 6: Builder 3 - Prompt Templates with safety constraints"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/ai/conversation_manager.py`

**Purpose:** Conversation Manager — Manages multi-turn conversations with context preservation and memory.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/ai/smart_router.py` — Smart Router (Builder 1)
- `backend/ai/tier_manager.py` — Tier Manager (Builder 2)
- `backend/ai/prompt_templates.py` — Prompt Templates (Builder 3)
- `shared/core_functions/logger.py` — Logger

**Step 3: Create the Conversation Manager File**

Create `backend/ai/conversation_manager.py` with:

```python
"""
PARWA Conversation Manager.

Manages multi-turn conversations with context preservation,
memory management, and turn tracking.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from collections import deque

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ConversationStatus(str, Enum):
    """Conversation status."""
    ACTIVE = "active"
    WAITING = "waiting"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class MessageRole(str, Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message:
    """Represents a single message in a conversation."""
    
    def __init__(
        self,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a message.
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (tokens, model, etc.)
        """
        self.id = uuid4()
        self.role = role
        self.content = content
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": str(self.id),
            "role": self.role.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class Conversation:
    """
    Represents a conversation with message history.
    
    Features:
    - Message history with configurable limit
    - Context preservation across turns
    - Turn counting and management
    - Escalation detection
    """
    
    MAX_HISTORY = 50  # Maximum messages to keep
    MAX_TURNS = 20    # Maximum turns before suggesting escalation
    
    def __init__(
        self,
        conversation_id: Optional[UUID] = None,
        company_id: Optional[UUID] = None,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize a conversation.
        
        Args:
            conversation_id: Conversation UUID (generated if not provided)
            company_id: Company UUID
            customer_id: Customer identifier
            channel: Communication channel (chat, email, etc.)
            metadata: Additional metadata
        """
        self.id = conversation_id or uuid4()
        self.company_id = company_id
        self.customer_id = customer_id
        self.channel = channel
        self.metadata = metadata or {}
        
        self.messages: deque = deque(maxlen=self.MAX_HISTORY)
        self.status = ConversationStatus.ACTIVE
        self.turn_count = 0
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def add_message(
        self,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """
        Add a message to the conversation.
        
        Args:
            role: Message role
            content: Message content
            metadata: Optional metadata
            
        Returns:
            The created Message instance
        """
        message = Message(role, content, metadata)
        self.messages.append(message)
        
        # Update turn count for user messages
        if role == MessageRole.USER:
            self.turn_count += 1
        
        self.updated_at = datetime.now(timezone.utc)
        
        logger.info({
            "event": "conversation_message_added",
            "conversation_id": str(self.id),
            "role": role.value,
            "turn_count": self.turn_count,
        })
        
        return message
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get conversation history.
        
        Args:
            limit: Maximum messages to return
            
        Returns:
            List of message dictionaries
        """
        messages = list(self.messages)
        if limit:
            messages = messages[-limit:]
        return [m.to_dict() for m in messages]
    
    def get_context_for_llm(self, max_tokens: int = 4000) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM.
        
        Args:
            max_tokens: Approximate token limit
            
        Returns:
            List of messages in LLM format [{"role": ..., "content": ...}]
        """
        # Rough estimate: 4 chars per token
        max_chars = max_tokens * 4
        
        context = []
        total_chars = 0
        
        # Add messages from newest to oldest until limit
        for message in reversed(self.messages):
            msg_chars = len(message.content)
            if total_chars + msg_chars > max_chars:
                break
            
            context.insert(0, {
                "role": message.role.value,
                "content": message.content,
            })
            total_chars += msg_chars
        
        return context
    
    def should_suggest_escalation(self) -> bool:
        """
        Check if escalation should be suggested.
        
        Returns:
            True if conversation should be escalated
        """
        return self.turn_count >= self.MAX_TURNS
    
    def escalate(self, reason: Optional[str] = None) -> None:
        """
        Mark conversation as escalated.
        
        Args:
            reason: Reason for escalation
        """
        self.status = ConversationStatus.ESCALATED
        self.metadata["escalation_reason"] = reason
        self.metadata["escalated_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info({
            "event": "conversation_escalated",
            "conversation_id": str(self.id),
            "reason": reason,
            "turn_count": self.turn_count,
        })
    
    def resolve(self) -> None:
        """Mark conversation as resolved."""
        self.status = ConversationStatus.RESOLVED
        self.metadata["resolved_at"] = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            "id": str(self.id),
            "company_id": str(self.company_id) if self.company_id else None,
            "customer_id": self.customer_id,
            "channel": self.channel,
            "status": self.status.value,
            "turn_count": self.turn_count,
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class ConversationManager:
    """
    Manages multiple conversations with memory and context.
    
    Features:
    - Create and retrieve conversations
    - Message history management
    - Active conversation tracking
    - Conversation summarization triggers
    """
    
    def __init__(self, max_conversations: int = 1000) -> None:
        """
        Initialize conversation manager.
        
        Args:
            max_conversations: Maximum conversations to keep in memory
        """
        self._conversations: Dict[UUID, Conversation] = {}
        self._max_conversations = max_conversations
    
    def create_conversation(
        self,
        company_id: Optional[UUID] = None,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            company_id: Company UUID
            customer_id: Customer identifier
            channel: Communication channel
            metadata: Additional metadata
            
        Returns:
            Created Conversation instance
        """
        # Clean up if at limit
        if len(self._conversations) >= self._max_conversations:
            self._cleanup_old_conversations()
        
        conversation = Conversation(
            company_id=company_id,
            customer_id=customer_id,
            channel=channel,
            metadata=metadata
        )
        
        self._conversations[conversation.id] = conversation
        
        logger.info({
            "event": "conversation_created",
            "conversation_id": str(conversation.id),
            "company_id": str(company_id) if company_id else None,
            "channel": channel,
        })
        
        return conversation
    
    def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Conversation if found, None otherwise
        """
        return self._conversations.get(conversation_id)
    
    def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation UUID
            role: Message role
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Message if conversation found, None otherwise
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        return conversation.add_message(role, content, metadata)
    
    def get_active_conversations(
        self,
        company_id: Optional[UUID] = None
    ) -> List[Conversation]:
        """
        Get active conversations, optionally filtered by company.
        
        Args:
            company_id: Filter by company
            
        Returns:
            List of active conversations
        """
        conversations = [
            c for c in self._conversations.values()
            if c.status == ConversationStatus.ACTIVE
        ]
        
        if company_id:
            conversations = [
                c for c in conversations
                if c.company_id == company_id
            ]
        
        return conversations
    
    def _cleanup_old_conversations(self) -> None:
        """Remove oldest resolved/abandoned conversations."""
        to_remove = []
        
        for conv_id, conv in self._conversations.items():
            if conv.status in (ConversationStatus.RESOLVED, ConversationStatus.ABANDONED):
                to_remove.append(conv_id)
        
        # Remove half of old conversations
        for conv_id in to_remove[:len(to_remove) // 2]:
            del self._conversations[conv_id]
        
        logger.info({
            "event": "conversations_cleaned_up",
            "removed_count": len(to_remove) // 2,
        })
```

**Step 5: Create the Test File**

Create `tests/unit/test_conversation_manager.py`:

```python
"""
Unit tests for Conversation Manager.
"""
import os
import uuid
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.ai.conversation_manager import (
    Message,
    MessageRole,
    Conversation,
    ConversationStatus,
    ConversationManager,
)


class TestMessage:
    """Tests for Message class."""
    
    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(MessageRole.USER, "Hello!")
        
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.id is not None
    
    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(MessageRole.ASSISTANT, "Hi there!")
        
        data = msg.to_dict()
        assert data["role"] == "assistant"
        assert data["content"] == "Hi there!"


class TestConversation:
    """Tests for Conversation class."""
    
    def test_conversation_creation(self):
        """Test creating a conversation."""
        conv = Conversation()
        
        assert conv.id is not None
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.turn_count == 0
    
    def test_add_message(self):
        """Test adding messages."""
        conv = Conversation()
        
        conv.add_message(MessageRole.USER, "Hello")
        conv.add_message(MessageRole.ASSISTANT, "Hi there!")
        
        assert len(conv.messages) == 2
        assert conv.turn_count == 1  # Only user messages count
    
    def test_get_history(self):
        """Test getting history."""
        conv = Conversation()
        
        conv.add_message(MessageRole.USER, "Message 1")
        conv.add_message(MessageRole.ASSISTANT, "Response 1")
        conv.add_message(MessageRole.USER, "Message 2")
        
        history = conv.get_history()
        assert len(history) == 3
    
    def test_get_context_for_llm(self):
        """Test getting LLM context."""
        conv = Conversation()
        
        conv.add_message(MessageRole.USER, "Hello")
        conv.add_message(MessageRole.ASSISTANT, "Hi there!")
        
        context = conv.get_context_for_llm()
        assert len(context) == 2
        assert context[0]["role"] == "user"
    
    def test_should_suggest_escalation(self):
        """Test escalation suggestion."""
        conv = Conversation()
        conv.MAX_TURNS = 3
        
        for i in range(3):
            conv.add_message(MessageRole.USER, f"Message {i}")
        
        assert conv.should_suggest_escalation() == True
    
    def test_escalate(self):
        """Test escalating conversation."""
        conv = Conversation()
        
        conv.escalate("Customer requested")
        
        assert conv.status == ConversationStatus.ESCALATED
        assert "escalation_reason" in conv.metadata
    
    def test_resolve(self):
        """Test resolving conversation."""
        conv = Conversation()
        
        conv.resolve()
        
        assert conv.status == ConversationStatus.RESOLVED


class TestConversationManager:
    """Tests for ConversationManager class."""
    
    def test_create_conversation(self):
        """Test creating conversation via manager."""
        manager = ConversationManager()
        
        conv = manager.create_conversation()
        assert conv.id is not None
        assert conv.status == ConversationStatus.ACTIVE
    
    def test_get_conversation(self):
        """Test getting conversation by ID."""
        manager = ConversationManager()
        
        created = manager.create_conversation()
        retrieved = manager.get_conversation(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_add_message_via_manager(self):
        """Test adding message via manager."""
        manager = ConversationManager()
        
        conv = manager.create_conversation()
        msg = manager.add_message(conv.id, MessageRole.USER, "Hello!")
        
        assert msg is not None
        assert msg.content == "Hello!"
    
    def test_get_active_conversations(self):
        """Test getting active conversations."""
        manager = ConversationManager()
        
        conv1 = manager.create_conversation()
        conv2 = manager.create_conversation()
        conv2.resolve()
        
        active = manager.get_active_conversations()
        assert len(active) == 1


class TestMessageRole:
    """Tests for MessageRole enum."""
    
    def test_role_values(self):
        """Test message role values."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"


class TestConversationStatus:
    """Tests for ConversationStatus enum."""
    
    def test_status_values(self):
        """Test conversation status values."""
        assert ConversationStatus.ACTIVE.value == "active"
        assert ConversationStatus.ESCALATED.value == "escalated"
        assert ConversationStatus.RESOLVED.value == "resolved"
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_conversation_manager.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/ai/conversation_manager.py tests/unit/test_conversation_manager.py
git commit -m "Week 4 Day 6: Builder 4 - Conversation Manager with multi-turn support"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/ai/smart_router.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_smart_router_new.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 2 → STATUS
**File:** `backend/ai/tier_manager.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_tier_manager.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 3 → STATUS
**File:** `backend/ai/prompt_templates.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_prompt_templates.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 4 → STATUS
**File:** `backend/ai/conversation_manager.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_conversation_manager.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS FOR ALL BUILDERS:**

1. **AI Safety Checks** — All prompts MUST include safety constraints
2. **Provider Failover** — Tier Manager must handle provider failures gracefully
3. **Token Limits** — Respect context limits when building LLM context
4. **Company Scoping** — All AI operations should be company-aware
5. **No Docker** — Use mocked sessions in tests
6. **One Push Only** — Push ONLY after all tests pass

---

═══════════════════════════════════════════════════════════════════════════════
## ASSISTANCE AGENT → RESPONSE
═══════════════════════════════════════════════════════════════════════════════

[Assistance Agent will provide help here when activated]
