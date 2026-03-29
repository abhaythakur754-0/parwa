"""
Cold Start Service for PARWA

Bootstraps new clients with industry-specific FAQs and initial knowledge base entries.
Supports multiple industries: e-commerce, SaaS, healthcare, logistics, financial services.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger("cold_start_service")
settings = get_settings()


class Industry(str, Enum):
    """Supported industries for cold start"""
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    LOGISTICS = "logistics"
    FINANCIAL = "financial"
    GENERAL = "general"


class BootstrapStatus(str, Enum):
    """Bootstrap status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ColdStartConfig:
    """Configuration for cold start service"""
    
    DEFAULT_FAQ_COUNT = 10
    MAX_FAQ_COUNT = 50
    INDUSTRY_KEYWORDS = {
        Industry.ECOMMERCE: ["shop", "store", "cart", "checkout", "product", "order", "shipping", "refund"],
        Industry.SAAS: ["subscription", "trial", "plan", "billing", "api", "integration", "dashboard"],
        Industry.HEALTHCARE: ["patient", "appointment", "prescription", "insurance", "medical", "hipaa"],
        Industry.LOGISTICS: ["shipping", "delivery", "tracking", "warehouse", "freight", "supply chain"],
        Industry.FINANCIAL: ["banking", "investment", "loan", "credit", "payment", "transaction", "compliance"],
    }
    
    COMPLIANCE_REQUIREMENTS = {
        Industry.ECOMMERCE: ["gdpr", "pci_dss"],
        Industry.SAAS: ["gdpr", "soc2"],
        Industry.HEALTHCARE: ["hipaa", "gdpr"],
        Industry.LOGISTICS: ["gdpr"],
        Industry.FINANCIAL: ["pci_dss", "sox", "gdpr"],
    }


class ColdStartService:
    """
    Service for bootstrapping new clients with industry-specific content.
    
    Handles:
    - Industry detection from client data
    - FAQ template loading
    - Knowledge base initialization
    - Workflow setup
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.config = ColdStartConfig()
    
    async def bootstrap_client(
        self,
        client_id: str,
        company_data: Dict[str, Any],
        industry_hint: Optional[Industry] = None,
        custom_faqs: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Bootstrap a new client with industry-specific content.
        
        Args:
            client_id: Unique client identifier
            company_data: Company information (name, website, description, etc.)
            industry_hint: Optional industry hint to skip detection
            custom_faqs: Optional custom FAQs to include
            
        Returns:
            Bootstrap result with status and created resources
        """
        logger.info(f"Starting bootstrap for client {client_id}")
        
        try:
            # Detect or use provided industry
            industry = industry_hint or await self._detect_industry(company_data)
            logger.info(f"Detected industry: {industry} for client {client_id}")
            
            # Get industry-specific FAQs
            faqs = await self._get_industry_faqs(industry, custom_faqs)
            
            # Create knowledge base entries
            kb_entries = await self._create_kb_entries(client_id, faqs)
            
            # Set up default workflows
            workflows = await self._setup_workflows(client_id, industry)
            
            # Record bootstrap completion
            result = {
                "client_id": client_id,
                "industry": industry.value,
                "status": BootstrapStatus.COMPLETED.value,
                "faqs_created": len(faqs),
                "kb_entries": len(kb_entries),
                "workflows": workflows,
                "bootstrapped_at": datetime.utcnow().isoformat(),
            }
            
            logger.info(f"Bootstrap completed for client {client_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Bootstrap failed for client {client_id}: {str(e)}")
            return {
                "client_id": client_id,
                "status": BootstrapStatus.FAILED.value,
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            }
    
    async def _detect_industry(self, company_data: Dict[str, Any]) -> Industry:
        """
        Detect industry from company data.
        
        Analyzes company name, description, website, and other metadata
        to determine the most likely industry.
        """
        # Combine all text for analysis
        text_parts = []
        for field in ["name", "description", "website", "industry"]:
            if field in company_data and company_data[field]:
                text_parts.append(str(company_data[field]).lower())
        
        combined_text = " ".join(text_parts)
        
        # Score each industry based on keyword matches
        scores: Dict[Industry, int] = {}
        for industry, keywords in self.config.INDUSTRY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            scores[industry] = score
        
        # Get industry with highest score
        if scores:
            best_industry = max(scores, key=scores.get)
            if scores[best_industry] > 0:
                return best_industry
        
        # Default to general if no match
        return Industry.GENERAL
    
    async def _get_industry_faqs(
        self,
        industry: Industry,
        custom_faqs: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Get industry-specific FAQ templates.
        
        Returns a list of FAQ entries tailored to the detected industry.
        """
        # Industry-specific FAQ templates
        industry_faqs = {
            Industry.ECOMMERCE: [
                {"question": "What is your return policy?", "category": "returns", "priority": 1},
                {"question": "How do I track my order?", "category": "orders", "priority": 1},
                {"question": "What payment methods do you accept?", "category": "payment", "priority": 1},
                {"question": "How long does shipping take?", "category": "shipping", "priority": 1},
                {"question": "Do you offer international shipping?", "category": "shipping", "priority": 2},
                {"question": "How do I cancel my order?", "category": "orders", "priority": 2},
                {"question": "What if I received a damaged item?", "category": "returns", "priority": 2},
                {"question": "Do you have a loyalty program?", "category": "account", "priority": 3},
                {"question": "How do I apply a discount code?", "category": "payment", "priority": 3},
                {"question": "Can I change my shipping address?", "category": "orders", "priority": 3},
            ],
            Industry.SAAS: [
                {"question": "How do I start a free trial?", "category": "billing", "priority": 1},
                {"question": "What plans are available?", "category": "billing", "priority": 1},
                {"question": "How do I cancel my subscription?", "category": "billing", "priority": 1},
                {"question": "Do you offer API access?", "category": "technical", "priority": 1},
                {"question": "How do I integrate with other tools?", "category": "technical", "priority": 2},
                {"question": "What happens when I exceed my usage limit?", "category": "billing", "priority": 2},
                {"question": "Is my data secure?", "category": "security", "priority": 1},
                {"question": "How do I add team members?", "category": "account", "priority": 2},
                {"question": "Do you offer training or onboarding?", "category": "support", "priority": 3},
                {"question": "How do I export my data?", "category": "technical", "priority": 3},
            ],
            Industry.HEALTHCARE: [
                {"question": "How do I schedule an appointment?", "category": "appointments", "priority": 1},
                {"question": "Do you accept my insurance?", "category": "insurance", "priority": 1},
                {"question": "How do I get a prescription refill?", "category": "prescriptions", "priority": 1},
                {"question": "What are your office hours?", "category": "general", "priority": 1},
                {"question": "How do I access my medical records?", "category": "records", "priority": 2},
                {"question": "Is my health information secure?", "category": "privacy", "priority": 1},
                {"question": "How do I update my insurance information?", "category": "insurance", "priority": 2},
                {"question": "What is your cancellation policy?", "category": "appointments", "priority": 2},
                {"question": "Do you offer telehealth appointments?", "category": "appointments", "priority": 2},
                {"question": "How do I contact my doctor?", "category": "general", "priority": 3},
            ],
            Industry.LOGISTICS: [
                {"question": "How do I track my shipment?", "category": "tracking", "priority": 1},
                {"question": "What are your delivery zones?", "category": "delivery", "priority": 1},
                {"question": "How do I schedule a pickup?", "category": "pickup", "priority": 1},
                {"question": "What are your shipping rates?", "category": "pricing", "priority": 1},
                {"question": "Do you offer freight services?", "category": "freight", "priority": 2},
                {"question": "How do I file a claim for damaged goods?", "category": "claims", "priority": 2},
                {"question": "What are your warehouse locations?", "category": "warehousing", "priority": 2},
                {"question": "Do you offer same-day delivery?", "category": "delivery", "priority": 2},
                {"question": "How do I get a shipping quote?", "category": "pricing", "priority": 3},
                {"question": "What documentation do I need for international shipping?", "category": "international", "priority": 3},
            ],
            Industry.FINANCIAL: [
                {"question": "How do I open an account?", "category": "account", "priority": 1},
                {"question": "What are your interest rates?", "category": "rates", "priority": 1},
                {"question": "How do I apply for a loan?", "category": "loans", "priority": 1},
                {"question": "Is my money FDIC insured?", "category": "security", "priority": 1},
                {"question": "How do I transfer funds?", "category": "transactions", "priority": 1},
                {"question": "What are your fees?", "category": "pricing", "priority": 2},
                {"question": "How do I set up direct deposit?", "category": "account", "priority": 2},
                {"question": "How do I report a lost card?", "category": "cards", "priority": 1},
                {"question": "Do you offer investment services?", "category": "investments", "priority": 2},
                {"question": "How do I access my statements?", "category": "account", "priority": 3},
            ],
            Industry.GENERAL: [
                {"question": "What are your business hours?", "category": "general", "priority": 1},
                {"question": "How do I contact support?", "category": "support", "priority": 1},
                {"question": "Where are you located?", "category": "general", "priority": 1},
                {"question": "How do I provide feedback?", "category": "feedback", "priority": 2},
                {"question": "Do you have a privacy policy?", "category": "legal", "priority": 1},
            ],
        }
        
        faqs = industry_faqs.get(industry, industry_faqs[Industry.GENERAL])
        
        # Add custom FAQs if provided
        if custom_faqs:
            faqs = faqs + custom_faqs
        
        # Limit to max FAQs
        return faqs[:self.config.MAX_FAQ_COUNT]
    
    async def _create_kb_entries(
        self,
        client_id: str,
        faqs: List[Dict]
    ) -> List[Dict]:
        """
        Create knowledge base entries from FAQs.
        
        Returns list of created KB entry IDs.
        """
        entries = []
        for faq in faqs:
            entry = {
                "client_id": client_id,
                "question": faq["question"],
                "category": faq.get("category", "general"),
                "priority": faq.get("priority", 3),
                "created_at": datetime.utcnow().isoformat(),
                "source": "cold_start",
            }
            entries.append(entry)
        
        return entries
    
    async def _setup_workflows(
        self,
        client_id: str,
        industry: Industry
    ) -> List[str]:
        """
        Set up default workflows for the client based on industry.
        
        Returns list of configured workflow names.
        """
        # Industry-specific workflow configurations
        workflow_configs = {
            Industry.ECOMMERCE: ["order_tracking", "refund_processing", "cart_recovery"],
            Industry.SAAS: ["onboarding", "subscription_management", "churn_prevention"],
            Industry.HEALTHCARE: ["appointment_scheduling", "prescription_refill", "insurance_verification"],
            Industry.LOGISTICS: ["shipment_tracking", "delivery_notification", "claims_processing"],
            Industry.FINANCIAL: ["account_onboarding", "transaction_monitoring", "compliance_check"],
            Industry.GENERAL: ["general_inquiry", "escalation", "feedback_collection"],
        }
        
        return workflow_configs.get(industry, workflow_configs[Industry.GENERAL])
    
    async def get_bootstrap_status(self, client_id: str) -> Dict[str, Any]:
        """
        Get the bootstrap status for a client.
        
        Returns current bootstrap status and progress.
        """
        # In a real implementation, this would query the database
        return {
            "client_id": client_id,
            "status": BootstrapStatus.COMPLETED.value,
            "message": "Bootstrap completed successfully",
        }
    
    def get_compliance_requirements(self, industry: Industry) -> List[str]:
        """
        Get compliance requirements for an industry.
        
        Returns list of required compliance frameworks.
        """
        return self.config.COMPLIANCE_REQUIREMENTS.get(industry, [])


# Convenience function for dependency injection
def get_cold_start_service(db: AsyncSession) -> ColdStartService:
    """Get cold start service instance with database session."""
    return ColdStartService(db)
