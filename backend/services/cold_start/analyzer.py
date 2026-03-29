"""
Cold Start Analyzer Module

Analyzes client data to detect industry, extract keywords, identify compliance requirements,
and suggest initial FAQ topics for knowledge base bootstrapping.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import logging

from shared.core_functions.logger import get_logger

logger = get_logger("cold_start_analyzer")


@dataclass
class AnalysisResult:
    """Result of client data analysis"""
    industry: str
    confidence: float
    keywords: List[str]
    compliance_requirements: List[str]
    suggested_faq_topics: List[str]
    risk_factors: List[str]
    metadata: Dict[str, Any]


class IndustryAnalyzer:
    """
    Analyzes client data to determine industry and related configurations.
    
    Uses pattern matching and keyword extraction to identify industry,
    compliance requirements, and suggest appropriate FAQ topics.
    """
    
    # Industry detection patterns with weights
    INDUSTRY_PATTERNS = {
        "ecommerce": {
            "keywords": [
                ("shop", 3), ("store", 3), ("cart", 2), ("checkout", 2),
                ("product", 2), ("order", 2), ("shipping", 2), ("refund", 2),
                ("customer", 1), ("inventory", 2), ("sku", 3), ("payment", 1),
                ("delivery", 2), ("ecommerce", 4), ("retail", 2), ("purchase", 1),
            ],
            "domains": ["shopify", "woocommerce", "magento", "bigcommerce", "amazon"],
            "compliance": ["gdpr", "pci_dss", "ccpa"],
        },
        "saas": {
            "keywords": [
                ("subscription", 3), ("trial", 2), ("plan", 2), ("billing", 2),
                ("api", 2), ("integration", 2), ("dashboard", 1), ("user", 1),
                ("team", 1), ("account", 1), ("feature", 1), ("platform", 2),
                ("software", 2), ("cloud", 2), ("saas", 4), ("enterprise", 1),
            ],
            "domains": ["stripe", "paddle", "chargebee", "recurly", "intercom"],
            "compliance": ["gdpr", "soc2", "iso27001"],
        },
        "healthcare": {
            "keywords": [
                ("patient", 3), ("appointment", 2), ("prescription", 3), ("insurance", 2),
                ("medical", 3), ("hipaa", 4), ("doctor", 2), ("hospital", 3),
                ("clinic", 2), ("health", 2), ("treatment", 2), ("diagnosis", 2),
                ("telehealth", 3), ("ehr", 3), ("pharmacy", 3), ("wellness", 1),
            ],
            "domains": ["epic", "cerner", "athenahealth", "drchrono", "zocdoc"],
            "compliance": ["hipaa", "gdpr", "hitech"],
        },
        "logistics": {
            "keywords": [
                ("shipping", 3), ("delivery", 2), ("tracking", 2), ("warehouse", 3),
                ("freight", 3), ("supply chain", 3), ("logistics", 4), ("cargo", 3),
                ("dispatch", 2), ("fleet", 3), ("inventory", 2), ("distribution", 2),
                ("carrier", 2), ("shipment", 3), ("transport", 2), ("fulfillment", 3),
            ],
            "domains": ["fedex", "ups", "dhl", "usps", "flexport", "project44"],
            "compliance": ["gdpr", "c_tpAT"],
        },
        "financial": {
            "keywords": [
                ("banking", 3), ("investment", 3), ("loan", 2), ("credit", 2),
                ("payment", 1), ("transaction", 2), ("compliance", 2), ("finance", 3),
                ("account", 1), ("debit", 2), ("mortgage", 3), ("insurance", 1),
                ("wealth", 2), ("trading", 3), ("fintech", 4), ("bank", 3),
            ],
            "domains": ["plaid", "stripe", "square", "chime", "robinhood", "coinbase"],
            "compliance": ["pci_dss", "sox", "gdpr", "finra", "sec"],
        },
    }
    
    # FAQ topic suggestions by industry
    FAQ_TOPICS = {
        "ecommerce": [
            "Order Status & Tracking",
            "Returns & Refunds",
            "Shipping Information",
            "Payment Methods",
            "Product Availability",
            "Account Management",
            "Promotions & Discounts",
            "Size & Fit Guides",
            "Store Policies",
            "Contact Information",
        ],
        "saas": [
            "Getting Started",
            "Pricing & Plans",
            "Account Management",
            "Billing & Invoices",
            "API Documentation",
            "Integrations",
            "Security & Privacy",
            "Feature Requests",
            "Troubleshooting",
            "Upgrade/Downgrade",
        ],
        "healthcare": [
            "Appointment Scheduling",
            "Insurance & Billing",
            "Prescription Refills",
            "Medical Records",
            "Privacy & HIPAA",
            "Telehealth Services",
            "Office Hours & Location",
            "Emergency Procedures",
            "Patient Portal Access",
            "Provider Information",
        ],
        "logistics": [
            "Shipment Tracking",
            "Delivery Estimates",
            "Shipping Rates",
            "Pickup Services",
            "Customs & International",
            "Claims & Insurance",
            "Account Management",
            "Freight Services",
            "Warehouse Services",
            "Contact Support",
        ],
        "financial": [
            "Account Opening",
            "Transaction History",
            "Security & Fraud",
            "Loan Applications",
            "Interest Rates",
            "Fees & Charges",
            "Card Services",
            "Fund Transfers",
            "Statements & Documents",
            "Regulatory Information",
        ],
    }
    
    def __init__(self):
        self.min_confidence_threshold = 0.3
    
    async def analyze(
        self,
        company_data: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Analyze company data to determine industry and related information.
        
        Args:
            company_data: Company information including name, description,
                         website, industry hints, etc.
            
        Returns:
            AnalysisResult with industry, confidence, keywords, and suggestions
        """
        logger.info(f"Analyzing company data: {company_data.get('name', 'Unknown')}")
        
        # Extract text for analysis
        text_content = self._extract_text_content(company_data)
        
        # Detect industry with confidence
        industry, confidence = self._detect_industry(text_content, company_data)
        
        # Extract relevant keywords
        keywords = self._extract_keywords(text_content, industry)
        
        # Get compliance requirements
        compliance = self._get_compliance_requirements(industry)
        
        # Generate FAQ suggestions
        faq_topics = self._suggest_faq_topics(industry, keywords)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(company_data, industry)
        
        return AnalysisResult(
            industry=industry,
            confidence=confidence,
            keywords=keywords,
            compliance_requirements=compliance,
            suggested_faq_topics=faq_topics,
            risk_factors=risk_factors,
            metadata={
                "analyzed_at": self._get_timestamp(),
                "source_fields": list(company_data.keys()),
            }
        )
    
    def _extract_text_content(self, company_data: Dict[str, Any]) -> str:
        """Extract all text content from company data for analysis."""
        text_parts = []
        
        # Primary fields
        for field in ["name", "description", "industry", "website"]:
            if field in company_data and company_data[field]:
                text_parts.append(str(company_data[field]))
        
        # Additional metadata
        if "keywords" in company_data:
            text_parts.extend(company_data["keywords"])
        
        if "products" in company_data:
            text_parts.extend(company_data["products"])
        
        return " ".join(text_parts).lower()
    
    def _detect_industry(
        self,
        text_content: str,
        company_data: Dict[str, Any]
    ) -> Tuple[str, float]:
        """
        Detect industry from text content and company data.
        
        Returns tuple of (industry, confidence).
        """
        # Check for explicit industry hint
        explicit_industry = company_data.get("industry", "").lower()
        if explicit_industry in self.INDUSTRY_PATTERNS:
            return explicit_industry, 1.0
        
        # Score each industry
        scores = {}
        text_lower = text_content.lower()
        
        for industry, patterns in self.INDUSTRY_PATTERNS.items():
            score = 0
            max_score = 0
            
            # Keyword matching
            for keyword, weight in patterns["keywords"]:
                max_score += weight * 3  # Max possible score
                if keyword in text_lower:
                    score += weight
            
            # Domain matching
            for domain in patterns.get("domains", []):
                if domain in text_lower:
                    score += 5
            
            # Normalize score
            scores[industry] = score / max(max_score, 1)
        
        # Get best match
        if scores:
            best_industry = max(scores, key=scores.get)
            confidence = scores[best_industry]
            
            # Check if confidence is above threshold
            if confidence >= self.min_confidence_threshold:
                return best_industry, min(confidence, 1.0)
        
        return "general", 0.0
    
    def _extract_keywords(self, text_content: str, industry: str) -> List[str]:
        """Extract relevant keywords from text content."""
        keywords = set()
        text_lower = text_content.lower()
        
        # Get industry-specific keywords
        if industry in self.INDUSTRY_PATTERNS:
            for keyword, _ in self.INDUSTRY_PATTERNS[industry]["keywords"]:
                if keyword in text_lower:
                    keywords.add(keyword)
        
        # Extract common business terms
        business_terms = [
            "support", "help", "service", "contact", "account",
            "order", "payment", "delivery", "return", "refund"
        ]
        for term in business_terms:
            if term in text_lower:
                keywords.add(term)
        
        return list(keywords)
    
    def _get_compliance_requirements(self, industry: str) -> List[str]:
        """Get compliance requirements for an industry."""
        if industry in self.INDUSTRY_PATTERNS:
            return self.INDUSTRY_PATTERNS[industry].get("compliance", [])
        return ["gdpr"]  # Default to GDPR
    
    def _suggest_faq_topics(
        self,
        industry: str,
        keywords: List[str]
    ) -> List[str]:
        """Generate FAQ topic suggestions based on industry and keywords."""
        base_topics = self.FAQ_TOPICS.get(industry, self.FAQ_TOPICS["ecommerce"])
        
        # Prioritize topics based on keywords
        prioritized = []
        remaining = []
        
        for topic in base_topics:
            topic_lower = topic.lower()
            if any(kw in topic_lower for kw in keywords):
                prioritized.append(topic)
            else:
                remaining.append(topic)
        
        return prioritized + remaining
    
    def _identify_risk_factors(
        self,
        company_data: Dict[str, Any],
        industry: str
    ) -> List[str]:
        """Identify potential risk factors for the client."""
        risks = []
        
        # Check for missing critical data
        critical_fields = ["name", "email", "industry"]
        for field in critical_fields:
            if field not in company_data or not company_data[field]:
                risks.append(f"missing_{field}")
        
        # Industry-specific risks
        if industry == "healthcare":
            if "hipaa_compliant" not in company_data.get("compliance", []):
                risks.append("hipaa_compliance_required")
        
        if industry == "financial":
            if "pci_compliant" not in company_data.get("compliance", []):
                risks.append("pci_compliance_required")
        
        return risks
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


def analyze_client(client_data: Dict[str, Any]) -> AnalysisResult:
    """
    Convenience function to analyze client data.
    
    Args:
        client_data: Company information dictionary
        
    Returns:
        AnalysisResult with industry detection and suggestions
    """
    analyzer = IndustryAnalyzer()
    import asyncio
    return asyncio.run(analyzer.analyze(client_data))
