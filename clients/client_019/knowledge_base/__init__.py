"""Client 019 Knowledge Base - LegalEase Services

This module contains the knowledge base for LegalEase Services.
"""

FAQ_ENTRIES = [
    {
        "question": "How do I schedule a consultation?",
        "answer": "Request a consultation through our client portal or call our intake line. We'll match you with the right attorney."
    },
    {
        "question": "Is my communication with the firm confidential?",
        "answer": "Yes, all communications are protected by attorney-client privilege. Our systems are encrypted for your protection."
    },
    {
        "question": "How do I access my case documents?",
        "answer": "Log into the secure client portal to access all case documents, updates, and communications."
    },
    {
        "question": "What are your billing practices?",
        "answer": "We offer hourly, flat-fee, and retainer billing depending on case type. You'll receive detailed monthly invoices."
    },
    {
        "question": "Can I get a copy of my signed documents?",
        "answer": "All signed documents are stored in your client portal. Download copies anytime."
    }
]

POLICIES = {
    "consultation_fee": "Varies by practice area",
    "response_sla_hours": 24,
    "document_retention_years": 7,
    "conflict_check_required": True,
    "secure_communication_only": True
}
