"""
PARWA Knowledge Base Cold Start.

Bootstraps a new client's knowledge base with industry-specific FAQs
and common support content to enable immediate value from the AI support system.
"""
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from shared.knowledge_base.kb_manager import KnowledgeBaseManager, KnowledgeBaseConfig

logger = get_logger(__name__)


class IndustryType(str, Enum):
    """Supported industry types for cold start."""
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    RETAIL = "retail"
    GENERAL = "general"


class ColdStartConfig(BaseModel):
    """Configuration for Cold Start process."""
    include_industry_faqs: bool = Field(default=True)
    include_general_faqs: bool = Field(default=True)
    include_escalation_rules: bool = Field(default=True)
    max_faqs_per_category: int = Field(default=50, ge=1, le=200)
    auto_activate: bool = Field(default=True)

    model_config = ConfigDict(use_enum_values=True)


class ColdStartResult(BaseModel):
    """Result of cold start process."""
    company_id: UUID
    industry: str
    documents_ingested: int = Field(default=0)
    categories_created: int = Field(default=0)
    faqs_added: int = Field(default=0)
    status: str = "pending"
    processing_time_ms: float = Field(default=0.0)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)


# Industry-specific FAQ templates
INDUSTRY_FAQS: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    IndustryType.ECOMMERCE.value: {
        "orders": [
            {
                "question": "How do I track my order?",
                "answer": "You can track your order by logging into your account and visiting the 'My Orders' section. Click on the specific order to see real-time tracking information. You'll also receive email updates with tracking links.",
            },
            {
                "question": "Can I change my order after placing it?",
                "answer": "Orders can typically be modified within 1 hour of placement. Go to 'My Orders', select the order, and click 'Modify Order'. If the option isn't available, the order may have already been processed for shipping.",
            },
            {
                "question": "How do I cancel my order?",
                "answer": "To cancel an order, go to 'My Orders', select the order you want to cancel, and click 'Cancel Order'. Cancellations are only possible before the order ships. If already shipped, you'll need to initiate a return.",
            },
        ],
        "shipping": [
            {
                "question": "What are the shipping options?",
                "answer": "We offer Standard Shipping (5-7 business days), Express Shipping (2-3 business days), and Next-Day Delivery. Shipping costs vary by order value and destination. Free shipping is available on orders over the minimum threshold.",
            },
            {
                "question": "Do you ship internationally?",
                "answer": "Yes, we ship to over 100 countries. International shipping typically takes 7-14 business days. Customs fees may apply and are the responsibility of the recipient.",
            },
            {
                "question": "Why was my package returned to sender?",
                "answer": "Packages may be returned due to incorrect address, failed delivery attempts, or recipient unavailability. Contact customer support with your order number to arrange redelivery or address correction.",
            },
        ],
        "returns": [
            {
                "question": "What is your return policy?",
                "answer": "We accept returns within 30 days of delivery for most items in original condition. Some items like personalized products, perishables, and intimate items are non-returnable. Refunds are processed within 5-7 business days.",
            },
            {
                "question": "How do I initiate a return?",
                "answer": "Go to 'My Orders', select the item(s) to return, and click 'Start Return'. Print the prepaid return label, pack the items securely, and drop off at any authorized location.",
            },
            {
                "question": "When will I receive my refund?",
                "answer": "Refunds are processed within 5-7 business days after we receive and inspect the returned items. The refund will be credited to your original payment method. You'll receive an email confirmation once processed.",
            },
        ],
        "payments": [
            {
                "question": "What payment methods do you accept?",
                "answer": "We accept major credit cards (Visa, MasterCard, American Express, Discover), PayPal, Apple Pay, Google Pay, and Shop Pay. We also offer buy-now-pay-later options through Klarna and Afterpay.",
            },
            {
                "question": "Why was my payment declined?",
                "answer": "Payment declines can occur due to insufficient funds, incorrect billing address, security flags, or bank restrictions. Try using a different payment method or contact your bank for more details.",
            },
            {
                "question": "Is my payment information secure?",
                "answer": "Yes, we use industry-standard SSL encryption and are PCI DSS compliant. We never store your complete credit card information on our servers. All transactions are processed through secure payment gateways.",
            },
        ],
    },
    IndustryType.SAAS.value: {
        "account": [
            {
                "question": "How do I create an account?",
                "answer": "Click 'Sign Up' on our homepage, enter your email and create a password. You'll receive a verification email - click the link to activate your account. You can then start your free trial.",
            },
            {
                "question": "How do I reset my password?",
                "answer": "Click 'Forgot Password' on the login page, enter your email address, and we'll send a password reset link. The link expires in 24 hours for security purposes.",
            },
            {
                "question": "How do I delete my account?",
                "answer": "Go to Settings > Account > Delete Account. You'll need to confirm your password and acknowledge that this action is irreversible. Your data will be permanently deleted within 30 days per our retention policy.",
            },
        ],
        "billing": [
            {
                "question": "What payment methods do you accept?",
                "answer": "We accept all major credit cards (Visa, MasterCard, American Express) for monthly subscriptions. Annual plans can also be paid via bank transfer or check. Contact sales for enterprise invoicing options.",
            },
            {
                "question": "How do I upgrade or downgrade my plan?",
                "answer": "Navigate to Settings > Billing > Subscription. Select your new plan and confirm the change. Upgrades take effect immediately with prorated charges. Downgrades take effect at the next billing cycle.",
            },
            {
                "question": "Do you offer refunds?",
                "answer": "We offer a full refund within 14 days of purchase for annual plans. Monthly subscriptions can be cancelled anytime but are non-refundable for the current billing period. Contact support for exceptional circumstances.",
            },
        ],
        "features": [
            {
                "question": "What features are included in each plan?",
                "answer": "Our Starter plan includes basic features for small teams. Professional adds advanced analytics and integrations. Enterprise includes custom branding, dedicated support, and SLA guarantees. See our pricing page for detailed comparisons.",
            },
            {
                "question": "How do I enable integrations?",
                "answer": "Go to Settings > Integrations, find the app you want to connect, and click 'Connect'. You'll be redirected to authorize the connection. Most integrations sync automatically once connected.",
            },
            {
                "question": "Is there an API available?",
                "answer": "Yes, our REST API is available on Professional and Enterprise plans. Access your API keys in Settings > API. Documentation is available at docs.example.com with examples in multiple programming languages.",
            },
        ],
    },
    IndustryType.HEALTHCARE.value: {
        "appointments": [
            {
                "question": "How do I schedule an appointment?",
                "answer": "Log into your patient portal, go to 'Appointments', and click 'Schedule New'. Select your provider, choose an available time slot, and confirm. You'll receive email and SMS confirmations.",
            },
            {
                "question": "How do I cancel or reschedule?",
                "answer": "Go to 'My Appointments', select the appointment, and click 'Cancel' or 'Reschedule'. Please provide at least 24 hours notice to avoid cancellation fees. Rescheduling is free if done 24 hours in advance.",
            },
            {
                "question": "What if I'm running late?",
                "answer": "Call our office as soon as possible. If you're more than 15 minutes late, you may need to reschedule to ensure adequate time for your appointment and to respect other patients' scheduled times.",
            },
        ],
        "records": [
            {
                "question": "How do I access my medical records?",
                "answer": "Log into the patient portal and navigate to 'Health Records'. You can view lab results, visit summaries, and immunization records. For complete medical records, submit a request through the portal.",
            },
            {
                "question": "How do I request my records be sent to another provider?",
                "answer": "Submit a records release request through the patient portal or complete a form at our office. Include the receiving provider's information. Processing typically takes 5-7 business days.",
            },
            {
                "question": "Are my records secure?",
                "answer": "Yes, we comply with HIPAA regulations and use encrypted storage and transmission. Access is logged and monitored. You control who can view your information through the patient portal.",
            },
        ],
        "insurance": [
            {
                "question": "What insurance do you accept?",
                "answer": "We accept most major insurance plans. Check our website for the current list or contact your insurance provider to verify coverage. We also offer self-pay options for uninsured patients.",
            },
            {
                "question": "How do I update my insurance information?",
                "answer": "Log into the patient portal, go to 'Insurance', and click 'Update'. Upload images of your insurance card front and back. Changes take effect for future appointments.",
            },
            {
                "question": "Why was my claim denied?",
                "answer": "Claims may be denied for various reasons including services not covered, pre-authorization requirements, or out-of-network providers. Contact your insurance company for specific details. Our billing team can help appeal if appropriate.",
            },
        ],
    },
    IndustryType.FINANCE.value: {
        "accounts": [
            {
                "question": "How do I open an account?",
                "answer": "Apply online or visit any branch. You'll need valid ID, proof of address, and Social Security number. The process takes about 15 minutes online. Accounts are typically opened same-day.",
            },
            {
                "question": "What account types are available?",
                "answer": "We offer checking, savings, money market, and certificate of deposit accounts. Business accounts include additional features. Investment accounts are available through our brokerage division.",
            },
            {
                "question": "How do I close an account?",
                "answer": "Visit a branch or call customer service. Ensure all transactions have cleared and the balance is zero or transferable. A written request may be required for certain account types.",
            },
        ],
        "security": [
            {
                "question": "How do I report suspicious activity?",
                "answer": "Call our fraud hotline immediately at the number on the back of your card. You can also report through online banking by selecting the transaction and clicking 'Report Issue'. We'll investigate and may issue provisional credit.",
            },
            {
                "question": "How do I set up account alerts?",
                "answer": "Log into online banking, go to 'Alerts & Notifications', and customize your preferences. You can receive alerts via email, SMS, or push notifications for transactions, balance thresholds, and account activity.",
            },
            {
                "question": "Is online banking secure?",
                "answer": "We use multi-factor authentication, encryption, and 24/7 monitoring. Enable biometric login for additional security. Never share your credentials and always log out when using shared devices.",
            },
        ],
        "transactions": [
            {
                "question": "What are the transfer limits?",
                "answer": "Internal transfers have a daily limit of $50,000. External ACH transfers are limited to $25,000 daily. Wire transfers can be arranged up to $100,000 with branch approval. Higher limits available for premium accounts.",
            },
            {
                "question": "How long do transfers take?",
                "answer": "Internal transfers are instant. ACH transfers take 1-3 business days. Wire transfers are typically same-day if initiated before the cutoff time. International wires may take 3-5 business days.",
            },
            {
                "question": "How do I dispute a transaction?",
                "answer": "Log into online banking, find the transaction, and click 'Dispute'. Provide details about why you're disputing. We'll investigate and provide a decision within 10 business days for most cases.",
            },
        ],
    },
    IndustryType.GENERAL.value: {
        "general": [
            {
                "question": "How do I contact customer support?",
                "answer": "You can reach us through live chat on our website, by phone during business hours, or by email. Response times vary by contact method - chat is typically fastest.",
            },
            {
                "question": "What are your business hours?",
                "answer": "Our customer service team is available Monday through Friday, 9 AM to 6 PM in your local time zone. Some services may be available 24/7 through our online portal.",
            },
            {
                "question": "How do I provide feedback?",
                "answer": "We welcome your feedback! Use the feedback form on our website, reply to post-interaction surveys, or email feedback@example.com. All feedback is reviewed by our team.",
            },
        ],
    },
}


class ColdStart:
    """
    Knowledge Base Cold Start for new clients.

    Bootstraps a new client's knowledge base with industry-specific
    FAQs and common support content for immediate AI support capability.

    Features:
    - Industry-specific FAQ templates
    - Automatic category creation
    - Document ingestion pipeline
    - Activation management
    """

    def __init__(
        self,
        kb_manager: Optional[KnowledgeBaseManager] = None,
        config: Optional[ColdStartConfig] = None,
        company_id: Optional[UUID] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None
    ) -> None:
        """
        Initialize Cold Start.

        Args:
            kb_manager: Knowledge Base Manager instance
            config: Cold Start configuration
            company_id: Company UUID for scoping
            embedding_fn: Function to generate embeddings
        """
        self.config = config or ColdStartConfig()
        self.company_id = company_id
        self.embedding_fn = embedding_fn

        # Initialize KB manager if not provided
        if kb_manager:
            self.kb_manager = kb_manager
        else:
            self.kb_manager = KnowledgeBaseManager(
                company_id=company_id,
                embedding_fn=embedding_fn,
                config=KnowledgeBaseConfig()
            )

        # Statistics
        self._cold_starts_completed = 0
        self._total_documents_ingested = 0

        logger.info({
            "event": "cold_start_initialized",
            "company_id": str(company_id) if company_id else None,
            "config": self.config.model_dump(),
        })

    def bootstrap(
        self,
        company_id: UUID,
        industry: IndustryType,
        custom_faqs: Optional[List[Dict[str, str]]] = None,
        company_name: Optional[str] = None
    ) -> ColdStartResult:
        """
        Bootstrap knowledge base for a new company.

        Args:
            company_id: Company UUID
            industry: Industry type for FAQ selection
            custom_faqs: Optional custom FAQs to add
            company_name: Company name for personalization

        Returns:
            ColdStartResult with bootstrap status

        Raises:
            ValueError: If company_id is None
        """
        if company_id is None:
            raise ValueError("Company ID is required for cold start")

        start_time = datetime.now()

        result = ColdStartResult(
            company_id=company_id,
            industry=industry.value,
            status="in_progress",
        )

        try:
            # Get industry FAQs
            industry_faqs = self._get_industry_faqs(industry)

            # Prepare all documents
            documents = []

            # Add industry FAQs
            if self.config.include_industry_faqs:
                for category, faqs in industry_faqs.items():
                    for faq in faqs[:self.config.max_faqs_per_category]:
                        documents.append({
                            "content": self._format_faq(faq, company_name),
                            "metadata": {
                                "type": "faq",
                                "category": category,
                                "industry": industry.value,
                                "source": "cold_start_industry",
                            }
                        })
                result.categories_created = len(industry_faqs)

            # Add general FAQs
            if self.config.include_general_faqs:
                general_faqs = INDUSTRY_FAQS.get(
                    IndustryType.GENERAL.value, {}
                ).get("general", [])
                for faq in general_faqs[:self.config.max_faqs_per_category]:
                    documents.append({
                        "content": self._format_faq(faq, company_name),
                        "metadata": {
                            "type": "faq",
                            "category": "general",
                            "source": "cold_start_general",
                        }
                    })

            # Add custom FAQs
            if custom_faqs:
                for faq in custom_faqs[:self.config.max_faqs_per_category]:
                    documents.append({
                        "content": self._format_faq(faq, company_name),
                        "metadata": {
                            "type": "faq",
                            "category": faq.get("category", "custom"),
                            "source": "cold_start_custom",
                        }
                    })

            # Ingest all documents
            ingest_results = self.kb_manager.ingest_batch(documents)

            # Count successes
            result.documents_ingested = sum(
                1 for r in ingest_results if r.status == "success"
            )
            result.faqs_added = result.documents_ingested

            # Collect errors
            for r in ingest_results:
                if r.status == "error" and r.message:
                    result.errors.append(r.message)

            result.status = "completed" if result.documents_ingested > 0 else "failed"
            result.metadata["industry"] = industry.value

            self._cold_starts_completed += 1
            self._total_documents_ingested += result.documents_ingested

            logger.info({
                "event": "cold_start_completed",
                "company_id": str(company_id),
                "industry": industry.value,
                "documents_ingested": result.documents_ingested,
                "status": result.status,
            })

        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))

            logger.error({
                "event": "cold_start_failed",
                "company_id": str(company_id),
                "error": str(e),
            })

        # Finalize timing
        result.processing_time_ms = (
            datetime.now() - start_time
        ).total_seconds() * 1000

        return result

    def get_available_industries(self) -> List[str]:
        """
        Get list of available industry types.

        Returns:
            List of industry type values
        """
        return [industry.value for industry in IndustryType]

    def get_industry_preview(
        self,
        industry: IndustryType
    ) -> Dict[str, int]:
        """
        Preview FAQ counts for an industry.

        Args:
            industry: Industry type to preview

        Returns:
            Dict with category counts
        """
        industry_faqs = INDUSTRY_FAQS.get(industry.value, {})
        return {
            category: len(faqs)
            for category, faqs in industry_faqs.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cold start statistics.

        Returns:
            Dict with stats
        """
        return {
            "cold_starts_completed": self._cold_starts_completed,
            "total_documents_ingested": self._total_documents_ingested,
            "average_documents_per_bootstrap": (
                self._total_documents_ingested / self._cold_starts_completed
                if self._cold_starts_completed > 0 else 0
            ),
            "available_industries": self.get_available_industries(),
            "config": self.config.model_dump(),
        }

    def _get_industry_faqs(
        self,
        industry: IndustryType
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Get FAQs for an industry.

        Args:
            industry: Industry type

        Returns:
            Dict of category to FAQ list
        """
        return INDUSTRY_FAQS.get(industry.value, INDUSTRY_FAQS.get(IndustryType.GENERAL.value, {}))

    def _format_faq(
        self,
        faq: Dict[str, str],
        company_name: Optional[str] = None
    ) -> str:
        """
        Format FAQ for ingestion.

        Args:
            faq: FAQ dict with question and answer
            company_name: Optional company name

        Returns:
            Formatted FAQ string
        """
        question = faq.get("question", "")
        answer = faq.get("answer", "")

        # Add company name personalization
        if company_name:
            answer = answer.replace("We", company_name)
            answer = answer.replace("our", f"{company_name}'s")

        return f"Q: {question}\n\nA: {answer}"


def create_cold_start_data(
    industry: IndustryType,
    custom_questions: Optional[List[Dict[str, str]]] = None
) -> List[Dict[str, Any]]:
    """
    Create cold start data for a specific industry.

    Utility function to prepare cold start documents without
    full bootstrap process.

    Args:
        industry: Industry type
        custom_questions: Optional custom questions to add

    Returns:
        List of document dicts ready for ingestion
    """
    documents = []

    industry_faqs = INDUSTRY_FAQS.get(industry.value, {})
    cold_start = ColdStart()

    for category, faqs in industry_faqs.items():
        for faq in faqs:
            documents.append({
                "content": cold_start._format_faq(faq),
                "metadata": {
                    "type": "faq",
                    "category": category,
                    "industry": industry.value,
                }
            })

    if custom_questions:
        for q in custom_questions:
            documents.append({
                "content": cold_start._format_faq(q),
                "metadata": {
                    "type": "faq",
                    "category": q.get("category", "custom"),
                    "industry": industry.value,
                }
            })

    return documents
