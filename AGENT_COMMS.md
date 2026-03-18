# AGENT_COMMS.md — Week 6 Day 1-5
# Last updated: Manager Agent
# Current status: WEEK 6 READY TO START

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 6 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: Week 6 Start

> **Phase: Phase 2 — Core AI Engine (TRIVYA Techniques + Confidence + Sentiment)**
>
> **Week 6 Goals:**
> - Day 1: TRIVYA Tier 1 chain (clara → crp → gsd_integration → orchestrator)
> - Day 2: TRIVYA Tier 2 chain (trigger_detector → chain_of_thought → react → reverse_thinking → step_back → thread_of_thought)
> - Day 3: Confidence + Compliance tests (thresholds → scorer → tests)
> - Day 4: Sentiment chain (analyzer → routing_rules)
> - Day 5: Cold start + T1+T2 integration tests
> - Day 6: Tester Agent runs full week integration test
>
> **CRITICAL RULES:**
> 1. Within-day files CAN depend on each other — build in order listed
> 2. Across-day files CANNOT depend on each other — days run in parallel
> 3. You CANNOT use Docker locally — write tests with MOCKED databases
> 4. Build → Unit Test passes → THEN push (ONE push only per file)
> 5. NEVER push before test passes
> 6. Type hints on ALL functions, docstrings on ALL classes/functions

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/trivya_techniques/tier1/clara.py`
2. `shared/trivya_techniques/tier1/crp.py`
3. `shared/trivya_techniques/tier1/gsd_integration.py`
4. `shared/trivya_techniques/orchestrator.py`
5. `tests/unit/test_trivya_tier1.py`

**Purpose:** Build TRIVYA Tier 1 techniques — CLARA (Context-Aware Retrieval), CRP (Compressed Response Protocol), GSD integration, and the main orchestrator.

### DEPENDENCIES FROM PREVIOUS WEEKS
- `shared/knowledge_base/rag_pipeline.py` (Wk5) — for CLARA retrieval
- `shared/knowledge_base/hyde.py` (Wk5) — for HyDE generation
- `shared/gsd_engine/state_engine.py` (Wk5) — for GSD integration
- `shared/core_functions/config.py` (Wk1)
- `shared/smart_router/router.py` (Wk5)

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
- `shared/knowledge_base/rag_pipeline.py`
- `shared/knowledge_base/hyde.py`
- `shared/gsd_engine/state_engine.py`
- `shared/smart_router/router.py`
- `shared/core_functions/config.py`
- `shared/core_functions/logger.py`

**Step 3: Create Directories**
```bash
mkdir -p shared/trivya_techniques/tier1
touch shared/trivya_techniques/__init__.py
touch shared/trivya_techniques/tier1/__init__.py
```

**Step 4: Create clara.py**

Create `shared/trivya_techniques/tier1/clara.py`:

```python
"""
TRIVYA Tier 1 - CLARA (Context-Aware Retrieval and Response Assembly).

CLARA is the first tier technique that fires on every query.
It retrieves relevant context from the knowledge base and assembles
a response using the retrieved information.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CLARA:
    """
    Context-Aware Retrieval and Response Assembly.
    
    CLARA is TRIVYA's Tier 1 technique that processes every query:
    1. Retrieves relevant context from KB
    2. Assembles response using context
    3. Provides confidence score for response
    
    Always fires regardless of query complexity.
    """
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        kb_manager: Optional[Any] = None
    ) -> None:
        """
        Initialize CLARA.
        
        Args:
            company_id: Company UUID for KB scoping
            kb_manager: Knowledge base manager instance
        """
        self.company_id = company_id
        self.kb_manager = kb_manager
    
    def retrieve_context(
        self,
        query: str,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from knowledge base.
        
        Args:
            query: Customer query
            max_chunks: Maximum chunks to retrieve
            
        Returns:
            List of relevant context chunks
        """
        if not self.kb_manager:
            logger.warning({
                "event": "clara_no_kb_manager",
                "company_id": str(self.company_id),
            })
            return []
        
        try:
            # Use KB manager to retrieve relevant docs
            context = self.kb_manager.retrieve(
                query=query,
                company_id=self.company_id,
                limit=max_chunks
            )
            
            logger.info({
                "event": "clara_context_retrieved",
                "company_id": str(self.company_id),
                "query_length": len(query),
                "chunks_found": len(context),
            })
            
            return context
        except Exception as e:
            logger.error({
                "event": "clara_retrieval_error",
                "error": str(e),
            })
            return []
    
    def assemble_response(
        self,
        query: str,
        context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assemble response using retrieved context.
        
        Args:
            query: Customer query
            context: Retrieved context chunks
            
        Returns:
            Dict with response and metadata
        """
        # Calculate context relevance
        total_relevance = sum(c.get("score", 0) for c in context)
        avg_relevance = total_relevance / len(context) if context else 0
        
        # Determine if context is sufficient
        has_sufficient_context = avg_relevance > 0.5 and len(context) > 0
        
        response = {
            "query": query,
            "context_used": len(context),
            "avg_relevance": avg_relevance,
            "has_sufficient_context": has_sufficient_context,
            "context_chunks": [
                {
                    "content": c.get("content", "")[:200],
                    "score": c.get("score", 0),
                }
                for c in context[:3]  # Top 3 chunks
            ],
        }
        
        logger.info({
            "event": "clara_response_assembled",
            "context_chunks": len(context),
            "avg_relevance": avg_relevance,
            "sufficient": has_sufficient_context,
        })
        
        return response
    
    def process(self, query: str) -> Dict[str, Any]:
        """
        Process a query through CLARA pipeline.
        
        Args:
            query: Customer query
            
        Returns:
            Dict with retrieval and assembly results
        """
        context = self.retrieve_context(query)
        response = self.assemble_response(query, context)
        
        return {
            "technique": "CLARA",
            "tier": 1,
            "query": query,
            "context": context,
            "response": response,
        }
```

**Step 5: Create crp.py**

Create `shared/trivya_techniques/tier1/crp.py`:

```python
"""
TRIVYA Tier 1 - CRP (Compressed Response Protocol).

CRP compresses response content to reduce token usage
while preserving essential information.
"""
from typing import Dict, Any, List, Optional
import re

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class CRP:
    """
    Compressed Response Protocol.
    
    Compresses responses by:
    1. Removing redundant phrases
    2. Condensing verbose explanations
    3. Preserving key information
    4. Maintaining readability
    """
    
    # Redundant phrases to remove
    REDUNDANT_PHRASES = [
        r"\bAs an AI assistant,?\b",
        r"\bI would be happy to help you with that\.?\b",
        r"\bPlease let me know if you have any other questions\.?\b",
        r"\bI hope this helps\.?\b",
        r"\bIs there anything else I can help you with\??\b",
        r"\bFeel free to ask if you need anything else\.?\b",
    ]
    
    # Compression ratios
    TARGET_RATIO = 0.7  # Target 70% of original length
    MIN_LENGTH = 50  # Don't compress below 50 chars
    
    def __init__(self, target_ratio: float = TARGET_RATIO) -> None:
        """
        Initialize CRP.
        
        Args:
            target_ratio: Target compression ratio (0.7 = 70%)
        """
        self.target_ratio = target_ratio
    
    def compress(self, text: str) -> str:
        """
        Compress text while preserving meaning.
        
        Args:
            text: Text to compress
            
        Returns:
            Compressed text
        """
        if not text or len(text) < self.MIN_LENGTH:
            return text
        
        original_length = len(text)
        compressed = text
        
        # Step 1: Remove redundant phrases
        for pattern in self.REDUNDANT_PHRASES:
            compressed = re.sub(pattern, "", compressed, flags=re.IGNORECASE)
        
        # Step 2: Clean up whitespace
        compressed = re.sub(r"\s+", " ", compressed).strip()
        
        # Step 3: Remove duplicate sentences
        sentences = compressed.split(". ")
        unique_sentences = []
        for s in sentences:
            s = s.strip()
            if s and s not in unique_sentences:
                unique_sentences.append(s)
        compressed = ". ".join(unique_sentences)
        
        # Ensure proper ending
        if compressed and not compressed.endswith((".", "!", "?")):
            compressed += "."
        
        new_length = len(compressed)
        compression_ratio = new_length / original_length if original_length > 0 else 1
        
        logger.info({
            "event": "crp_compression",
            "original_length": original_length,
            "new_length": new_length,
            "ratio": f"{compression_ratio:.2%}",
        })
        
        return compressed
    
    def compress_context(
        self,
        context: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compress multiple context chunks.
        
        Args:
            context: List of context chunks
            
        Returns:
            List of compressed chunks
        """
        compressed = []
        
        for chunk in context:
            content = chunk.get("content", "")
            if content:
                chunk_copy = chunk.copy()
                chunk_copy["content"] = self.compress(content)
                chunk_copy["compressed"] = True
                compressed.append(chunk_copy)
            else:
                compressed.append(chunk)
        
        return compressed
    
    def get_compression_stats(
        self,
        original: str,
        compressed: str
    ) -> Dict[str, Any]:
        """
        Get compression statistics.
        
        Args:
            original: Original text
            compressed: Compressed text
            
        Returns:
            Dict with compression stats
        """
        return {
            "original_length": len(original),
            "compressed_length": len(compressed),
            "reduction": len(original) - len(compressed),
            "ratio": len(compressed) / len(original) if len(original) > 0 else 1,
        }
```

**Step 6: Create gsd_integration.py**

Create `shared/trivya_techniques/tier1/gsd_integration.py`:

```python
"""
TRIVYA Tier 1 - GSD Integration.

Integrates TRIVYA techniques with the GSD State Engine
for conversation state management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class GSDIntegration:
    """
    GSD Integration for TRIVYA Tier 1.
    
    Manages:
    - Conversation state persistence
    - Context window management
    - Turn tracking
    - State transitions
    """
    
    def __init__(
        self,
        state_engine: Optional[Any] = None,
        conversation_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize GSD Integration.
        
        Args:
            state_engine: GSD State Engine instance
            conversation_id: Current conversation ID
        """
        self.state_engine = state_engine
        self.conversation_id = conversation_id
    
    def sync_context(
        self,
        trivya_context: Dict[str, Any]
    ) -> bool:
        """
        Sync TRIVYA context with GSD state.
        
        Args:
            trivya_context: Context from TRIVYA processing
            
        Returns:
            True if sync successful
        """
        if not self.state_engine or not self.conversation_id:
            logger.warning({
                "event": "gsd_integration_no_engine",
            })
            return False
        
        # Update GSD state with TRIVYA context
        conversation = self.state_engine.get_conversation(self.conversation_id)
        if conversation:
            conversation.metadata["trivya_context"] = trivya_context
            logger.info({
                "event": "gsd_context_synced",
                "conversation_id": str(self.conversation_id),
            })
            return True
        
        return False
    
    def get_conversation_context(self) -> Dict[str, Any]:
        """
        Get context from GSD for TRIVYA processing.
        
        Returns:
            Dict with conversation context
        """
        if not self.state_engine or not self.conversation_id:
            return {}
        
        conversation = self.state_engine.get_conversation(self.conversation_id)
        if not conversation:
            return {}
        
        return {
            "turn_count": conversation.context.turn_count,
            "message_count": len(conversation.messages),
            "total_tokens": conversation.get_token_count(),
            "status": conversation.status,
            "recent_messages": [
                {"role": m.role.value if hasattr(m.role, 'value') else m.role, "content": m.content[:100]}
                for m in conversation.messages[-5:]
            ],
        }
    
    def should_trigger_tier2(self) -> bool:
        """
        Check if Tier 2 techniques should be triggered.
        
        Returns:
            True if Tier 2 should be triggered
        """
        context = self.get_conversation_context()
        
        # Trigger T2 if:
        # - More than 3 turns (multiple exchanges)
        # - Previous TRIVYA context indicates complexity
        # - Total tokens approaching limit
        
        turn_count = context.get("turn_count", 0)
        token_count = context.get("total_tokens", 0)
        
        return turn_count >= 3 or token_count > 2000
```

**Step 7: Create orchestrator.py**

Create `shared/trivya_techniques/orchestrator.py`:

```python
"""
TRIVYA Orchestrator.

Orchestrates all TRIVYA techniques (Tier 1, 2, 3) and
coordinates their execution based on query characteristics.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings
from shared.trivya_techniques.tier1.clara import CLARA
from shared.trivya_techniques.tier1.crp import CRP
from shared.trivya_techniques.tier1.gsd_integration import GSDIntegration

logger = get_logger(__name__)
settings = get_settings()


class ProcessingTier(str, Enum):
    """Processing tier levels."""
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class TRIVYAOrchestrator:
    """
    TRIVYA Orchestrator.
    
    Coordinates execution of TRIVYA techniques:
    - Tier 1 (CLARA, CRP): Always fires on every query
    - Tier 2: Fires on complex/decision queries
    - Tier 3: Fires on high-stakes scenarios
    """
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        kb_manager: Optional[Any] = None,
        state_engine: Optional[Any] = None
    ) -> None:
        """
        Initialize TRIVYA Orchestrator.
        
        Args:
            company_id: Company UUID
            kb_manager: Knowledge base manager
            state_engine: GSD state engine
        """
        self.company_id = company_id
        self.kb_manager = kb_manager
        self.state_engine = state_engine
        
        # Initialize Tier 1 components
        self.clara = CLARA(company_id=company_id, kb_manager=kb_manager)
        self.crp = CRP()
    
    def process(
        self,
        query: str,
        conversation_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process a query through TRIVYA pipeline.
        
        Args:
            query: Customer query
            conversation_id: Optional conversation ID for state
            
        Returns:
            Dict with processing results
        """
        logger.info({
            "event": "trivya_processing_started",
            "company_id": str(self.company_id),
            "query_length": len(query),
        })
        
        # Initialize GSD integration if state engine available
        gsd_integration = None
        if self.state_engine and conversation_id:
            gsd_integration = GSDIntegration(
                state_engine=self.state_engine,
                conversation_id=conversation_id
            )
        
        # Tier 1: Always fire CLARA
        tier1_result = self._process_tier1(query, gsd_integration)
        
        # Determine if Tier 2 should fire
        tier2_result = None
        if self._should_fire_tier2(query, tier1_result, gsd_integration):
            tier2_result = self._process_tier2(query, tier1_result)
        
        # Assemble final result
        result = {
            "query": query,
            "company_id": str(self.company_id) if self.company_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "tier_1": tier1_result,
            "tier_2": tier2_result,
            "processing_tier": ProcessingTier.TIER_2.value if tier2_result else ProcessingTier.TIER_1.value,
        }
        
        logger.info({
            "event": "trivya_processing_complete",
            "processing_tier": result["processing_tier"],
        })
        
        return result
    
    def _process_tier1(
        self,
        query: str,
        gsd_integration: Optional[GSDIntegration]
    ) -> Dict[str, Any]:
        """
        Process through Tier 1 techniques.
        
        Args:
            query: Customer query
            gsd_integration: GSD integration instance
            
        Returns:
            Tier 1 processing results
        """
        # Get conversation context if available
        conv_context = {}
        if gsd_integration:
            conv_context = gsd_integration.get_conversation_context()
        
        # CLARA: Retrieve and assemble
        clara_result = self.clara.process(query)
        
        # CRP: Compress response
        compressed_context = self.crp.compress_context(
            clara_result.get("context", [])
        )
        
        return {
            "technique": "tier_1",
            "clara": clara_result,
            "crp": {
                "compressed_chunks": len(compressed_context),
            },
            "conversation_context": conv_context,
        }
    
    def _should_fire_tier2(
        self,
        query: str,
        tier1_result: Dict[str, Any],
        gsd_integration: Optional[GSDIntegration]
    ) -> bool:
        """
        Determine if Tier 2 should fire.
        
        Args:
            query: Customer query
            tier1_result: Tier 1 results
            gsd_integration: GSD integration
            
        Returns:
            True if Tier 2 should fire
        """
        # Check conversation turns
        if gsd_integration and gsd_integration.should_trigger_tier2():
            return True
        
        # Check context sufficiency
        clara_response = tier1_result.get("clara", {}).get("response", {})
        if not clara_response.get("has_sufficient_context", True):
            return True
        
        # Check query complexity indicators
        complexity_indicators = ["decision", "compare", "should i", "which is better", "recommend"]
        query_lower = query.lower()
        if any(indicator in query_lower for indicator in complexity_indicators):
            return True
        
        return False
    
    def _process_tier2(
        self,
        query: str,
        tier1_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process through Tier 2 techniques.
        
        Args:
            query: Customer query
            tier1_result: Tier 1 results
            
        Returns:
            Tier 2 processing results
        """
        # Tier 2 techniques will be implemented in Day 2
        # For now, return placeholder
        return {
            "technique": "tier_2",
            "status": "triggered",
            "note": "Tier 2 techniques to be implemented",
        }
```

**Step 8: Create test_trivya_tier1.py**

Create `tests/unit/test_trivya_tier1.py`:

```python
"""
Unit tests for TRIVYA Tier 1.
"""
import os
import uuid
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.trivya_techniques.tier1.clara import CLARA
from shared.trivya_techniques.tier1.crp import CRP
from shared.trivya_techniques.tier1.gsd_integration import GSDIntegration
from shared.trivya_techniques.orchestrator import TRIVYAOrchestrator, ProcessingTier


class TestCLARA:
    """Tests for CLARA technique."""
    
    def test_clara_initialization(self):
        """Test CLARA initializes correctly."""
        clara = CLARA()
        assert clara is not None
    
    def test_clara_retrieve_context_no_kb(self):
        """Test CLARA retrieval without KB manager."""
        clara = CLARA()
        
        context = clara.retrieve_context("What is your return policy?")
        assert context == []
    
    def test_clara_assemble_response(self):
        """Test CLARA response assembly."""
        clara = CLARA()
        
        context = [
            {"content": "Returns accepted within 30 days", "score": 0.9},
            {"content": "Items must be unused", "score": 0.7},
        ]
        
        response = clara.assemble_response("What is your return policy?", context)
        
        assert response["query"] == "What is your return policy?"
        assert response["context_used"] == 2
        assert response["has_sufficient_context"] == True
    
    def test_clara_process(self):
        """Test CLARA full process."""
        clara = CLARA()
        
        result = clara.process("Hello")
        
        assert result["technique"] == "CLARA"
        assert result["tier"] == 1


class TestCRP:
    """Tests for CRP compression."""
    
    def test_crp_compress_removes_redundant(self):
        """Test CRP removes redundant phrases."""
        crp = CRP()
        
        text = "As an AI assistant, I would be happy to help you with that. Your order will arrive in 3 days."
        compressed = crp.compress(text)
        
        assert "As an AI assistant" not in compressed
        assert "order will arrive" in compressed
    
    def test_crp_compress_short_text(self):
        """Test CRP doesn't compress short text."""
        crp = CRP()
        
        text = "Hello"
        compressed = crp.compress(text)
        
        assert compressed == "Hello"
    
    def test_crp_compress_preserves_meaning(self):
        """Test CRP preserves key information."""
        crp = CRP()
        
        text = "Your refund has been processed and will appear in 5-7 business days. Please let me know if you have any questions."
        compressed = crp.compress(text)
        
        assert "refund" in compressed.lower()
        assert "5-7" in compressed
    
    def test_crp_get_compression_stats(self):
        """Test CRP compression statistics."""
        crp = CRP()
        
        original = "This is a long text with many words."
        compressed = crp.compress(original)
        
        stats = crp.get_compression_stats(original, compressed)
        
        assert "original_length" in stats
        assert "compressed_length" in stats
        assert "ratio" in stats


class TestGSDIntegration:
    """Tests for GSD Integration."""
    
    def test_gsd_integration_initialization(self):
        """Test GSD integration initializes."""
        gsd = GSDIntegration()
        assert gsd is not None
    
    def test_gsd_get_context_no_engine(self):
        """Test GSD context without engine."""
        gsd = GSDIntegration()
        
        context = gsd.get_conversation_context()
        assert context == {}
    
    def test_gsd_should_trigger_tier2(self):
        """Test Tier 2 trigger logic."""
        gsd = GSDIntegration()
        
        # Without engine, should return False
        assert gsd.should_trigger_tier2() == False


class TestTRIVYAOrchestrator:
    """Tests for TRIVYA Orchestrator."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes."""
        orch = TRIVYAOrchestrator()
        assert orch is not None
    
    def test_orchestrator_process_query(self):
        """Test orchestrator processes query."""
        orch = TRIVYAOrchestrator()
        
        result = orch.process("What are your hours?")
        
        assert "query" in result
        assert "tier_1" in result
        assert result["processing_tier"] in [ProcessingTier.TIER_1.value, ProcessingTier.TIER_2.value]
    
    def test_orchestrator_tier1_always_fires(self):
        """Test that Tier 1 always fires."""
        orch = TRIVYAOrchestrator()
        
        result = orch.process("Hello")
        
        assert result["tier_1"] is not None
        assert result["tier_1"]["technique"] == "tier_1"
    
    def test_orchestrator_with_company_id(self):
        """Test orchestrator with company ID."""
        company_id = uuid.uuid4()
        orch = TRIVYAOrchestrator(company_id=company_id)
        
        result = orch.process("Test query")
        
        assert result["company_id"] == str(company_id)
```

**Step 9: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_trivya_tier1.py -v
```

**Step 10: Fix Until Pass, Then Push**
```bash
git add shared/trivya_techniques/ tests/unit/test_trivya_tier1.py
git commit -m "Week 6 Day 1: TRIVYA Tier 1 - CLARA, CRP, GSD Integration, Orchestrator"
git push origin main
```

**Step 11: Update Status Below**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/trivya_techniques/tier2/trigger_detector.py`
2. `shared/trivya_techniques/tier2/chain_of_thought.py`
3. `shared/trivya_techniques/tier2/react.py`
4. `shared/trivya_techniques/tier2/reverse_thinking.py`
5. `shared/trivya_techniques/tier2/step_back.py`
6. `shared/trivya_techniques/tier2/thread_of_thought.py`
7. `tests/unit/test_trivya_tier2.py`

**Purpose:** Build TRIVYA Tier 2 techniques — advanced reasoning methods for complex queries.

### DEPENDENCIES
- `shared/core_functions/config.py` (Wk1)
- `shared/gsd_engine/state_engine.py` (Wk5)

### KEY TESTS
- Test: detects decision_needed queries
- Test: produces step-by-step reasoning
- Test: reason+act loop runs
- Test: reverse approach produces output
- Test: abstracts question correctly
- Test: thread maintains context

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/confidence/thresholds.py`
2. `shared/confidence/scorer.py`
3. `tests/unit/test_confidence_scorer.py`
4. `tests/unit/test_compliance.py`
5. `tests/unit/test_audit_trail.py`

**Purpose:** Build Confidence scoring thresholds and scorer, plus compliance and audit trail tests.

### DEPENDENCIES
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/compliance.py` (Wk1)
- `shared/core_functions/audit_trail.py` (Wk1)

### KEY TESTS
- Test: GRADUATE=95%, ESCALATE=70%
- Test: weighted avg 40+30+20+10=100%

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/sentiment/analyzer.py`
2. `shared/sentiment/routing_rules.py`
3. `tests/unit/test_sentiment.py`

**Purpose:** Build Sentiment analyzer and routing rules for customer emotion detection.

### DEPENDENCIES
- `shared/smart_router/router.py` (Wk5)
- `shared/confidence/thresholds.py` (Wk6 D3)

### KEY TESTS
- Test: anger score routes to High pathway
- Test: routing rules apply correctly

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/knowledge_base/cold_start.py`
2. `tests/unit/test_trivya_tier1_tier2.py`

**Purpose:** Build Cold start for new client KB bootstrap and T1+T2 integration tests.

### DEPENDENCIES
- `shared/knowledge_base/kb_manager.py` (Wk5)
- All TRIVYA T1+T2 files (Wk6 D1-D2)

### KEY TESTS
- Test: bootstraps with industry FAQs
- Test: T1+T2 pipeline works end-to-end

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 (DAY 1) → STATUS
**Files:** `shared/trivya_techniques/tier1/` + `orchestrator.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_trivya_tier1.py`
**Pushed:** NO
**Notes:** Waiting to start

---

## BUILDER 2 (DAY 2) → STATUS
**Files:** `shared/trivya_techniques/tier2/` (6 files)
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_trivya_tier2.py`
**Pushed:** NO
**Notes:** Waiting to start

---

## BUILDER 3 (DAY 3) → STATUS
**Files:** `shared/confidence/` + tests
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** Multiple
**Pushed:** NO
**Notes:** Waiting to start

---

## BUILDER 4 (DAY 4) → STATUS
**Files:** `shared/sentiment/`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_sentiment.py`
**Pushed:** NO
**Notes:** Waiting to start

---

## BUILDER 5 (DAY 5) → STATUS
**Files:** `shared/knowledge_base/cold_start.py` + integration tests
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_trivya_tier1_tier2.py`
**Pushed:** NO
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

**Test Command:** `pytest tests/integration/test_week6_trivya.py -v`

**Verification Criteria:**
- TRIVYA orchestrator: Tier 1 fires on every query
- Tier 2 trigger: only activates on decision_needed or multi_step
- Confidence: 95%+ → GRADUATE, <70% → ESCALATE
- Sentiment: high anger score routes to PARWA High pathway
- All 6 Tier 2 techniques produce meaningfully different outputs
- Cold start: bootstraps new client KB correctly

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS FOR ALL BUILDERS:**

1. **Within-day dependencies OK** — Build files in order listed
2. **Across-day dependencies FORBIDDEN** — Don't import from other day's files
3. **No Docker** — Use mocked sessions in tests
4. **One Push Per File** — Push ONLY after test passes
5. **Type hints required** — All functions need type hints
6. **Docstrings required** — All classes and public functions need docstrings
7. **TRIVYA T1 always fires** — CLARA/CRP process every query
8. **TRIVYA T2 conditional** — Only fires on complex queries

---

═══════════════════════════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════════════════════════

[Team discussion items will be added here as needed]
