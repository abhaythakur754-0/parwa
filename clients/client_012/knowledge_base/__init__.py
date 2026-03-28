"""Client 012 Knowledge Base - EduLearn Platform

This module contains the knowledge base for EduLearn Platform.
"""

# Knowledge base for EdTech platform support
FAQ_ENTRIES = [
    {
        "question": "How do I reset my password?",
        "answer": "Click 'Forgot Password' on the login page. Check your email for reset instructions."
    },
    {
        "question": "Can I download courses for offline viewing?",
        "answer": "Yes, Pro and Enterprise subscribers can download courses on our mobile app."
    },
    {
        "question": "How do I get a certificate?",
        "answer": "Complete all course modules and pass the final assessment with 70% or higher."
    },
    {
        "question": "What is your refund policy?",
        "answer": "We offer a 14-day money-back guarantee for all paid subscriptions."
    }
]

POLICIES = {
    "subscription_tiers": ["free", "basic", "pro", "enterprise"],
    "certificate_passing_score": 70,
    "refund_period_days": 14,
    "max_devices_per_account": 3,
    "languages_supported": 15
}
