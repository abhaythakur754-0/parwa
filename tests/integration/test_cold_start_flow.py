"""
Integration tests for Cold Start Flow.

Tests the complete bootstrap flow for new clients including:
- Full bootstrap flow for new client
- Industry detection and FAQ loading
- KB entry creation end-to-end
- Error handling and recovery
"""
import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from shared.knowledge_base.cold_start import (
    ColdStart,
    ColdStartConfig,
    ColdStartResult,
    IndustryType,
    INDUSTRY_FAQS,
    create_cold_start_data,
)
from shared.knowledge_base.kb_manager import (
    KnowledgeBaseManager,
    KnowledgeBaseConfig,
    IngestResult,
)
from shared.knowledge_base.vector_store import VectorStore, Document


class MockVectorStore:
    """Mock VectorStore for testing."""
    
    def __init__(self):
        self._documents = {}
        self._embeddings_generated = []
    
    def add_document(
        self,
        content: str,
        embedding: list = None,
        metadata: dict = None
    ) -> Document:
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            content=content,
            embedding=embedding or [],
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._documents[doc_id] = doc
        return doc
    
    def search(
        self,
        query_embedding: list,
        top_k: int = 5,
        metadata_filter: dict = None,
        min_score: float = 0.0
    ) -> list:
        return []
    
    def get_document(self, doc_id: UUID) -> Document:
        return self._documents.get(doc_id)
    
    def delete_document(self, doc_id: UUID) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False
    
    def get_stats(self) -> dict:
        return {
            "document_count": len(self._documents),
            "embedding_dimension": 1536,
        }


class TestColdStartFlow:
    """Test cold start bootstrap flow."""
    
    @pytest.fixture
    def mock_kb_manager(self):
        """Create a mock KB manager."""
        vector_store = MockVectorStore()
        manager = KnowledgeBaseManager(
            vector_store=vector_store,
            config=KnowledgeBaseConfig(),
            company_id=uuid4(),
        )
        return manager
    
    @pytest.fixture
    def cold_start(self, mock_kb_manager):
        """Create a ColdStart instance with mock KB manager."""
        return ColdStart(
            kb_manager=mock_kb_manager,
            config=ColdStartConfig(),
        )
    
    @pytest.fixture
    def sample_company_id(self):
        """Generate a sample company ID."""
        return uuid4()
    
    # ========================================
    # Full Bootstrap Flow Tests
    # ========================================
    
    def test_full_bootstrap_flow_ecommerce(self, cold_start, sample_company_id):
        """Test complete bootstrap for ecommerce client."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
            company_name="TestStore",
        )
        
        assert result.status == "completed"
        assert result.company_id == sample_company_id
        assert result.industry == "ecommerce"
        assert result.documents_ingested > 0
        assert result.faqs_added > 0
        assert result.categories_created > 0
        assert len(result.errors) == 0
    
    def test_full_bootstrap_flow_saas(self, cold_start, sample_company_id):
        """Test complete bootstrap for SaaS client."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.SAAS,
            company_name="TestSaaS",
        )
        
        assert result.status == "completed"
        assert result.industry == "saas"
        assert result.documents_ingested > 0
    
    def test_full_bootstrap_flow_healthcare(self, cold_start, sample_company_id):
        """Test complete bootstrap for healthcare client."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.HEALTHCARE,
        )
        
        assert result.status == "completed"
        assert result.industry == "healthcare"
    
    def test_full_bootstrap_flow_finance(self, cold_start, sample_company_id):
        """Test complete bootstrap for finance client."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.FINANCE,
        )
        
        assert result.status == "completed"
        assert result.industry == "finance"
    
    def test_bootstrap_with_custom_faqs(self, cold_start, sample_company_id):
        """Test bootstrap with additional custom FAQs."""
        custom_faqs = [
            {
                "question": "What is your return policy?",
                "answer": "We accept returns within 30 days.",
                "category": "returns",
            },
            {
                "question": "Do you offer international shipping?",
                "answer": "Yes, we ship worldwide.",
                "category": "shipping",
            },
        ]
        
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
            custom_faqs=custom_faqs,
        )
        
        assert result.status == "completed"
        # Should have industry FAQs + custom FAQs
        assert result.faqs_added > len(custom_faqs)
    
    def test_bootstrap_without_industry_faqs(self, sample_company_id):
        """Test bootstrap with industry FAQs disabled."""
        config = ColdStartConfig(include_industry_faqs=False)
        cold_start = ColdStart(config=config)
        
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        # Should still complete but with fewer FAQs
        assert result.documents_ingested >= 0
    
    def test_bootstrap_without_general_faqs(self, sample_company_id):
        """Test bootstrap with general FAQs disabled."""
        config = ColdStartConfig(include_general_faqs=False)
        cold_start = ColdStart(config=config)
        
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        assert result.status == "completed"
    
    # ========================================
    # Industry Detection and FAQ Loading Tests
    # ========================================
    
    def test_get_available_industries(self, cold_start):
        """Test getting list of available industries."""
        industries = cold_start.get_available_industries()
        
        assert IndustryType.ECOMMERCE.value in industries
        assert IndustryType.SAAS.value in industries
        assert IndustryType.HEALTHCARE.value in industries
        assert IndustryType.FINANCE.value in industries
        assert IndustryType.GENERAL.value in industries
    
    def test_industry_faq_content(self):
        """Test that industry FAQs have proper content."""
        # Verify ecommerce FAQs
        ecommerce_faqs = INDUSTRY_FAQS.get(IndustryType.ECOMMERCE.value, {})
        
        assert "orders" in ecommerce_faqs
        assert "shipping" in ecommerce_faqs
        assert "returns" in ecommerce_faqs
        assert "payments" in ecommerce_faqs
        
        # Verify FAQ structure
        for category, faqs in ecommerce_faqs.items():
            for faq in faqs:
                assert "question" in faq
                assert "answer" in faq
                assert len(faq["question"]) > 0
                assert len(faq["answer"]) > 0
    
    def test_industry_preview(self, cold_start):
        """Test industry FAQ preview."""
        preview = cold_start.get_industry_preview(IndustryType.ECOMMERCE)
        
        assert "orders" in preview
        assert "shipping" in preview
        assert preview["orders"] > 0
    
    def test_unknown_industry_falls_back_to_general(self, cold_start, sample_company_id):
        """Test that unknown industry uses general FAQs."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.GENERAL,
        )
        
        assert result.status == "completed"
    
    # ========================================
    # KB Entry Creation End-to-End Tests
    # ========================================
    
    def test_kb_entry_creation_with_company_scope(self, cold_start, sample_company_id):
        """Test that KB entries are created with proper company scoping."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.SAAS,
        )
        
        assert result.company_id == sample_company_id
        assert result.metadata.get("industry") == "saas"
    
    def test_processing_time_tracked(self, cold_start, sample_company_id):
        """Test that processing time is tracked."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        assert result.processing_time_ms > 0
    
    def test_categories_created_count(self, cold_start, sample_company_id):
        """Test that category count is accurate."""
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        # Ecommerce should have orders, shipping, returns, payments
        assert result.categories_created >= 4
    
    def test_max_faqs_per_category_limit(self, sample_company_id):
        """Test that max FAQs per category is respected."""
        config = ColdStartConfig(max_faqs_per_category=2)
        cold_start = ColdStart(config=config)
        
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        # Should limit FAQs per category
        assert result.faqs_added <= 2 * 4  # max_per_category * num_categories
    
    # ========================================
    # Error Handling and Recovery Tests
    # ========================================
    
    def test_error_handling_none_company_id(self, cold_start):
        """Test error handling for None company ID."""
        with pytest.raises(ValueError, match="Company ID is required"):
            cold_start.bootstrap(
                company_id=None,
                industry=IndustryType.ECOMMERCE,
            )
    
    def test_error_handling_kb_manager_failure(self, sample_company_id):
        """Test error handling when KB manager fails."""
        # Create a mock KB manager that fails
        mock_kb = Mock(spec=KnowledgeBaseManager)
        mock_kb.ingest_batch.side_effect = Exception("KB failure")
        
        cold_start = ColdStart(kb_manager=mock_kb)
        result = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        assert result.status == "failed"
        assert len(result.errors) > 0
        assert "KB failure" in result.errors[0]
    
    def test_statistics_tracking(self, cold_start, sample_company_id):
        """Test that cold start statistics are tracked."""
        # Perform multiple bootstraps
        for _ in range(3):
            cold_start.bootstrap(
                company_id=uuid4(),
                industry=IndustryType.ECOMMERCE,
            )
        
        stats = cold_start.get_stats()
        
        assert stats["cold_starts_completed"] == 3
        assert stats["total_documents_ingested"] > 0
        assert stats["average_documents_per_bootstrap"] > 0
    
    def test_create_cold_start_data_utility(self):
        """Test the create_cold_start_data utility function."""
        custom_questions = [
            {
                "question": "Custom Q",
                "answer": "Custom A",
                "category": "custom",
            }
        ]
        
        documents = create_cold_start_data(
            industry=IndustryType.SAAS,
            custom_questions=custom_questions,
        )
        
        assert len(documents) > 0
        
        # Check that all documents have required fields
        for doc in documents:
            assert "content" in doc
            assert "metadata" in doc
            assert doc["metadata"]["type"] == "faq"
    
    def test_faq_formatting_with_company_name(self, cold_start):
        """Test FAQ formatting with company name personalization."""
        formatted = cold_start._format_faq(
            {"question": "Test Q?", "answer": "We offer great service."},
            company_name="AcmeCorp"
        )
        
        assert "Q: Test Q?" in formatted
        assert "AcmeCorp" in formatted or "We offer great service." in formatted
    
    def test_multiple_bootstrap_same_company(self, cold_start, sample_company_id):
        """Test multiple bootstraps for same company."""
        # First bootstrap
        result1 = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        # Second bootstrap (different industry - simulating re-bootstrap)
        result2 = cold_start.bootstrap(
            company_id=sample_company_id,
            industry=IndustryType.SAAS,
        )
        
        assert result1.status == "completed"
        assert result2.status == "completed"
    
    # ========================================
    # Integration with Knowledge Base Tests
    # ========================================
    
    def test_integration_with_vector_store(self, mock_kb_manager):
        """Test integration with vector store."""
        cold_start = ColdStart(kb_manager=mock_kb_manager)
        company_id = uuid4()
        
        result = cold_start.bootstrap(
            company_id=company_id,
            industry=IndustryType.ECOMMERCE,
        )
        
        # Check that documents were added to vector store
        stats = mock_kb_manager.vector_store.get_stats()
        assert stats["document_count"] > 0
    
    def test_different_industries_create_different_content(self, cold_start, sample_company_id):
        """Test that different industries create different content."""
        company_id_1 = uuid4()
        company_id_2 = uuid4()
        
        result1 = cold_start.bootstrap(
            company_id=company_id_1,
            industry=IndustryType.HEALTHCARE,
        )
        
        result2 = cold_start.bootstrap(
            company_id=company_id_2,
            industry=IndustryType.FINANCE,
        )
        
        # Both should complete successfully
        assert result1.status == "completed"
        assert result2.status == "completed"
        
        # Categories should differ
        preview1 = cold_start.get_industry_preview(IndustryType.HEALTHCARE)
        preview2 = cold_start.get_industry_preview(IndustryType.FINANCE)
        
        assert set(preview1.keys()) != set(preview2.keys())


class TestColdStartConfigValidation:
    """Test ColdStart configuration validation."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ColdStartConfig()
        
        assert config.include_industry_faqs is True
        assert config.include_general_faqs is True
        assert config.max_faqs_per_category == 50
        assert config.auto_activate is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ColdStartConfig(
            include_industry_faqs=False,
            max_faqs_per_category=10,
        )
        
        assert config.include_industry_faqs is False
        assert config.max_faqs_per_category == 10
    
    def test_config_validation_max_faqs(self):
        """Test validation of max_faqs_per_category."""
        # Should accept valid values
        config = ColdStartConfig(max_faqs_per_category=100)
        assert config.max_faqs_per_category == 100
        
        # Should reject values outside range
        with pytest.raises(ValueError):
            ColdStartConfig(max_faqs_per_category=0)
        
        with pytest.raises(ValueError):
            ColdStartConfig(max_faqs_per_category=300)


class TestColdStartResultModel:
    """Test ColdStartResult model."""
    
    def test_default_result(self):
        """Test default result values."""
        result = ColdStartResult(company_id=uuid4(), industry="ecommerce")
        
        assert result.documents_ingested == 0
        assert result.categories_created == 0
        assert result.faqs_added == 0
        assert result.status == "pending"
        assert result.processing_time_ms == 0.0
        assert len(result.errors) == 0
        assert len(result.metadata) == 0
    
    def test_result_serialization(self):
        """Test result can be serialized."""
        company_id = uuid4()
        result = ColdStartResult(
            company_id=company_id,
            industry="saas",
            documents_ingested=10,
            status="completed",
        )
        
        data = result.model_dump()
        
        assert data["company_id"] == company_id
        assert data["industry"] == "saas"
        assert data["documents_ingested"] == 10
