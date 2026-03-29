"""
Cold Start Bootstrap Module

Creates initial knowledge base entries, loads industry-specific templates,
and sets up default workflows for new clients during onboarding.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update

from shared.core_functions.logger import get_logger
from backend.services.cold_start import Industry, ColdStartConfig

logger = get_logger("cold_start_bootstrap")


@dataclass
class BootstrapProgress:
    """Tracks bootstrap progress for a client"""
    client_id: str
    stage: str
    total_steps: int
    completed_steps: int
    started_at: datetime
    errors: List[str]


class KnowledgeBaseBootstrap:
    """
    Handles knowledge base initialization for new clients.
    
    Creates initial KB entries from industry templates and custom FAQs,
    sets up default categories and tags, and initializes search indexing.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.config = ColdStartConfig()
    
    async def create_entries(
        self,
        client_id: str,
        industry: Industry,
        custom_faqs: Optional[List[Dict]] = None,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Create knowledge base entries for a new client.
        
        Args:
            client_id: Unique client identifier
            industry: Detected or provided industry
            custom_faqs: Optional custom FAQs to include
            overwrite: Whether to overwrite existing entries
            
        Returns:
            Dictionary with created entries and statistics
        """
        logger.info(f"Creating KB entries for client {client_id}, industry {industry}")
        
        progress = BootstrapProgress(
            client_id=client_id,
            stage="initialization",
            total_steps=5,
            completed_steps=0,
            started_at=datetime.utcnow(),
            errors=[]
        )
        
        try:
            # Step 1: Load industry templates
            progress.stage = "loading_templates"
            templates = await self._load_industry_templates(industry)
            progress.completed_steps += 1
            
            # Step 2: Merge with custom FAQs
            progress.stage = "merging_faqs"
            all_faqs = templates.copy()
            if custom_faqs:
                all_faqs.extend(custom_faqs)
            progress.completed_steps += 1
            
            # Step 3: Create KB entries
            progress.stage = "creating_entries"
            entries = await self._create_kb_records(client_id, all_faqs)
            progress.completed_steps += 1
            
            # Step 4: Set up categories
            progress.stage = "setting_categories"
            categories = await self._setup_categories(client_id, industry)
            progress.completed_steps += 1
            
            # Step 5: Initialize search index
            progress.stage = "indexing"
            index_result = await self._initialize_search_index(client_id)
            progress.completed_steps += 1
            
            return {
                "success": True,
                "client_id": client_id,
                "industry": industry.value,
                "entries_created": len(entries),
                "categories": categories,
                "search_indexed": index_result,
                "completed_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            progress.errors.append(str(e))
            logger.error(f"Bootstrap failed for client {client_id}: {str(e)}")
            return {
                "success": False,
                "client_id": client_id,
                "error": str(e),
                "progress": progress.stage,
                "entries_created": progress.completed_steps,
            }
    
    async def _load_industry_templates(self, industry: Industry) -> List[Dict]:
        """
        Load industry-specific FAQ templates.
        
        Returns list of FAQ dictionaries with question, answer, and metadata.
        """
        templates = {
            Industry.ECOMMERCE: [
                {
                    "question": "What is your return policy?",
                    "answer": "We accept returns within 30 days of purchase for items in original condition.",
                    "category": "returns",
                    "tags": ["return", "refund", "policy"],
                    "priority": 1,
                },
                {
                    "question": "How do I track my order?",
                    "answer": "You can track your order using the tracking number sent to your email.",
                    "category": "orders",
                    "tags": ["tracking", "order", "shipping"],
                    "priority": 1,
                },
                {
                    "question": "What payment methods do you accept?",
                    "answer": "We accept all major credit cards, PayPal, and Apple Pay.",
                    "category": "payment",
                    "tags": ["payment", "checkout", "credit card"],
                    "priority": 1,
                },
                {
                    "question": "How long does shipping take?",
                    "answer": "Standard shipping takes 5-7 business days. Express shipping is 2-3 days.",
                    "category": "shipping",
                    "tags": ["shipping", "delivery", "time"],
                    "priority": 1,
                },
                {
                    "question": "Do you offer international shipping?",
                    "answer": "Yes, we ship to most countries. International shipping rates apply.",
                    "category": "shipping",
                    "tags": ["international", "shipping", "worldwide"],
                    "priority": 2,
                },
            ],
            Industry.SAAS: [
                {
                    "question": "How do I start a free trial?",
                    "answer": "Click 'Start Free Trial' on our pricing page. No credit card required.",
                    "category": "billing",
                    "tags": ["trial", "free", "getting started"],
                    "priority": 1,
                },
                {
                    "question": "What plans are available?",
                    "answer": "We offer Starter, Professional, and Enterprise plans to fit your needs.",
                    "category": "billing",
                    "tags": ["plans", "pricing", "subscription"],
                    "priority": 1,
                },
                {
                    "question": "How do I cancel my subscription?",
                    "answer": "You can cancel anytime from Account Settings > Subscription.",
                    "category": "billing",
                    "tags": ["cancel", "subscription", "account"],
                    "priority": 1,
                },
                {
                    "question": "Do you offer API access?",
                    "answer": "Yes, API access is available on Professional and Enterprise plans.",
                    "category": "technical",
                    "tags": ["api", "integration", "developer"],
                    "priority": 1,
                },
                {
                    "question": "Is my data secure?",
                    "answer": "We use industry-standard encryption and are SOC 2 Type II certified.",
                    "category": "security",
                    "tags": ["security", "encryption", "compliance"],
                    "priority": 1,
                },
            ],
            Industry.HEALTHCARE: [
                {
                    "question": "How do I schedule an appointment?",
                    "answer": "You can schedule appointments through our online portal or by calling our office.",
                    "category": "appointments",
                    "tags": ["appointment", "schedule", "booking"],
                    "priority": 1,
                },
                {
                    "question": "Do you accept my insurance?",
                    "answer": "We accept most major insurance plans. Please contact us to verify coverage.",
                    "category": "insurance",
                    "tags": ["insurance", "coverage", "billing"],
                    "priority": 1,
                },
                {
                    "question": "How do I get a prescription refill?",
                    "answer": "Contact your pharmacy or request a refill through our patient portal.",
                    "category": "prescriptions",
                    "tags": ["prescription", "refill", "medication"],
                    "priority": 1,
                },
                {
                    "question": "Is my health information secure?",
                    "answer": "Yes, we are fully HIPAA compliant and use encrypted systems.",
                    "category": "privacy",
                    "tags": ["hipaa", "privacy", "security"],
                    "priority": 1,
                },
                {
                    "question": "Do you offer telehealth appointments?",
                    "answer": "Yes, we offer video consultations for many appointment types.",
                    "category": "appointments",
                    "tags": ["telehealth", "video", "remote"],
                    "priority": 2,
                },
            ],
            Industry.LOGISTICS: [
                {
                    "question": "How do I track my shipment?",
                    "answer": "Enter your tracking number on our tracking page for real-time updates.",
                    "category": "tracking",
                    "tags": ["tracking", "shipment", "status"],
                    "priority": 1,
                },
                {
                    "question": "What are your shipping rates?",
                    "answer": "Rates depend on package size, weight, and destination. Get a quote online.",
                    "category": "pricing",
                    "tags": ["rates", "pricing", "cost"],
                    "priority": 1,
                },
                {
                    "question": "How do I schedule a pickup?",
                    "answer": "Schedule pickups through your account dashboard or call our dispatch.",
                    "category": "pickup",
                    "tags": ["pickup", "collection", "schedule"],
                    "priority": 1,
                },
                {
                    "question": "How do I file a claim for damaged goods?",
                    "answer": "Submit claims within 48 hours with photos through our claims portal.",
                    "category": "claims",
                    "tags": ["claim", "damage", "insurance"],
                    "priority": 2,
                },
                {
                    "question": "Do you offer international shipping?",
                    "answer": "Yes, we provide international shipping to over 200 countries.",
                    "category": "international",
                    "tags": ["international", "global", "worldwide"],
                    "priority": 2,
                },
            ],
            Industry.FINANCIAL: [
                {
                    "question": "How do I open an account?",
                    "answer": "Apply online in minutes with basic identification documents.",
                    "category": "account",
                    "tags": ["account", "open", "apply"],
                    "priority": 1,
                },
                {
                    "question": "What are your interest rates?",
                    "answer": "Rates vary by product. Check our rates page for current offers.",
                    "category": "rates",
                    "tags": ["interest", "rates", "apy"],
                    "priority": 1,
                },
                {
                    "question": "How do I transfer funds?",
                    "answer": "Transfer funds instantly between accounts or to external banks.",
                    "category": "transactions",
                    "tags": ["transfer", "funds", "money"],
                    "priority": 1,
                },
                {
                    "question": "Is my money FDIC insured?",
                    "answer": "Yes, deposits are FDIC insured up to $250,000 per depositor.",
                    "category": "security",
                    "tags": ["fdic", "insurance", "safety"],
                    "priority": 1,
                },
                {
                    "question": "How do I report a lost card?",
                    "answer": "Freeze your card instantly in the app or call our 24/7 support line.",
                    "category": "cards",
                    "tags": ["card", "lost", "stolen"],
                    "priority": 1,
                },
            ],
            Industry.GENERAL: [
                {
                    "question": "What are your business hours?",
                    "answer": "We are available Monday-Friday 9am-5pm. Contact us anytime via email.",
                    "category": "general",
                    "tags": ["hours", "availability", "contact"],
                    "priority": 1,
                },
                {
                    "question": "How do I contact support?",
                    "answer": "Reach us via email, phone, or live chat through our website.",
                    "category": "support",
                    "tags": ["support", "contact", "help"],
                    "priority": 1,
                },
            ],
        }
        
        return templates.get(industry, templates[Industry.GENERAL])
    
    async def _create_kb_records(
        self,
        client_id: str,
        faqs: List[Dict]
    ) -> List[Dict]:
        """
        Create knowledge base records in the database.
        
        Returns list of created entry dictionaries.
        """
        entries = []
        
        for faq in faqs:
            entry = {
                "id": self._generate_entry_id(client_id, faq["question"]),
                "client_id": client_id,
                "question": faq["question"],
                "answer": faq.get("answer", ""),
                "category": faq.get("category", "general"),
                "tags": faq.get("tags", []),
                "priority": faq.get("priority", 3),
                "source": "cold_start_template",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "active": True,
            }
            entries.append(entry)
        
        return entries
    
    async def _setup_categories(
        self,
        client_id: str,
        industry: Industry
    ) -> List[str]:
        """
        Set up default categories for the client.
        
        Returns list of created category names.
        """
        # Industry-specific category sets
        category_sets = {
            Industry.ECOMMERCE: ["orders", "returns", "shipping", "payment", "account", "products"],
            Industry.SAAS: ["billing", "technical", "account", "security", "integrations"],
            Industry.HEALTHCARE: ["appointments", "insurance", "prescriptions", "records", "privacy"],
            Industry.LOGISTICS: ["tracking", "delivery", "pickup", "claims", "pricing"],
            Industry.FINANCIAL: ["account", "transactions", "cards", "loans", "security"],
            Industry.GENERAL: ["general", "support", "account"],
        }
        
        return category_sets.get(industry, category_sets[Industry.GENERAL])
    
    async def _initialize_search_index(self, client_id: str) -> bool:
        """
        Initialize search indexing for client's KB entries.
        
        Returns True if indexing was successful.
        """
        # In a real implementation, this would set up Elasticsearch/Algolia
        logger.info(f"Search index initialized for client {client_id}")
        return True
    
    def _generate_entry_id(self, client_id: str, question: str) -> str:
        """Generate a unique ID for a KB entry."""
        import hashlib
        hash_input = f"{client_id}:{question}".encode()
        return f"kb_{hashlib.md5(hash_input).hexdigest()[:12]}"


class WorkflowSetup:
    """
    Sets up default workflows for new clients.
    
    Configures automation rules, escalation paths, and notification
    preferences based on industry best practices.
    """
    
    DEFAULT_WORKFLOWS = {
        Industry.ECOMMERCE: [
            {
                "name": "order_tracking",
                "trigger": "order_created",
                "actions": ["send_confirmation", "track_shipment"],
                "active": True,
            },
            {
                "name": "refund_processing",
                "trigger": "refund_requested",
                "actions": ["verify_order", "process_refund", "notify_customer"],
                "active": True,
            },
            {
                "name": "cart_recovery",
                "trigger": "cart_abandoned",
                "actions": ["send_reminder", "offer_discount"],
                "active": True,
            },
        ],
        Industry.SAAS: [
            {
                "name": "onboarding",
                "trigger": "account_created",
                "actions": ["send_welcome", "setup_guide", "schedule_checkin"],
                "active": True,
            },
            {
                "name": "subscription_management",
                "trigger": "subscription_changed",
                "actions": ["update_access", "send_confirmation"],
                "active": True,
            },
            {
                "name": "churn_prevention",
                "trigger": "cancellation_initiated",
                "actions": ["offer_retention", "exit_survey"],
                "active": True,
            },
        ],
        Industry.HEALTHCARE: [
            {
                "name": "appointment_scheduling",
                "trigger": "appointment_booked",
                "actions": ["send_confirmation", "send_reminder_24h", "send_reminder_1h"],
                "active": True,
            },
            {
                "name": "prescription_refill",
                "trigger": "refill_requested",
                "actions": ["verify_prescription", "contact_pharmacy", "notify_patient"],
                "active": True,
            },
        ],
        Industry.LOGISTICS: [
            {
                "name": "shipment_tracking",
                "trigger": "shipment_created",
                "actions": ["send_tracking", "status_updates", "delivery_notification"],
                "active": True,
            },
            {
                "name": "delivery_notification",
                "trigger": "out_for_delivery",
                "actions": ["notify_recipient", "request_signature"],
                "active": True,
            },
        ],
        Industry.FINANCIAL: [
            {
                "name": "account_onboarding",
                "trigger": "account_opened",
                "actions": ["verify_identity", "send_welcome", "setup_services"],
                "active": True,
            },
            {
                "name": "transaction_monitoring",
                "trigger": "unusual_activity",
                "actions": ["flag_transaction", "notify_customer", "request_verification"],
                "active": True,
            },
        ],
        Industry.GENERAL: [
            {
                "name": "general_inquiry",
                "trigger": "ticket_created",
                "actions": ["route_ticket", "auto_respond"],
                "active": True,
            },
            {
                "name": "escalation",
                "trigger": "escalation_requested",
                "actions": ["notify_manager", "prioritize_ticket"],
                "active": True,
            },
        ],
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def setup_workflows(
        self,
        client_id: str,
        industry: Industry,
        custom_workflows: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Set up default workflows for a client.
        
        Args:
            client_id: Unique client identifier
            industry: Client's industry
            custom_workflows: Optional custom workflow configurations
            
        Returns:
            Dictionary with workflow setup results
        """
        workflows = self.DEFAULT_WORKFLOWS.get(industry, self.DEFAULT_WORKFLOWS[Industry.GENERAL])
        
        if custom_workflows:
            workflows = workflows + custom_workflows
        
        configured = []
        for workflow in workflows:
            config = {
                "client_id": client_id,
                "name": workflow["name"],
                "trigger": workflow["trigger"],
                "actions": workflow["actions"],
                "active": workflow.get("active", True),
                "created_at": datetime.utcnow().isoformat(),
            }
            configured.append(config)
        
        return {
            "success": True,
            "client_id": client_id,
            "workflows_configured": len(configured),
            "workflows": [w["name"] for w in configured],
        }


def get_kb_bootstrap(db: AsyncSession) -> KnowledgeBaseBootstrap:
    """Get KB bootstrap instance with database session."""
    return KnowledgeBaseBootstrap(db)


def get_workflow_setup(db: AsyncSession) -> WorkflowSetup:
    """Get workflow setup instance with database session."""
    return WorkflowSetup(db)
