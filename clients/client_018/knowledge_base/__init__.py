"""Client 018 Knowledge Base - FitLife Wellness

This module contains the knowledge base for FitLife Wellness.
"""

FAQ_ENTRIES = [
    {
        "question": "How do I book a class?",
        "answer": "Book classes through our mobile app or website. Premium members can book up to 7 days in advance."
    },
    {
        "question": "Can I freeze my membership?",
        "answer": "Yes, you can freeze your membership for up to 3 months per year. Contact us or use the member portal."
    },
    {
        "question": "What is your cancellation policy for personal training?",
        "answer": "Cancel or reschedule at least 24 hours in advance. Late cancellations will be charged."
    },
    {
        "question": "Do you offer virtual classes?",
        "answer": "Yes! Premium and Elite members have access to our full library of virtual classes."
    },
    {
        "question": "How do I update my payment method?",
        "answer": "Update your payment method in the app under Account > Payment Methods or at the front desk."
    }
]

POLICIES = {
    "membership_tiers": ["basic", "premium", "elite", "family"],
    "class_cancellation_hours": 4,
    "pt_cancellation_hours": 24,
    "freeze_max_months": 3,
    "cancellation_notice_days": 30
}
