"""Client 020 Knowledge Base - ImpactHope Nonprofit

This module contains the knowledge base for ImpactHope Nonprofit.
"""

FAQ_ENTRIES = [
    {
        "question": "How can I make a donation?",
        "answer": "Donate online through our website, via mail, or set up recurring donations. All donations are tax-deductible."
    },
    {
        "question": "Will I receive a tax receipt?",
        "answer": "Yes, tax receipts are automatically sent via email for online donations. Mail donors receive receipts by January 31."
    },
    {
        "question": "How can I volunteer?",
        "answer": "Sign up through our volunteer portal. Browse opportunities and register for events that match your interests."
    },
    {
        "question": "How is my donation used?",
        "answer": "View our annual impact report to see how donations are allocated. We maintain full transparency."
    },
    {
        "question": "Can I donate to a specific cause?",
        "answer": "Yes, you can designate your donation to specific programs during the donation process."
    }
]

POLICIES = {
    "tax_deductible": True,
    "min_online_donation": 5,
    "recurring_options": ["monthly", "quarterly", "annually"],
    "volunteer_min_age": 16,
    "impact_report_frequency": "annual"
}
