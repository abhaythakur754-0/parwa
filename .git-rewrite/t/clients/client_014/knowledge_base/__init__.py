"""Client 014 Knowledge Base - TravelEase Hospitality

This module contains the knowledge base for TravelEase Hospitality.
"""

# Knowledge base for travel & hospitality support
FAQ_ENTRIES = [
    {
        "question": "Can I cancel my booking?",
        "answer": "Cancellation policies vary by booking. Check your confirmation email for specific terms."
    },
    {
        "question": "How do I change my flight?",
        "answer": "Contact us or use your booking management page. Change fees may apply depending on fare type."
    },
    {
        "question": "Do you offer travel insurance?",
        "answer": "Yes, we offer comprehensive travel insurance during booking or up to 24 hours after."
    },
    {
        "question": "What is your price match guarantee?",
        "answer": "If you find a lower price within 24 hours of booking, we'll match it and give you 10% off."
    }
]

POLICIES = {
    "cancellation_free_hours": 24,
    "price_match_hours": 24,
    "loyalty_points_per_dollar": 2,
    "group_booking_discount_threshold": 10,
    "emergency_support_24_7": True
}

DESTINATION_INFO = {
    "domestic": "US and Canada destinations",
    "caribbean": "Mexico, Caribbean, Central America",
    "europe": "European destinations",
    "asia": "Asia and Pacific destinations",
    "international": "All other international destinations"
}
