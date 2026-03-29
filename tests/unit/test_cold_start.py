"""
Unit Tests for Cold Start Service

Tests for industry detection, FAQ loading, KB bootstrap, and workflow setup.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.services.cold_start import (
    ColdStartService,
    ColdStartConfig,
    Industry,
    BootstrapStatus,
)
from backend.services.cold_start.analyzer import (
    IndustryAnalyzer,
    AnalysisResult,
    analyze_client,
)
from backend.services.cold_start.bootstrap import (
    KnowledgeBaseBootstrap,
    WorkflowSetup,
)


# ============================================================================
# Cold Start Service Tests
# ============================================================================

class TestColdStartService:
    """Tests for ColdStartService"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def cold_start_service(self, mock_db):
        """Create cold start service instance"""
        return ColdStartService(mock_db)
    
    @pytest.mark.asyncio
    async def test_bootstrap_client_ecommerce(self, cold_start_service):
        """Test bootstrapping an e-commerce client"""
        result = await cold_start_service.bootstrap_client(
            client_id="test_client_001",
            company_data={
                "name": "Test Shop",
                "description": "Online retail store selling electronics",
                "website": "https://testshop.com",
            }
        )
        
        assert result["client_id"] == "test_client_001"
        assert result["status"] == BootstrapStatus.COMPLETED.value
        assert result["industry"] in ["ecommerce", "general"]
        assert result["faqs_created"] > 0
        assert "bootstrapped_at" in result
    
    @pytest.mark.asyncio
    async def test_bootstrap_client_saas(self, cold_start_service):
        """Test bootstrapping a SaaS client"""
        result = await cold_start_service.bootstrap_client(
            client_id="test_client_002",
            company_data={
                "name": "Cloud Software Inc",
                "description": "SaaS platform for team collaboration and project management",
                "industry": "saas",
            }
        )
        
        assert result["client_id"] == "test_client_002"
        assert result["status"] == BootstrapStatus.COMPLETED.value
        assert result["industry"] == "saas"
    
    @pytest.mark.asyncio
    async def test_bootstrap_client_healthcare(self, cold_start_service):
        """Test bootstrapping a healthcare client"""
        result = await cold_start_service.bootstrap_client(
            client_id="test_client_003",
            company_data={
                "name": "City Medical Center",
                "description": "Hospital and outpatient clinic services",
            },
            industry_hint=Industry.HEALTHCARE,
        )
        
        assert result["client_id"] == "test_client_003"
        assert result["status"] == BootstrapStatus.COMPLETED.value
        assert result["industry"] == "healthcare"
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_custom_faqs(self, cold_start_service):
        """Test bootstrapping with custom FAQs"""
        custom_faqs = [
            {"question": "What is your warranty policy?", "category": "warranty", "priority": 1},
        ]
        
        result = await cold_start_service.bootstrap_client(
            client_id="test_client_004",
            company_data={"name": "Custom Store", "description": "Retail shop"},
            custom_faqs=custom_faqs,
        )
        
        assert result["status"] == BootstrapStatus.COMPLETED.value
        # Should have at least industry FAQs + custom FAQs
        assert result["faqs_created"] >= 1


class TestColdStartConfig:
    """Tests for ColdStartConfig"""
    
    def test_default_faq_count(self):
        """Test default FAQ count configuration"""
        config = ColdStartConfig()
        assert config.DEFAULT_FAQ_COUNT == 10
        assert config.MAX_FAQ_COUNT == 50
    
    def test_industry_keywords(self):
        """Test industry keywords are defined"""
        config = ColdStartConfig()
        assert Industry.ECOMMERCE in config.INDUSTRY_KEYWORDS
        assert "shop" in config.INDUSTRY_KEYWORDS[Industry.ECOMMERCE]
    
    def test_compliance_requirements(self):
        """Test compliance requirements by industry"""
        config = ColdStartConfig()
        assert "hipaa" in config.COMPLIANCE_REQUIREMENTS[Industry.HEALTHCARE]
        assert "pci_dss" in config.COMPLIANCE_REQUIREMENTS[Industry.FINANCIAL]


# ============================================================================
# Industry Analyzer Tests
# ============================================================================

class TestIndustryAnalyzer:
    """Tests for IndustryAnalyzer"""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return IndustryAnalyzer()
    
    @pytest.mark.asyncio
    async def test_detect_ecommerce_industry(self, analyzer):
        """Test detecting e-commerce industry"""
        result = await analyzer.analyze({
            "name": "Fashion Store",
            "description": "Online clothing and accessories shop with fast shipping",
            "website": "fashionstore.com",
        })
        
        assert isinstance(result, AnalysisResult)
        assert result.industry in ["ecommerce", "general"]
        assert 0 <= result.confidence <= 1
        assert len(result.keywords) > 0
    
    @pytest.mark.asyncio
    async def test_detect_saas_industry(self, analyzer):
        """Test detecting SaaS industry"""
        result = await analyzer.analyze({
            "name": "ProjectCloud",
            "description": "Cloud-based project management SaaS platform with API integrations",
            "industry": "saas",
        })
        
        assert result.industry == "saas"
        assert result.confidence == 1.0  # Explicit industry hint
    
    @pytest.mark.asyncio
    async def test_detect_healthcare_industry(self, analyzer):
        """Test detecting healthcare industry"""
        result = await analyzer.analyze({
            "name": "MedCare Clinic",
            "description": "Patient appointment scheduling and prescription management",
        })
        
        assert result.industry == "healthcare"
        assert "hipaa" in result.compliance_requirements
    
    @pytest.mark.asyncio
    async def test_detect_financial_industry(self, analyzer):
        """Test detecting financial industry"""
        result = await analyzer.analyze({
            "name": "Digital Bank",
            "description": "Online banking, loans, and investment services",
        })
        
        assert result.industry == "financial"
        assert "pci_dss" in result.compliance_requirements
    
    @pytest.mark.asyncio
    async def test_detect_logistics_industry(self, analyzer):
        """Test detecting logistics industry"""
        result = await analyzer.analyze({
            "name": "FastFreight",
            "description": "Freight shipping and warehouse logistics company",
        })
        
        assert result.industry == "logistics"
    
    @pytest.mark.asyncio
    async def test_extract_keywords(self, analyzer):
        """Test keyword extraction"""
        result = await analyzer.analyze({
            "name": "TechStore",
            "description": "E-commerce store selling technology products with shipping",
        })
        
        assert len(result.keywords) > 0
    
    @pytest.mark.asyncio
    async def test_suggest_faq_topics(self, analyzer):
        """Test FAQ topic suggestions"""
        result = await analyzer.analyze({
            "name": "Retail Shop",
            "description": "E-commerce retail store",
        })
        
        assert len(result.suggested_faq_topics) > 0
    
    @pytest.mark.asyncio
    async def test_identify_risk_factors(self, analyzer):
        """Test risk factor identification"""
        result = await analyzer.analyze({
            "name": "",  # Missing name
            "description": "Healthcare services",
        })
        
        assert "missing_name" in result.risk_factors


class TestAnalyzeClient:
    """Tests for the convenience analyze_client function"""
    
    def test_analyze_client_sync(self):
        """Test synchronous client analysis"""
        result = analyze_client({
            "name": "Test Company",
            "description": "E-commerce platform",
        })
        
        assert isinstance(result, AnalysisResult)
        assert result.industry is not None


# ============================================================================
# Knowledge Base Bootstrap Tests
# ============================================================================

class TestKnowledgeBaseBootstrap:
    """Tests for KnowledgeBaseBootstrap"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def kb_bootstrap(self, mock_db):
        """Create KB bootstrap instance"""
        return KnowledgeBaseBootstrap(mock_db)
    
    @pytest.mark.asyncio
    async def test_create_entries_ecommerce(self, kb_bootstrap):
        """Test creating KB entries for e-commerce"""
        result = await kb_bootstrap.create_entries(
            client_id="test_ecommerce_001",
            industry=Industry.ECOMMERCE,
        )
        
        assert result["success"] is True
        assert result["industry"] == "ecommerce"
        assert result["entries_created"] > 0
    
    @pytest.mark.asyncio
    async def test_create_entries_saas(self, kb_bootstrap):
        """Test creating KB entries for SaaS"""
        result = await kb_bootstrap.create_entries(
            client_id="test_saas_001",
            industry=Industry.SAAS,
        )
        
        assert result["success"] is True
        assert "billing" in result["categories"]
    
    @pytest.mark.asyncio
    async def test_create_entries_healthcare(self, kb_bootstrap):
        """Test creating KB entries for healthcare"""
        result = await kb_bootstrap.create_entries(
            client_id="test_healthcare_001",
            industry=Industry.HEALTHCARE,
        )
        
        assert result["success"] is True
        assert "appointments" in result["categories"]
    
    @pytest.mark.asyncio
    async def test_create_entries_with_custom_faqs(self, kb_bootstrap):
        """Test creating KB entries with custom FAQs"""
        custom_faqs = [
            {
                "question": "Custom question?",
                "answer": "Custom answer.",
                "category": "custom",
                "priority": 1,
            }
        ]
        
        result = await kb_bootstrap.create_entries(
            client_id="test_custom_001",
            industry=Industry.ECOMMERCE,
            custom_faqs=custom_faqs,
        )
        
        assert result["success"] is True
        assert result["entries_created"] >= 1
    
    @pytest.mark.asyncio
    async def test_initialize_search_index(self, kb_bootstrap):
        """Test search index initialization"""
        result = await kb_bootstrap._initialize_search_index("test_client")
        
        assert result is True


class TestWorkflowSetup:
    """Tests for WorkflowSetup"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return AsyncMock()
    
    @pytest.fixture
    def workflow_setup(self, mock_db):
        """Create workflow setup instance"""
        return WorkflowSetup(mock_db)
    
    @pytest.mark.asyncio
    async def test_setup_workflows_ecommerce(self, workflow_setup):
        """Test setting up e-commerce workflows"""
        result = await workflow_setup.setup_workflows(
            client_id="test_ecommerce_wf",
            industry=Industry.ECOMMERCE,
        )
        
        assert result["success"] is True
        assert "order_tracking" in result["workflows"]
        assert "refund_processing" in result["workflows"]
    
    @pytest.mark.asyncio
    async def test_setup_workflows_saas(self, workflow_setup):
        """Test setting up SaaS workflows"""
        result = await workflow_setup.setup_workflows(
            client_id="test_saas_wf",
            industry=Industry.SAAS,
        )
        
        assert result["success"] is True
        assert "onboarding" in result["workflows"]
        assert "subscription_management" in result["workflows"]
    
    @pytest.mark.asyncio
    async def test_setup_workflows_healthcare(self, workflow_setup):
        """Test setting up healthcare workflows"""
        result = await workflow_setup.setup_workflows(
            client_id="test_healthcare_wf",
            industry=Industry.HEALTHCARE,
        )
        
        assert result["success"] is True
        assert "appointment_scheduling" in result["workflows"]
    
    @pytest.mark.asyncio
    async def test_setup_workflows_with_custom(self, workflow_setup):
        """Test setting up workflows with custom additions"""
        custom_workflows = [
            {
                "name": "custom_workflow",
                "trigger": "custom_event",
                "actions": ["custom_action"],
                "active": True,
            }
        ]
        
        result = await workflow_setup.setup_workflows(
            client_id="test_custom_wf",
            industry=Industry.GENERAL,
            custom_workflows=custom_workflows,
        )
        
        assert result["success"] is True
        assert "custom_workflow" in result["workflows"]


# ============================================================================
# Integration Tests
# ============================================================================

class TestColdStartIntegration:
    """Integration tests for cold start flow"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_full_bootstrap_flow(self, mock_db):
        """Test full bootstrap flow from analysis to KB creation"""
        # Step 1: Analyze client
        analyzer = IndustryAnalyzer()
        analysis = await analyzer.analyze({
            "name": "Tech Startup",
            "description": "SaaS platform for developers with API and integrations",
        })
        
        assert analysis.industry == "saas"
        
        # Step 2: Bootstrap KB
        kb_bootstrap = KnowledgeBaseBootstrap(mock_db)
        kb_result = await kb_bootstrap.create_entries(
            client_id="integration_test_001",
            industry=Industry.SAAS,
        )
        
        assert kb_result["success"] is True
        
        # Step 3: Setup workflows
        workflow_setup = WorkflowSetup(mock_db)
        wf_result = await workflow_setup.setup_workflows(
            client_id="integration_test_001",
            industry=Industry.SAAS,
        )
        
        assert wf_result["success"] is True
        
        # Step 4: Full bootstrap with service
        service = ColdStartService(mock_db)
        result = await service.bootstrap_client(
            client_id="integration_test_001",
            company_data={"name": "Tech Startup"},
            industry_hint=Industry.SAAS,
        )
        
        assert result["status"] == BootstrapStatus.COMPLETED.value


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def analyzer(self):
        return IndustryAnalyzer()
    
    @pytest.fixture
    def cold_start_service(self, mock_db):
        return ColdStartService(mock_db)
    
    @pytest.mark.asyncio
    async def test_empty_company_data(self, analyzer):
        """Test analysis with empty company data"""
        result = await analyzer.analyze({})
        
        assert result.industry == "general"
    
    @pytest.mark.asyncio
    async def test_unknown_industry_defaults_to_general(self, analyzer):
        """Test unknown industry defaults to general"""
        result = await analyzer.analyze({
            "name": "Mystery Company",
            "description": "We do things",
        })
        
        # Should return some industry (possibly general)
        assert result.industry is not None
    
    @pytest.mark.asyncio
    async def test_bootstrap_max_faq_limit(self, cold_start_service):
        """Test that FAQ count respects max limit"""
        # Create more custom FAQs than max limit
        many_faqs = [{"question": f"Q{i}?", "category": "test"} for i in range(100)]
        
        result = await cold_start_service.bootstrap_client(
            client_id="test_max_faqs",
            company_data={"name": "Test"},
            custom_faqs=many_faqs,
        )
        
        # Should be capped at MAX_FAQ_COUNT
        assert result["faqs_created"] <= ColdStartConfig.MAX_FAQ_COUNT
    
    @pytest.mark.asyncio
    async def test_compliance_requirements_retrieval(self, cold_start_service):
        """Test getting compliance requirements"""
        requirements = cold_start_service.get_compliance_requirements(Industry.HEALTHCARE)
        
        assert "hipaa" in requirements
        
        requirements = cold_start_service.get_compliance_requirements(Industry.FINANCIAL)
        assert "pci_dss" in requirements or "sox" in requirements


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
