"""Seed data for clients 031-050.

This module provides seed data generation for clients 031-050,
extending the PARWA platform from 30 to 50 clients.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class ClientSeed:
    """Client seed data structure."""
    client_id: str
    client_name: str
    industry: str
    variant: str
    timezone: str
    employees: int
    users: int
    monthly_tickets: int
    founded_year: int
    services: List[str]
    features: Dict[str, bool]


CLIENTS_031_050 = [
    ClientSeed(
        client_id="client_031",
        client_name="EduTech Academy",
        industry="education_technology",
        variant="parwa_junior",
        timezone="America/New_York",
        employees=150,
        users=50000,
        monthly_tickets=800,
        founded_year=2018,
        services=["online_courses", "certifications", "corporate_training", "tutoring"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_032",
        client_name="FoodDash Delivery",
        industry="food_delivery",
        variant="mini_parwa",
        timezone="America/Los_Angeles",
        employees=300,
        users=500000,
        monthly_tickets=2500,
        founded_year=2019,
        services=["food_delivery", "grocery_delivery", "restaurant_partnerships"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_033",
        client_name="SecureLife Insurance",
        industry="insurtech",
        variant="parwa_high",
        timezone="America/Chicago",
        employees=500,
        users=200000,
        monthly_tickets=1200,
        founded_year=2015,
        services=["life_insurance", "health_insurance", "claims_processing", "underwriting"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_034",
        client_name="TeleCare Health",
        industry="telehealth",
        variant="parwa_high",
        timezone="America/New_York",
        employees=200,
        users=100000,
        monthly_tickets=900,
        founded_year=2017,
        services=["video_consultations", "prescription_refills", "health_monitoring", "specialist_referrals"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_035",
        client_name="FreightPro Logistics",
        industry="logistics",
        variant="parwa_junior",
        timezone="America/Denver",
        employees=400,
        users=25000,
        monthly_tickets=600,
        founded_year=2016,
        services=["freight_shipping", "warehousing", "supply_chain", "tracking"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_036",
        client_name="PropTech Realty",
        industry="real_estate",
        variant="parwa_junior",
        timezone="America/New_York",
        employees=100,
        users=10000,
        monthly_tickets=400,
        founded_year=2019,
        services=["property_listings", "virtual_tours", "tenant_support", "lease_management"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_037",
        client_name="GameZone Entertainment",
        industry="gaming",
        variant="mini_parwa",
        timezone="America/Los_Angeles",
        employees=250,
        users=1000000,
        monthly_tickets=3000,
        founded_year=2018,
        services=["game_support", "in_app_purchases", "account_management", "tournaments"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_038",
        client_name="CryptoVault Exchange",
        industry="cryptocurrency",
        variant="parwa_high",
        timezone="UTC",
        employees=150,
        users=75000,
        monthly_tickets=1500,
        founded_year=2020,
        services=["trading", "wallet_management", "security", "staking"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_039",
        client_name="DentalCare Plus",
        industry="healthcare",
        variant="parwa_junior",
        timezone="America/Chicago",
        employees=80,
        users=15000,
        monthly_tickets=350,
        founded_year=2017,
        services=["appointments", "dental_procedures", "insurance_billing", "emergency_care"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_040",
        client_name="ShipFast Global",
        industry="shipping",
        variant="parwa_junior",
        timezone="UTC",
        employees=350,
        users=20000,
        monthly_tickets=500,
        founded_year=2018,
        services=["international_shipping", "tracking", "customs_clearance", "insurance"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_041",
        client_name="PeopleFirst HR",
        industry="hr_software",
        variant="parwa_junior",
        timezone="America/New_York",
        employees=120,
        users=30000,
        monthly_tickets=450,
        founded_year=2019,
        services=["payroll", "benefits", "employee_onboarding", "performance_reviews"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_042",
        client_name="StyleHub Fashion",
        industry="ecommerce",
        variant="mini_parwa",
        timezone="America/Los_Angeles",
        employees=200,
        users=200000,
        monthly_tickets=1800,
        founded_year=2017,
        services=["fashion_retail", "returns", "style_consultations", "loyalty_program"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_043",
        client_name="WealthWise Capital",
        industry="wealth_management",
        variant="parwa_high",
        timezone="America/New_York",
        employees=300,
        users=40000,
        monthly_tickets=800,
        founded_year=2014,
        services=["portfolio_management", "investment_advice", "retirement_planning", "tax_optimization"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_044",
        client_name="PetCare Veterinary",
        industry="veterinary",
        variant="parwa_junior",
        timezone="America/Chicago",
        employees=60,
        users=8000,
        monthly_tickets=250,
        founded_year=2018,
        services=["appointments", "pet_health", "prescriptions", "emergency_care"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_045",
        client_name="ExpressCourier X",
        industry="courier",
        variant="parwa_junior",
        timezone="America/Denver",
        employees=450,
        users=35000,
        monthly_tickets=700,
        founded_year=2019,
        services=["same_day_delivery", "tracking", "signature_required", "insurance"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_046",
        client_name="LegalTech Pro",
        industry="legal_software",
        variant="parwa_high",
        timezone="America/New_York",
        employees=180,
        users=12000,
        monthly_tickets=500,
        founded_year=2016,
        services=["document_management", "case_tracking", "client_portal", "billing"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_047",
        client_name="TechGear Electronics",
        industry="electronics",
        variant="mini_parwa",
        timezone="America/Los_Angeles",
        employees=280,
        users=150000,
        monthly_tickets=2000,
        founded_year=2015,
        services=["product_support", "warranty", "repairs", "installation"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_048",
        client_name="PayFlow Gateway",
        industry="payment_processing",
        variant="parwa_high",
        timezone="UTC",
        employees=220,
        users=50000,
        monthly_tickets=1000,
        founded_year=2017,
        services=["payment_processing", "fraud_detection", "merchant_support", "reconciliation"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
    ClientSeed(
        client_id="client_049",
        client_name="MindWell Mental Health",
        industry="mental_health",
        variant="parwa_junior",
        timezone="America/New_York",
        employees=100,
        users=20000,
        monthly_tickets=600,
        founded_year=2019,
        services=["therapy_sessions", "counseling", "crisis_support", "wellness_programs"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True},
    ),
    ClientSeed(
        client_id="client_050",
        client_name="GlobalShip Enterprise",
        industry="logistics",
        variant="parwa_high",
        timezone="UTC",
        employees=600,
        users=45000,
        monthly_tickets=900,
        founded_year=2012,
        services=["global_shipping", "customs", "freight_forwarding", "supply_chain_management"],
        features={"shadow_mode": True, "auto_escalation": True, "sentiment_analysis": True, "voice_support": True},
    ),
]


def get_all_clients() -> List[ClientSeed]:
    """Get all clients 031-050."""
    return CLIENTS_031_050


def get_client_by_id(client_id: str) -> ClientSeed:
    """Get a specific client by ID."""
    for client in CLIENTS_031_050:
        if client.client_id == client_id:
            return client
    raise ValueError(f"Client {client_id} not found")


def get_clients_by_variant(variant: str) -> List[ClientSeed]:
    """Get all clients of a specific variant."""
    return [c for c in CLIENTS_031_050 if c.variant == variant]


def get_clients_by_industry(industry: str) -> List[ClientSeed]:
    """Get all clients in a specific industry."""
    return [c for c in CLIENTS_031_050 if c.industry == industry]


def get_total_stats() -> Dict[str, Any]:
    """Get total statistics for clients 031-050."""
    return {
        "total_clients": len(CLIENTS_031_050),
        "total_employees": sum(c.employees for c in CLIENTS_031_050),
        "total_users": sum(c.users for c in CLIENTS_031_050),
        "total_monthly_tickets": sum(c.monthly_tickets for c in CLIENTS_031_050),
        "by_variant": {
            "mini_parwa": len([c for c in CLIENTS_031_050 if c.variant == "mini_parwa"]),
            "parwa_junior": len([c for c in CLIENTS_031_050 if c.variant == "parwa_junior"]),
            "parwa_high": len([c for c in CLIENTS_031_050 if c.variant == "parwa_high"]),
        },
    }


def validate_all_clients() -> bool:
    """Validate all clients have required fields."""
    for client in CLIENTS_031_050:
        assert client.client_id.startswith("client_"), f"Invalid client_id: {client.client_id}"
        assert len(client.client_name) > 0, f"Empty client_name for {client.client_id}"
        assert len(client.industry) > 0, f"Empty industry for {client.client_id}"
        assert client.variant in ["mini_parwa", "parwa_junior", "parwa_high"], f"Invalid variant for {client.client_id}"
        assert client.employees > 0, f"Invalid employees for {client.client_id}"
        assert client.users > 0, f"Invalid users for {client.client_id}"
    return True


if __name__ == "__main__":
    stats = get_total_stats()
    print("Clients 031-050 Statistics:")
    print(f"  Total Clients: {stats['total_clients']}")
    print(f"  Total Employees: {stats['total_employees']}")
    print(f"  Total Users: {stats['total_users']}")
    print(f"  Total Monthly Tickets: {stats['total_monthly_tickets']}")
    print(f"  By Variant: {stats['by_variant']}")
