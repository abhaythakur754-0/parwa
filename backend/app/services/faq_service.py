"""
FAQ Management Service (Mini Parwa Feature)

Manages Frequently Asked Questions for AI reference.
The AI pipeline uses FAQs to provide quick answers to common questions.

Features:
- CRUD operations for FAQs
- Category-based organization
- Search functionality
- AI-friendly formatting
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4
import json

from sqlalchemy.orm import Session

logger = logging.getLogger("parwa.faq_service")


# ── In-Memory FAQ Store (for development/testing) ────────────────────────────
# In production, this would be stored in the database

_faq_store: Dict[str, Dict[str, Any]] = {}

# Default FAQs for new Mini Parwa instances
DEFAULT_FAQS = [
    {
        "id": "faq_001",
        "question": "How do I reset my password?",
        "answer": "You can reset your password by clicking the 'Forgot Password' link on the login page. Enter your email address and we'll send you a reset link.",
        "category": "Account",
        "keywords": ["password", "reset", "login", "forgot"],
    },
    {
        "id": "faq_002",
        "question": "What is the ticket limit for Mini Parwa?",
        "answer": "Mini Parwa includes 2,000 tickets per month. If you need more, you can upgrade to Parwa (5,000 tickets) or High Parwa (15,000 tickets).",
        "category": "Billing",
        "keywords": ["ticket", "limit", "quota", "usage"],
    },
    {
        "id": "faq_003",
        "question": "How do I add a team member?",
        "answer": "Go to Settings > User Management and click 'Invite Team Member'. Enter their email and select their role. Mini Parwa supports up to 3 team members.",
        "category": "Team",
        "keywords": ["team", "member", "invite", "user", "add"],
    },
    {
        "id": "faq_004",
        "question": "What AI features are included in Mini Parwa?",
        "answer": "Mini Parwa includes AI ticket resolution, classification, sentiment analysis, and suggested responses using our Light model. Advanced techniques and Medium/Heavy models are available in higher tiers.",
        "category": "AI Features",
        "keywords": ["ai", "features", "model", "resolution", "classification"],
    },
    {
        "id": "faq_005",
        "question": "How does Shadow Mode work?",
        "answer": "Shadow Mode lets you preview AI actions before they're executed. You can approve, reject, or let AI auto-execute. This gives you control over automated responses while training the system.",
        "category": "AI Features",
        "keywords": ["shadow", "mode", "preview", "approve", "control"],
    },
    {
        "id": "faq_006",
        "question": "Can I upgrade my plan?",
        "answer": "Yes! You can upgrade from Mini Parwa to Parwa or High Parwa at any time. The upgrade takes effect immediately with prorated billing. Go to Billing > Change Plan to see options.",
        "category": "Billing",
        "keywords": ["upgrade", "plan", "change", "billing"],
    },
    {
        "id": "faq_007",
        "question": "What channels are supported?",
        "answer": "Mini Parwa supports Email and Live Chat channels. SMS and Voice channels are available in Parwa and High Parwa tiers.",
        "category": "Channels",
        "keywords": ["channel", "email", "chat", "sms", "voice"],
    },
    {
        "id": "faq_008",
        "question": "How do I upload documents to the Knowledge Base?",
        "answer": "Go to Knowledge Base > Upload and select your documents. Mini Parwa supports up to 100 documents. Supported formats include PDF, DOCX, TXT, and Markdown.",
        "category": "Knowledge Base",
        "keywords": ["kb", "knowledge", "document", "upload", "upload"],
    },
    {
        "id": "faq_009",
        "question": "What are Industry Add-ons?",
        "answer": "Industry Add-ons provide specialized support for E-commerce, SaaS, Logistics, and other industries. They add extra tickets and KB docs. Prices start at $39/month.",
        "category": "Billing",
        "keywords": ["industry", "addon", "ecommerce", "saas", "logistics"],
    },
    {
        "id": "faq_010",
        "question": "How do I cancel my subscription?",
        "answer": "Go to Billing > Cancel Subscription. Your access continues until the end of your current billing period. You can reactivate anytime within 30 days with data retention.",
        "category": "Billing",
        "keywords": ["cancel", "subscription", "billing", "reactivate"],
    },
]


class FAQService:
    """Service for managing FAQs for AI reference."""

    def __init__(self, db: Session = None, company_id: str = None):
        self.db = db
        self.company_id = company_id
        self._initialize_default_faqs()

    def _initialize_default_faqs(self):
        """Initialize default FAQs if not already present."""
        if self.company_id and self.company_id not in _faq_store:
            _faq_store[self.company_id] = {
                faq["id"]: {**faq, "created_at": datetime.now(timezone.utc).isoformat()}
                for faq in DEFAULT_FAQS
            }

    # ── CRUD Operations ─────────────────────────────────────────────────────

    def list_faqs(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List FAQs with optional filtering."""
        if not self.company_id:
            return []

        company_faqs = _faq_store.get(self.company_id, {})
        results = list(company_faqs.values())

        # Filter by category
        if category:
            results = [f for f in results if f.get("category") == category]

        # Search filter
        if search:
            search_lower = search.lower()
            results = [
                f
                for f in results
                if search_lower in f.get("question", "").lower()
                or search_lower in f.get("answer", "").lower()
                or any(search_lower in kw.lower() for kw in f.get("keywords", []))
            ]

        return results[:limit]

    def get_faq(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific FAQ by ID."""
        if not self.company_id:
            return None

        return _faq_store.get(self.company_id, {}).get(faq_id)

    def create_faq(
        self,
        question: str,
        answer: str,
        category: str = "General",
        keywords: List[str] = None,
    ) -> Dict[str, Any]:
        """Create a new FAQ."""
        if not self.company_id:
            raise ValueError("company_id is required")

        faq_id = f"faq_{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        faq = {
            "id": faq_id,
            "question": question,
            "answer": answer,
            "category": category,
            "keywords": keywords or [],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if self.company_id not in _faq_store:
            _faq_store[self.company_id] = {}

        _faq_store[self.company_id][faq_id] = faq
        logger.info(f"Created FAQ {faq_id} for company {self.company_id}")

        return faq

    def update_faq(
        self,
        faq_id: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        category: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an existing FAQ."""
        if not self.company_id:
            return None

        company_faqs = _faq_store.get(self.company_id, {})
        if faq_id not in company_faqs:
            return None

        faq = company_faqs[faq_id]

        if question is not None:
            faq["question"] = question
        if answer is not None:
            faq["answer"] = answer
        if category is not None:
            faq["category"] = category
        if keywords is not None:
            faq["keywords"] = keywords

        faq["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Updated FAQ {faq_id} for company {self.company_id}")
        return faq

    def delete_faq(self, faq_id: str) -> bool:
        """Delete an FAQ."""
        if not self.company_id:
            return False

        company_faqs = _faq_store.get(self.company_id, {})
        if faq_id not in company_faqs:
            return False

        del company_faqs[faq_id]
        logger.info(f"Deleted FAQ {faq_id} for company {self.company_id}")
        return True

    # ── AI-Friendly Methods ─────────────────────────────────────────────────

    def get_faqs_for_ai(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get FAQs relevant to a query for AI reference.

        This method is used by the AI pipeline to find relevant FAQs
        when generating responses.
        """
        results = self.list_faqs(search=query, limit=limit)

        # Format for AI consumption
        formatted = []
        for faq in results:
            formatted.append(
                {
                    "id": faq["id"],
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "category": faq["category"],
                    "relevance": self._calculate_relevance(query, faq),
                }
            )

        # Sort by relevance
        formatted.sort(key=lambda x: x["relevance"], reverse=True)

        return formatted

    def _calculate_relevance(self, query: str, faq: Dict[str, Any]) -> float:
        """Calculate relevance score for a FAQ against a query."""
        query_words = set(query.lower().split())

        # Check question match
        question_words = set(faq.get("question", "").lower().split())
        question_score = len(query_words & question_words) / max(len(query_words), 1)

        # Check keyword match
        keywords = set(kw.lower() for kw in faq.get("keywords", []))
        keyword_score = len(query_words & keywords) / max(len(query_words), 1)

        # Weighted combination
        return (question_score * 0.7) + (keyword_score * 0.3)

    def get_categories(self) -> List[str]:
        """Get all FAQ categories."""
        if not self.company_id:
            return []

        company_faqs = _faq_store.get(self.company_id, {})
        categories = set()

        for faq in company_faqs.values():
            cat = faq.get("category")
            if cat:
                categories.add(cat)

        return sorted(list(categories))

    def export_faqs(self) -> str:
        """Export FAQs as JSON string."""
        if not self.company_id:
            return "[]"

        company_faqs = _faq_store.get(self.company_id, {})
        return json.dumps(list(company_faqs.values()), indent=2)

    def import_faqs(self, faqs_json: str, merge: bool = True) -> int:
        """Import FAQs from JSON string.

        Args:
            faqs_json: JSON string containing array of FAQs
            merge: If True, merge with existing; if False, replace

        Returns:
            Number of FAQs imported
        """
        if not self.company_id:
            return 0

        try:
            faqs = json.loads(faqs_json)
            if not isinstance(faqs, list):
                return 0

            if not merge:
                _faq_store[self.company_id] = {}

            count = 0
            for faq in faqs:
                if "question" in faq and "answer" in faq:
                    self.create_faq(
                        question=faq["question"],
                        answer=faq["answer"],
                        category=faq.get("category", "General"),
                        keywords=faq.get("keywords", []),
                    )
                    count += 1

            logger.info(f"Imported {count} FAQs for company {self.company_id}")
            return count

        except json.JSONDecodeError:
            logger.error("Failed to parse FAQ import JSON")
            return 0


def get_faq_service(db: Session = None, company_id: str = None) -> FAQService:
    """Factory function to get FAQ service instance."""
    return FAQService(db=db, company_id=company_id)
