"""
Public API Endpoints

Public endpoints for landing page data (no authentication required).
- GET /api/public/features - Feature highlights for carousel
- GET /api/public/stats - Public statistics (optional)

Based on ONBOARDING_SPEC.md v2.0 Section 2.3
"""

from fastapi import APIRouter
from typing import List, Dict, Any

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/features")
async def get_features() -> List[Dict[str, Any]]:
    """
    Get feature highlights for landing page carousel.
    
    Returns the 5 slides with psychological triggers:
    1. Control Everything by Chat - SIMPLICITY
    2. No Tech Skills Needed - FEAR REMOVAL
    3. Self-Learning AI - EFFORT REDUCTION
    4. Eliminates 90% Daily Work - TIME FREEDOM
    5. Your Iron Man Jarvis - ASPIRATION
    
    Returns:
        List of feature objects with icon, title, description, and trigger
    """
    return [
        {
            "id": 1,
            "icon": "💬",
            "title": "Control Everything by Chat",
            "description": "Just type and control - no complex dashboards. No training needed. Just talk.",
            "psychological_trigger": "SIMPLICITY",
            "gradient": "from-primary-500 to-primary-700",
        },
        {
            "id": 2,
            "icon": "🎯",
            "title": "No Tech Skills Needed",
            "description": "Not technical? Never done customer care? Perfect. Jarvis handles everything. You just focus on your business.",
            "psychological_trigger": "FEAR REMOVAL",
            "gradient": "from-success-500 to-success-700",
        },
        {
            "id": 3,
            "icon": "🧠",
            "title": "Self-Learning AI",
            "description": "Upload your docs. Jarvis learns. Every question makes it smarter. Zero manual training needed.",
            "psychological_trigger": "EFFORT REDUCTION",
            "gradient": "from-purple-500 to-purple-700",
        },
        {
            "id": 4,
            "icon": "⚡",
            "title": "Eliminates 90% Daily Work",
            "description": "90% of support tickets are repetitive. Jarvis handles them all. You get 40+ hours back every week.",
            "psychological_trigger": "TIME FREEDOM",
            "gradient": "from-warning-500 to-warning-700",
        },
        {
            "id": 5,
            "icon": "🦾",
            "title": "Your Iron Man Jarvis",
            "description": "Like Tony Stark's Jarvis, but for your business. Your personal AI officer that never sleeps, never complains, and always delivers.",
            "psychological_trigger": "ASPIRATION",
            "gradient": "from-primary-600 to-purple-600",
        },
    ]


@router.get("/stats")
async def get_public_stats() -> Dict[str, Any]:
    """
    Get public statistics for landing page.
    
    Note: These are representative values for marketing purposes.
    Actual values would come from real data analysis.
    
    Returns:
        Dictionary with public statistics
    """
    return {
        "automation_rate": "90%",
        "hours_saved_per_week": "40+",
        "availability": "24/7/365",
        "response_time": "Instant",
        "starting_price": "$999/month",
    }


@router.get("/industries")
async def get_industries() -> List[Dict[str, Any]]:
    """
    Get available industry options.
    
    Only 4 industries are supported:
    - E-commerce
    - SaaS
    - Logistics
    - Others
    
    Returns:
        List of industry objects with name and description
    """
    return [
        {
            "id": "ecommerce",
            "name": "E-commerce",
            "description": "Online stores, retail",
            "variants": ["Order Management", "Returns", "Product FAQ", "Shipping", "Payment Issues"],
        },
        {
            "id": "saas",
            "name": "SaaS",
            "description": "Software companies",
            "variants": ["Technical Support", "Billing", "Feature Requests", "API Support", "Account Issues"],
        },
        {
            "id": "logistics",
            "name": "Logistics",
            "description": "Shipping, delivery, warehouse",
            "variants": ["Tracking", "Delivery Issues", "Warehouse Queries", "Fleet Management", "Customs"],
        },
        {
            "id": "others",
            "name": "Others",
            "description": "Any other industry",
            "variants": ["Custom variants based on industry"],
        },
    ]
