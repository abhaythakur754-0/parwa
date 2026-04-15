"""
Cold Start Service — F-107 New Agent Cold Start + Industry Templates

Handles the initialization of new AI agents with no prior training data.
Provides industry-specific templates to bootstrap agent knowledge and behavior.

Features:
- Cold start detection for new agents
- Industry template injection
- Baseline knowledge seeding
- Initial training with template data
- Progressive learning bootstrap

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped by company_id)
- BC-004: Background Jobs (Celery tasks for cold start training)
- BC-007: AI Model Interaction (Training pipeline integration)
- BC-012: Error handling (structured errors, retry logic)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.cold_start")

# ── Constants ───────────────────────────────────────────────────────────────

# Industries with pre-built templates
INDUSTRY_ECOMMERCE = "ecommerce"
INDUSTRY_SAAS = "saas"
INDUSTRY_HEALTHCARE = "healthcare"
INDUSTRY_FINANCE = "finance"
INDUSTRY_EDUCATION = "education"
INDUSTRY_TRAVEL = "travel"
INDUSTRY_REAL_ESTATE = "real_estate"
INDUSTRY_RETAIL = "retail"
INDUSTRY_TELECOM = "telecom"
INDUSTRY_GENERIC = "generic"

# Agent specialties
SPECIALTY_GENERAL = "general"
SPECIALTY_BILLING = "billing"
SPECIALTY_TECHNICAL = "technical"
SPECIALTY_SALES = "sales"
SPECIALTY_RETENTION = "retention"

# Cold start status
COLD_START_PENDING = "pending"
COLD_START_IN_PROGRESS = "in_progress"
COLD_START_COMPLETED = "completed"
COLD_START_FAILED = "failed"

# Minimum template samples
MIN_TEMPLATE_SAMPLES = 25


# ── Industry Templates ───────────────────────────────────────────────────────────────

INDUSTRY_TEMPLATES = {
    INDUSTRY_ECOMMERCE: {
        "name": "E-Commerce",
        "description": "Online retail and shopping platforms",
        "common_queries": [
            {"query": "Where is my order?", "category": "order_status"},
            {"query": "I want to return my item", "category": "returns"},
            {"query": "Can I change my shipping address?", "category": "shipping"},
            {"query": "What payment methods do you accept?", "category": "payment"},
            {"query": "My order arrived damaged", "category": "complaint"},
            {"query": "Do you have this item in stock?", "category": "inventory"},
            {"query": "I need to cancel my order", "category": "cancellation"},
            {"query": "How do I apply a discount code?", "category": "discounts"},
            {"query": "What's your return policy?", "category": "policy"},
            {"query": "My coupon code isn't working", "category": "technical"},
        ],
        "responses": {
            "order_status": "I'd be happy to help you track your order! Could you please provide your order number? It should be in your confirmation email.",
            "returns": "I understand you'd like to return your item. Our return policy allows returns within 30 days of delivery. I can help initiate a return for you - could you share your order number?",
            "shipping": "I can help with shipping address changes if your order hasn't shipped yet. Let me check the status of your order first.",
            "payment": "We accept all major credit cards (Visa, MasterCard, American Express), PayPal, Apple Pay, Google Pay, and Buy Now Pay Later options like Klarna.",
            "complaint": "I'm so sorry to hear your order arrived damaged. This is not the experience we want for you. Let me help arrange a replacement or refund right away.",
            "cancellation": "I can help with order cancellation. If the order hasn't been processed yet, we can cancel it immediately. Let me check the status for you.",
        },
        "knowledge_topics": [
            "order_tracking", "returns_policy", "shipping_options",
            "payment_methods", "product_information", "account_management"
        ],
        "escalation_triggers": ["fraud_suspected", "legal_inquiry", "high_value_dispute"],
    },
    INDUSTRY_SAAS: {
        "name": "SaaS / Software",
        "description": "Software as a Service platforms",
        "common_queries": [
            {"query": "How do I reset my password?", "category": "account"},
            {"query": "I can't log into my account", "category": "authentication"},
            {"query": "How do I upgrade my plan?", "category": "billing"},
            {"query": "The feature isn't working", "category": "technical"},
            {"query": "Can I get a refund?", "category": "billing"},
            {"query": "How do I cancel my subscription?", "category": "cancellation"},
            {"query": "I need help with integration", "category": "technical"},
            {"query": "What's included in the Pro plan?", "category": "sales"},
            {"query": "My data isn't syncing", "category": "technical"},
            {"query": "How do I add team members?", "category": "account"},
        ],
        "responses": {
            "account": "I can help you with your account. For password reset, you can click 'Forgot Password' on the login page, or I can send you a reset link directly.",
            "authentication": "Let me help you regain access to your account. I'll need to verify your identity first - can you confirm the email associated with your account?",
            "billing": "I'd be happy to help with your billing question. I can see your current subscription details and help with upgrades, downgrades, or invoice questions.",
            "technical": "I understand you're experiencing a technical issue. Let me gather some details so I can assist you effectively or connect you with our technical team.",
            "cancellation": "I can help with subscription management. Before canceling, I'd like to understand if there's anything we can do to improve your experience.",
        },
        "knowledge_topics": [
            "getting_started", "feature_guides", "api_documentation",
            "billing_management", "integrations", "troubleshooting"
        ],
        "escalation_triggers": ["data_breach", "service_outage", "enterprise_inquiry"],
    },
    INDUSTRY_HEALTHCARE: {
        "name": "Healthcare",
        "description": "Healthcare and medical services",
        "common_queries": [
            {"query": "How do I schedule an appointment?", "category": "scheduling"},
            {"query": "What insurance do you accept?", "category": "billing"},
            {"query": "I need to reschedule my appointment", "category": "scheduling"},
            {"query": "How do I access my test results?", "category": "records"},
            {"query": "I need a prescription refill", "category": "pharmacy"},
            {"query": "What are your hours?", "category": "general"},
            {"query": "How do I get my medical records?", "category": "records"},
            {"query": "I have a billing question", "category": "billing"},
        ],
        "responses": {
            "scheduling": "I can help you schedule an appointment. Please note that for urgent medical concerns, you should call our emergency line or visit the nearest emergency room.",
            "billing": "I can assist with billing questions. Our billing team can help with insurance claims, payment plans, and cost estimates for procedures.",
            "records": "I can help you access your medical records. For your privacy and security, I'll need to verify your identity first.",
            "general": "Our clinic hours are Monday-Friday 8am-6pm and Saturday 9am-2pm. We're closed on Sundays and major holidays.",
        },
        "knowledge_topics": [
            "appointment_scheduling", "insurance_coverage", "patient_portal",
            "medical_records", "prescription_services", "emergency_protocols"
        ],
        "escalation_triggers": ["medical_emergency", "privacy_concern", "complaint"],
        "disclaimer": "This assistant cannot provide medical advice. For medical emergencies, please call emergency services immediately.",
    },
    INDUSTRY_FINANCE: {
        "name": "Finance / Banking",
        "description": "Financial services and banking",
        "common_queries": [
            {"query": "What's my account balance?", "category": "account"},
            {"query": "I see a suspicious transaction", "category": "security"},
            {"query": "How do I transfer money?", "category": "transactions"},
            {"query": "I lost my card", "category": "cards"},
            {"query": "What are your fees?", "category": "billing"},
            {"query": "How do I apply for a loan?", "category": "products"},
            {"query": "I need to dispute a charge", "category": "disputes"},
            {"query": "How do I set up direct deposit?", "category": "account"},
        ],
        "responses": {
            "account": "For your security, I cannot display account balances directly. Please log into your secure online banking portal or I can connect you with a representative.",
            "security": "I understand you've noticed suspicious activity. For your protection, please call our fraud hotline immediately at the number on the back of your card.",
            "cards": "I can help with your card. If it's lost or stolen, I recommend immediately freezing it through your mobile app. I can also help order a replacement.",
            "transactions": "I can help with money transfers. You can transfer between your accounts, to other users, or to external accounts through our online banking.",
        },
        "knowledge_topics": [
            "account_services", "card_management", "transfers_payments",
            "security_fraud", "loans_credit", "investment_services"
        ],
        "escalation_triggers": ["fraud_report", "large_transaction_dispute", "regulatory_complaint"],
        "compliance_note": "All responses must comply with financial regulations. Never provide specific financial advice.",
    },
    INDUSTRY_EDUCATION: {
        "name": "Education",
        "description": "Educational institutions and e-learning",
        "common_queries": [
            {"query": "How do I enroll in a course?", "category": "enrollment"},
            {"query": "I need help with my assignment", "category": "academic"},
            {"query": "What's the course schedule?", "category": "scheduling"},
            {"query": "How do I access the learning portal?", "category": "technical"},
            {"query": "I need to withdraw from a course", "category": "enrollment"},
            {"query": "How do I contact my instructor?", "category": "academic"},
            {"query": "What resources are available?", "category": "resources"},
            {"query": "I have a technical issue", "category": "technical"},
        ],
        "responses": {
            "enrollment": "I can help you with course enrollment. Our next semester starts soon. Would you like to see available courses or check your enrollment status?",
            "academic": "I can help guide you to the right resources for your assignment. While I can't complete assignments, I can point you to relevant materials and tutoring services.",
            "technical": "I can help troubleshoot technical issues with the learning platform. Let me know what specific problem you're experiencing.",
            "resources": "We offer various student resources including tutoring, library access, career services, and mental health support. What type of assistance are you looking for?",
        },
        "knowledge_topics": [
            "course_catalog", "enrollment_process", "academic_calendar",
            "student_resources", "technical_support", "graduation_requirements"
        ],
        "escalation_triggers": ["academic_integrity", "accessibility_needs", "harassment_report"],
    },
    INDUSTRY_TRAVEL: {
        "name": "Travel / Hospitality",
        "description": "Travel agencies and hospitality services",
        "common_queries": [
            {"query": "How do I book a flight?", "category": "booking"},
            {"query": "I need to change my reservation", "category": "modifications"},
            {"query": "What's the cancellation policy?", "category": "policy"},
            {"query": "My flight was cancelled", "category": "disruption"},
            {"query": "How do I get a refund?", "category": "billing"},
            {"query": "What are the baggage allowances?", "category": "information"},
            {"query": "I need special assistance", "category": "special_needs"},
            {"query": "How do I earn loyalty points?", "category": "loyalty"},
        ],
        "responses": {
            "booking": "I can help you book your travel. Please share your destination, preferred dates, and any special requirements you have.",
            "modifications": "I can help modify your reservation. Changes may be subject to fare differences and airline policies. Let me pull up your booking details.",
            "disruption": "I'm sorry about the flight cancellation. Let me check alternative options for you right away and help you get rebooked.",
            "loyalty": "I can help with our loyalty program. You earn points on every booking, and status members enjoy benefits like priority boarding and lounge access.",
        },
        "knowledge_topics": [
            "booking_process", "cancellation_policy", "loyalty_program",
            "travel_requirements", "special_assistance", "destination_info"
        ],
        "escalation_triggers": ["safety_concern", "group_booking", "vip_customer"],
    },
    INDUSTRY_RETAIL: {
        "name": "Retail",
        "description": "Physical retail stores",
        "common_queries": [
            {"query": "Do you have this in store?", "category": "inventory"},
            {"query": "What are your store hours?", "category": "general"},
            {"query": "Can I return online purchase in store?", "category": "returns"},
            {"query": "Do you offer price matching?", "category": "policy"},
            {"query": "I'm looking for a specific product", "category": "inventory"},
            {"query": "Do you have layaway?", "category": "payment"},
            {"query": "How do I use my rewards?", "category": "loyalty"},
            {"query": "Is this item on sale?", "category": "promotions"},
        ],
        "responses": {
            "inventory": "I can check store availability for you. Which location are you interested in? I can also help you place an order for pickup or delivery.",
            "returns": "Yes, online purchases can be returned in store with your receipt or order confirmation. Returns are accepted within 30 days with original packaging.",
            "policy": "Yes, we offer price matching on identical items from authorized retailers. Bring in the advertisement and we'll match the price.",
            "loyalty": "I can help with your rewards! Points can be redeemed at checkout. Let me check your current balance and available rewards.",
        },
        "knowledge_topics": [
            "store_locator", "return_policy", "rewards_program",
            "price_matching", "product_catalog", "store_services"
        ],
        "escalation_triggers": ["theft_report", "customer_complaint", "safety_issue"],
    },
    INDUSTRY_TELECOM: {
        "name": "Telecommunications",
        "description": "Telecom and internet service providers",
        "common_queries": [
            {"query": "Why is my internet slow?", "category": "technical"},
            {"query": "I want to upgrade my plan", "category": "billing"},
            {"query": "How do I set up my router?", "category": "technical"},
            {"query": "There's an outage in my area", "category": "outage"},
            {"query": "I want to cancel my service", "category": "cancellation"},
            {"query": "Can I get a better deal?", "category": "retention"},
            {"query": "How do I pay my bill?", "category": "billing"},
            {"query": "My phone isn't working", "category": "technical"},
        ],
        "responses": {
            "technical": "I can help troubleshoot your service. Let me run a quick diagnostic on your connection and suggest some solutions.",
            "outage": "Let me check for any reported outages in your area. If there's a confirmed outage, our technicians are already working on it.",
            "retention": "I'd be happy to review your account for available promotions. We have several options that might better fit your needs.",
            "billing": "I can help with your billing. You can pay online, set up auto-pay, or I can review your bill for any questions about charges.",
        },
        "knowledge_topics": [
            "service_troubleshooting", "plan_options", "equipment_setup",
            "billing_support", "coverage_maps", "service_status"
        ],
        "escalation_triggers": ["service_complaint", "billing_dispute", "infrastructure_issue"],
    },
    INDUSTRY_GENERIC: {
        "name": "General Purpose",
        "description": "Generic template for any business",
        "common_queries": [
            {"query": "I have a question about my account", "category": "account"},
            {"query": "How can I contact customer support?", "category": "contact"},
            {"query": "What services do you offer?", "category": "general"},
            {"query": "I have a complaint", "category": "feedback"},
            {"query": "How do I update my information?", "category": "account"},
            {"query": "I need technical support", "category": "technical"},
            {"query": "What are your business hours?", "category": "general"},
            {"query": "I'd like to provide feedback", "category": "feedback"},
        ],
        "responses": {
            "account": "I can help you with your account. Please let me know what specific account-related question you have.",
            "contact": "You can reach our customer support team through various channels including phone, email, and live chat. How would you prefer to contact us?",
            "general": "I'd be happy to provide information about our services. What specific area are you interested in learning more about?",
            "feedback": "Thank you for wanting to share your feedback with us. We value all customer input. Please tell me more about your experience.",
        },
        "knowledge_topics": [
            "general_info", "contact_methods", "account_management",
            "services_overview", "faq", "feedback_process"
        ],
        "escalation_triggers": ["urgent_request", "formal_complaint", "legal_inquiry"],
    },
}


class ColdStartService:
    """Service for managing new agent cold start (F-107).

    This service handles:
    - Detecting agents that need cold start initialization
    - Injecting industry-specific templates
    - Creating initial training datasets
    - Running bootstrap training
    - Tracking cold start progress

    Usage:
        service = ColdStartService(db)
        status = service.get_cold_start_status(company_id, agent_id)
        result = service.initialize_cold_start(company_id, agent_id, industry="ecommerce")
    """

    def __init__(self, db: Session):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # Cold Start Detection
    # ══════════════════════════════════════════════════════════════════════════

    def get_cold_start_status(self, company_id: str, agent_id: str) -> Dict:
        """Check if an agent needs cold start initialization.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent to check.

        Returns:
            Dict with cold start status.
        """
        from database.models.agent import Agent
        from database.models.training import TrainingRun, AgentMistake

        agent = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.id == agent_id,
            )
            .first()
        )

        if not agent:
            return {
                "status": "error",
                "error": f"Agent {agent_id} not found",
            }

        # Check for completed training runs
        completed_runs = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.agent_id == agent_id,
                TrainingRun.status == "completed",
            )
            .count()
        )

        # Check for recorded mistakes (learning data)
        mistake_count = (
            self.db.query(AgentMistake)
            .filter(
                AgentMistake.company_id == company_id,
                AgentMistake.agent_id == agent_id,
            )
            .count()
        )

        # Check for active training
        active_run = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.agent_id == agent_id,
                TrainingRun.status.in_(["queued", "initializing", "running"]),
            )
            .first()
        )

        # Determine if cold start is needed
        needs_cold_start = completed_runs == 0 and active_run is None

        # Get assigned industry
        industry = getattr(agent, "industry", None) or getattr(agent, "specialty", None) or INDUSTRY_GENERIC

        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "needs_cold_start": needs_cold_start,
            "has_training_history": completed_runs > 0,
            "completed_training_runs": completed_runs,
            "mistake_count": mistake_count,
            "has_active_training": active_run is not None,
            "active_run_id": str(active_run.id) if active_run else None,
            "suggested_industry": industry,
            "available_industries": list(INDUSTRY_TEMPLATES.keys()),
        }

    def get_agents_needing_cold_start(self, company_id: str) -> List[Dict]:
        """Get all agents that need cold start initialization.

        Args:
            company_id: Tenant company ID.

        Returns:
            List of agents needing cold start.
        """
        from database.models.agent import Agent
        from database.models.training import TrainingRun

        # Get all active agents
        agents = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.status == "active",
            )
            .all()
        )

        agents_needing_cold_start = []

        for agent in agents:
            status = self.get_cold_start_status(company_id, str(agent.id))
            if status.get("needs_cold_start"):
                agents_needing_cold_start.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.name,
                    "status": agent.status,
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                    "suggested_industry": status.get("suggested_industry"),
                })

        return agents_needing_cold_start

    # ══════════════════════════════════════════════════════════════════════════
    # Industry Template Management
    # ══════════════════════════════════════════════════════════════════════════

    def get_industry_template(self, industry: str) -> Dict:
        """Get the template for a specific industry.

        Args:
            industry: Industry identifier.

        Returns:
            Dict with industry template data.
        """
        template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES[INDUSTRY_GENERIC])
        return {
            "industry": industry,
            "template": template,
        }

    def list_industry_templates(self) -> List[Dict]:
        """List all available industry templates.

        Returns:
            List of available templates with metadata.
        """
        templates = []
        for industry_key, template in INDUSTRY_TEMPLATES.items():
            templates.append({
                "industry_key": industry_key,
                "name": template.get("name"),
                "description": template.get("description"),
                "query_categories": list(set(q["category"] for q in template.get("common_queries", []))),
                "knowledge_topics": template.get("knowledge_topics", []),
                "sample_count": len(template.get("common_queries", [])),
            })
        return templates

    def get_template_training_data(
        self,
        industry: str,
        specialty: Optional[str] = None,
    ) -> List[Dict]:
        """Generate training data from an industry template.

        Args:
            industry: Industry identifier.
            specialty: Optional agent specialty filter.

        Returns:
            List of training samples.
        """
        template = INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES[INDUSTRY_GENERIC])

        training_samples = []

        for query_data in template.get("common_queries", []):
            query = query_data["query"]
            category = query_data["category"]

            # Get response for this category
            responses = template.get("responses", {})
            response = responses.get(category, f"I'll help you with your {category} concern. Let me look into this for you.")

            training_samples.append({
                "input": query,
                "expected_output": response,
                "category": category,
                "industry": industry,
                "source": "template",
            })

            # Add variations
            variations = self._generate_query_variations(query, category)
            for var in variations:
                training_samples.append({
                    "input": var,
                    "expected_output": response,
                    "category": category,
                    "industry": industry,
                    "source": "template_variation",
                })

        # Add knowledge topic samples
        for topic in template.get("knowledge_topics", []):
            topic_samples = self._generate_knowledge_samples(topic, industry)
            training_samples.extend(topic_samples)

        # Filter by specialty if provided
        if specialty and specialty != SPECIALTY_GENERAL:
            priority_categories = self._get_specialty_categories(specialty)
            training_samples.sort(
                key=lambda x: (0 if x.get("category") in priority_categories else 1, x.get("category"))
            )

        return training_samples

    def _generate_query_variations(self, query: str, category: str) -> List[str]:
        """Generate variations of a query for training diversity."""
        variations = []

        # Simple variations
        if "?" in query:
            variations.append(query.replace("?", ""))
            variations.append(f"Hi, {query.lower()}")

        # Add common prefixes
        prefixes = ["Can you tell me ", "I want to know ", "Help me with "]
        for prefix in prefixes:
            if not query.lower().startswith(prefix.lower()):
                variations.append(f"{prefix}{query.lower().rstrip('?')}")

        return variations[:3]  # Limit variations

    def _generate_knowledge_samples(self, topic: str, industry: str) -> List[Dict]:
        """Generate training samples for a knowledge topic."""
        # Simple knowledge samples
        return [
            {
                "input": f"Tell me about {topic.replace('_', ' ')}",
                "expected_output": f"I can provide information about {topic.replace('_', ' ')}. Let me look that up for you.",
                "category": "knowledge",
                "industry": industry,
                "source": "knowledge_topic",
            },
            {
                "input": f"I need help understanding {topic.replace('_', ' ')}",
                "expected_output": f"I'd be happy to help you understand {topic.replace('_', ' ')}. What specific aspect would you like to know more about?",
                "category": "knowledge",
                "industry": industry,
                "source": "knowledge_topic",
            },
        ]

    def _get_specialty_categories(self, specialty: str) -> List[str]:
        """Get priority categories for a specialty."""
        specialty_mapping = {
            SPECIALTY_BILLING: ["billing", "payment", "refunds", "invoices"],
            SPECIALTY_TECHNICAL: ["technical", "integration", "troubleshooting", "setup"],
            SPECIALTY_SALES: ["sales", "pricing", "products", "features"],
            SPECIALTY_RETENTION: ["cancellation", "feedback", "complaint", "retention"],
            SPECIALTY_GENERAL: [],
        }
        return specialty_mapping.get(specialty, [])

    # ══════════════════════════════════════════════════════════════════════════
    # Cold Start Initialization
    # ══════════════════════════════════════════════════════════════════════════

    def initialize_cold_start(
        self,
        company_id: str,
        agent_id: str,
        industry: str = INDUSTRY_GENERIC,
        specialty: Optional[str] = None,
        auto_train: bool = True,
    ) -> Dict:
        """Initialize cold start for a new agent.

        Args:
            company_id: Tenant company ID.
            agent_id: Agent to initialize.
            industry: Industry template to use.
            specialty: Optional agent specialty.
            auto_train: Whether to automatically start training.

        Returns:
            Dict with initialization result.
        """
        from database.models.agent import Agent

        # Verify agent exists
        agent = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.id == agent_id,
            )
            .first()
        )

        if not agent:
            return {
                "status": "error",
                "error": f"Agent {agent_id} not found",
            }

        # Check if already initialized
        status = self.get_cold_start_status(company_id, agent_id)
        if not status.get("needs_cold_start"):
            return {
                "status": "skipped",
                "reason": "already_initialized",
                "agent_id": agent_id,
                "completed_runs": status.get("completed_training_runs"),
            }

        try:
            # Generate training data from template
            training_data = self.get_template_training_data(industry, specialty)

            if len(training_data) < MIN_TEMPLATE_SAMPLES:
                # Supplement with generic data
                generic_data = self.get_template_training_data(INDUSTRY_GENERIC, specialty)
                training_data.extend(generic_data[:MIN_TEMPLATE_SAMPLES - len(training_data)])

            # Create dataset
            from app.services.dataset_preparation_service import DatasetPreparationService
            dataset_service = DatasetPreparationService(self.db)

            dataset_result = dataset_service.create_dataset_from_samples(
                company_id=company_id,
                agent_id=agent_id,
                samples=training_data,
                name=f"Cold Start Dataset - {industry}",
                source="cold_start_template",
            )

            if dataset_result.get("status") != "created":
                return {
                    "status": "error",
                    "error": f"Failed to create dataset: {dataset_result.get('error')}",
                    "agent_id": agent_id,
                }

            # Update agent with industry info
            if hasattr(agent, "industry"):
                agent.industry = industry
            self.db.commit()

            result = {
                "status": "initialized",
                "agent_id": agent_id,
                "industry": industry,
                "specialty": specialty,
                "dataset_id": dataset_result.get("dataset_id"),
                "sample_count": len(training_data),
                "template_used": industry,
            }

            # Auto-start training if requested
            if auto_train:
                train_result = self._start_cold_start_training(
                    company_id=company_id,
                    agent_id=agent_id,
                    dataset_id=dataset_result.get("dataset_id"),
                )
                result["training"] = train_result

            logger.info(
                "cold_start_initialized",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "industry": industry,
                    "sample_count": len(training_data),
                    "auto_train": auto_train,
                },
            )

            return result

        except Exception as exc:
            logger.error(
                "cold_start_initialization_failed",
                extra={
                    "company_id": company_id,
                    "agent_id": agent_id,
                    "industry": industry,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "error",
                "error": str(exc)[:500],
                "agent_id": agent_id,
            }

    def _start_cold_start_training(
        self,
        company_id: str,
        agent_id: str,
        dataset_id: str,
    ) -> Dict:
        """Start cold start training for an agent."""
        from app.services.agent_training_service import AgentTrainingService

        training_service = AgentTrainingService(self.db)

        run_result = training_service.create_training_run(
            company_id=company_id,
            agent_id=agent_id,
            dataset_id=dataset_id,
            name=f"Cold Start Training - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            trigger="cold_start",
            epochs=3,
        )

        return run_result

    # ══════════════════════════════════════════════════════════════════════════
    # Bulk Operations
    # ══════════════════════════════════════════════════════════════════════════

    def initialize_all_cold_start_agents(
        self,
        company_id: str,
        default_industry: str = INDUSTRY_GENERIC,
    ) -> Dict:
        """Initialize cold start for all agents that need it.

        Args:
            company_id: Tenant company ID.
            default_industry: Default industry template to use.

        Returns:
            Dict with bulk initialization results.
        """
        agents_needing_init = self.get_agents_needing_cold_start(company_id)

        results = {
            "initialized": [],
            "skipped": [],
            "errors": [],
        }

        for agent in agents_needing_init:
            industry = agent.get("suggested_industry") or default_industry

            result = self.initialize_cold_start(
                company_id=company_id,
                agent_id=agent["agent_id"],
                industry=industry,
                auto_train=True,
            )

            if result.get("status") == "initialized":
                results["initialized"].append(result)
            elif result.get("status") == "skipped":
                results["skipped"].append(result)
            else:
                results["errors"].append(result)

        logger.info(
            "bulk_cold_start_completed",
            extra={
                "company_id": company_id,
                "initialized_count": len(results["initialized"]),
                "skipped_count": len(results["skipped"]),
                "error_count": len(results["errors"]),
            },
        )

        return {
            "status": "completed",
            "company_id": company_id,
            "total_agents": len(agents_needing_init),
            "initialized": len(results["initialized"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "details": results,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Statistics
    # ══════════════════════════════════════════════════════════════════════════

    def get_cold_start_stats(self, company_id: str) -> Dict:
        """Get cold start statistics for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with cold start statistics.
        """
        from database.models.agent import Agent
        from database.models.training import TrainingRun

        # Total active agents
        total_agents = (
            self.db.query(Agent)
            .filter(
                Agent.company_id == company_id,
                Agent.status == "active",
            )
            .count()
        )

        # Agents needing cold start
        agents_needing_init = self.get_agents_needing_cold_start(company_id)

        # Cold start training runs
        cold_start_runs = (
            self.db.query(TrainingRun)
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.trigger == "cold_start",
            )
            .all()
        )

        completed = len([r for r in cold_start_runs if r.status == "completed"])
        failed = len([r for r in cold_start_runs if r.status == "failed"])
        total_cost = sum(float(r.cost_usd or 0) for r in cold_start_runs)

        return {
            "company_id": company_id,
            "total_active_agents": total_agents,
            "agents_needing_cold_start": len(agents_needing_init),
            "cold_start_runs_total": len(cold_start_runs),
            "cold_start_runs_completed": completed,
            "cold_start_runs_failed": failed,
            "total_cost_usd": round(total_cost, 2),
            "available_industries": len(INDUSTRY_TEMPLATES),
        }
