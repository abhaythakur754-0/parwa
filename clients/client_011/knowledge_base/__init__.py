"""Client 011 Knowledge Base - RetailPro E-commerce

This module contains the knowledge base for RetailPro E-commerce.
"""

# Knowledge base for retail e-commerce support
FAQ_ENTRIES = [
    {
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days of purchase. Items must be unused and in original packaging."
    },
    {
        "question": "How do I track my order?",
        "answer": "You can track your order using the tracking number sent to your email, or log into your account."
    },
    {
        "question": "Do you offer international shipping?",
        "answer": "Yes, we ship to over 50 countries. Shipping rates and times vary by destination."
    }
]

POLICIES = {
    "return_period_days": 30,
    "free_shipping_threshold": 50,
    "loyalty_points_per_dollar": 1,
    "gift_card_min": 10,
    "gift_card_max": 500
}
