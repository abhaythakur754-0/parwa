"""Client 015 Knowledge Base - HomeFind Realty

This module contains the knowledge base for HomeFind Realty.
"""

# Knowledge base for real estate support
FAQ_ENTRIES = [
    {
        "question": "How do I schedule a property viewing?",
        "answer": "Click 'Schedule Tour' on any listing or contact the listing agent directly."
    },
    {
        "question": "What is the home buying process?",
        "answer": "Get pre-approved, find a home, make an offer, conduct inspections, close the deal."
    },
    {
        "question": "How do I list my property?",
        "answer": "Contact one of our agents for a free property valuation and listing consultation."
    },
    {
        "question": "Do you offer virtual tours?",
        "answer": "Yes, many of our listings offer 3D virtual tours. Look for the virtual tour icon."
    }
]

POLICIES = {
    "application_fee": 50,
    "security_deposit_max_months": 2,
    "lead_response_sla_minutes": 15,
    "buyer_agent_commission_percent": 3,
    "listing_agreement_min_days": 90
}

PROPERTY_TYPES = {
    "residential": "Single family homes, condos, townhomes",
    "commercial": "Office, retail, industrial properties",
    "luxury": "High-end properties $1M+",
    "rentals": "Apartments and houses for rent",
    "land": "Vacant land and lots"
}
