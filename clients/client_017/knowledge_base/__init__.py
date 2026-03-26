"""Client 017 Knowledge Base - QuickBite Delivery

This module contains the knowledge base for QuickBite Delivery.
"""

FAQ_ENTRIES = [
    {
        "question": "Where is my order?",
        "answer": "Check the app for real-time tracking. You'll see your driver's location and estimated arrival time."
    },
    {
        "question": "My order was wrong or missing items. What do I do?",
        "answer": "Report the issue in the app within 2 hours. We'll arrange a refund or redelivery."
    },
    {
        "question": "Can I cancel my order?",
        "answer": "You can cancel within 2 minutes of placing the order. After that, cancellation fees may apply."
    },
    {
        "question": "How do I contact my driver?",
        "answer": "Use the in-app chat or call button to contact your driver directly."
    },
    {
        "question": "My food arrived cold. Can I get a refund?",
        "answer": "Report this in the app. We may offer partial refund or credits depending on the situation."
    }
]

POLICIES = {
    "delivery_fee": "2.99-5.99 depending on distance",
    "minimum_order": 15,
    "service_areas": ["Los Angeles", "San Francisco", "Seattle"],
    "instant_refund_threshold": 25,
    "cancellation_window_minutes": 2
}
