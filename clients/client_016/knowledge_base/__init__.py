"""Client 016 Knowledge Base - ManufacturePro B2B

This module contains the knowledge base for ManufacturePro B2B.
"""

FAQ_ENTRIES = [
    {
        "question": "How do I place a bulk order?",
        "answer": "Contact your account representative or use our B2B portal for bulk orders. Minimum order quantities apply."
    },
    {
        "question": "What is your lead time for custom manufacturing?",
        "answer": "Lead times vary by product complexity. Standard items: 2-4 weeks. Custom orders: 6-12 weeks."
    },
    {
        "question": "Do you offer technical support for equipment?",
        "answer": "Yes, our technical support team is available during business hours. Premium support available for contract customers."
    },
    {
        "question": "How do I track my shipment?",
        "answer": "Log into your account to track shipments. B2B customers receive proactive updates via email."
    }
]

POLICIES = {
    "minimum_order_value": 500,
    "payment_terms_days": 30,
    "bulk_discount_threshold": 10000,
    "warranty_years": 2,
    "technical_support_hours": "7am-7pm EST"
}
