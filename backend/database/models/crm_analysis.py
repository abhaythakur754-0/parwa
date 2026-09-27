"""
CRM Analysis Models: crm_analysis_results

Stores LLM-powered integration recommendations so they persist
across onboarding → dashboard transition.

BC-001: Every table has company_id.
"""

from datetime import datetime, timezone

import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CRMAnalysisResult(Base):
    __tablename__ = "crm_analysis_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    
    # Analysis metadata
    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    analysis_version = Column(String(20), default="1.0")  # For future schema migrations
    
    # Data profile (what we found)
    data_profile = Column(JSON, nullable=False, default=dict)
    # {
    #   "total_contacts": 2500,
    #   "total_orders": 850,
    #   "total_deals": 0,
    #   "has_products": true,
    #   "has_shipping_addresses": false,
    #   "has_payment_data": false,
    #   "has_email_campaigns": false,
    #   "has_ticket_data": false,
    #   "industries_detected": ["ecommerce"]
    # }
    
    # Connected integrations at time of analysis
    connected_integrations = Column(JSON, nullable=False, default=list)
    # [
    #   {"id": "xxx", "type": "shopify", "name": "Shopify", "category": "ecommerce"}
    # ]
    
    # Detected gaps
    detected_gaps = Column(JSON, nullable=False, default=list)
    # [
    #   {
    #     "id": "shipping_missing",
    #     "category": "shipping",
    #     "severity": "high",
    #     "message": "You have orders but no shipping integration",
    #     "recommended": ["shipstation", "aftership"]
    #   }
    # ]
    
    # LLM-generated recommendations
    recommendations = Column(JSON, nullable=False, default=list)
    # [
    #   {
    #     "integration_key": "stripe",
    #     "name": "Stripe",
    #     "category": "payments",
    #     "priority": "high",
    #     "reason": "Essential for processing payments",
    #     "business_impact": "Enable online transactions"
    #   }
    # ]
    
    # Overall assessment from LLM
    analysis_summary = Column(Text, default="")
    # "Your e-commerce setup is missing critical payment and shipping integrations..."
    
    # Tracking
    is_actioned = Column(Boolean, default=False)  # User acted on recommendations?
    actioned_at = Column(DateTime)
    recommendations_accepted = Column(JSON, nullable=False, default=list)  # Keys of accepted recs
    
    # Metadata
    llm_model_used = Column(String(100), default="")  # e.g., "z-ai/glm-5.2"
    llm_tokens_used = Column(Integer, default=0)
    analysis_duration_ms = Column(Integer, default=0)  # How long the analysis took
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<CRMAnalysisResult(id={self.id[:8]}..., company_id={self.company_id[:8]}..., recs={len(self.recommendations or [])})>"
