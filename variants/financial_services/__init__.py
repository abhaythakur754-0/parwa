"""
Financial Services Variant Module.

This module provides specialized support for financial services clients
including banks, credit unions, investment firms, and fintech companies.

Features:
- SOX (Sarbanes-Oxley) compliance
- FINRA regulatory compliance
- Enhanced audit trails
- Fraud detection capabilities
- PII/PCI data protection
- Transaction monitoring

Regulatory Compliance:
- SOX Section 404: Internal controls
- FINRA Rule 3110: Supervision
- FINRA Rule 4511: Books and records
- PCI DSS: Payment card data protection
- GLBA: Gramm-Leach-Bliley Act privacy

Usage:
    from variants.financial_services import FinancialServicesConfig
    from variants.financial_services.compliance import SOXCompliance, FINRARules
"""

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

__all__ = [
    "FinancialServicesConfig",
    "get_financial_services_config",
]

__version__ = "1.0.0"
