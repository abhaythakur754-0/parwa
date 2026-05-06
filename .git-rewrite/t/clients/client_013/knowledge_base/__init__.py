"""Client 013 Knowledge Base - SecureLife Insurance

This module contains the knowledge base for SecureLife Insurance.
"""

# Knowledge base for insurance support
FAQ_ENTRIES = [
    {
        "question": "How do I file a claim?",
        "answer": "You can file a claim through our mobile app, website, or by calling our claims hotline."
    },
    {
        "question": "What is my policy deductible?",
        "answer": "Your deductible is listed on your policy declaration page. Login to view your specific details."
    },
    {
        "question": "How do I add a driver to my auto policy?",
        "answer": "Contact your agent or use our online portal to add drivers. Additional premium may apply."
    },
    {
        "question": "What is covered under my home insurance?",
        "answer": "Standard coverage includes dwelling, personal property, liability, and additional living expenses."
    }
]

POLICIES = {
    "claim_processing_days": 15,
    "grace_period_days": 30,
    "data_retention_years": 7,
    "audit_logging_enabled": True,
    "session_timeout_minutes": 15
}

COMPLIANCE_NOTES = {
    "sox_compliant": True,
    "naic_compliant": True,
    "hipaa_compliant": True,  # For health policies
    "state_licensed": 50
}
