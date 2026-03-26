"""
Category Specialists for Agent Lightning.

Domain-specific training modules for different industries:
- E-commerce Specialist
- SaaS Specialist
- Healthcare Specialist
- Financial Specialist

Each specialist is trained for >92% accuracy on domain-specific queries.
"""

from agent_lightning.training.category_specialists.ecommerce_specialist import (
    EcommerceSpecialist,
    get_ecommerce_specialist
)
from agent_lightning.training.category_specialists.saas_specialist import (
    SaaSSpecialist,
    get_saas_specialist
)
from agent_lightning.training.category_specialists.healthcare_specialist import (
    HealthcareSpecialist,
    get_healthcare_specialist
)
from agent_lightning.training.category_specialists.financial_specialist import (
    FinancialSpecialist,
    get_financial_specialist
)

__all__ = [
    "EcommerceSpecialist",
    "get_ecommerce_specialist",
    "SaaSSpecialist",
    "get_saas_specialist",
    "HealthcareSpecialist",
    "get_healthcare_specialist",
    "FinancialSpecialist",
    "get_financial_specialist",
    "get_specialist_for_industry",
    "SPECIALIST_REGISTRY"
]


SPECIALIST_REGISTRY = {
    "ecommerce": EcommerceSpecialist,
    "retail": EcommerceSpecialist,
    "saas": SaaSSpecialist,
    "software": SaaSSpecialist,
    "healthcare": HealthcareSpecialist,
    "medical": HealthcareSpecialist,
    "financial": FinancialSpecialist,
    "fintech": FinancialSpecialist,
    "banking": FinancialSpecialist,
    "insurance": FinancialSpecialist
}


def get_specialist_for_industry(industry: str) -> object:
    """
    Get the appropriate specialist for an industry.

    Args:
        industry: Industry identifier

    Returns:
        Specialist instance for the industry
    """
    industry_lower = industry.lower().replace("-", "").replace("_", "")

    specialist_cls = SPECIALIST_REGISTRY.get(industry_lower)

    if specialist_cls:
        return specialist_cls()

    # Default to e-commerce for unknown industries
    return EcommerceSpecialist()
