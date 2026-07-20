"""
Fake CRM Server - Simulates HubSpot/Salesforce/Zendesk APIs
For testing Parwa CRM Analyzer feature

Author: Super Z (Testing Infrastructure)
Purpose: Production-ready mock CRM for integration testing

Honest Status: This is a TEST SERVER with FAKE DATA only
"""

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json
import random
import hashlib
import secrets

app = FastAPI(
    title="FakeCRM API",
    description="Mock CRM platform simulating HubSpot/Salesforce/Zendesk for testing",
    version="1.0.0-test"
)

# CORS - Allow Parwa to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# IN-MEMORY DATABASE (Realistic Fake Data)
# ============================================================

DB = {
    "contacts": [],
    "companies": [],
    "deals": [],
    "tickets": [],
    "orders": [],
    "products": [],
    "notes": [],
    "activities": [],
    "oauth_tokens": [],
    "webhooks": [],
}

# Track connected apps (for testing)
CONNECTED_APPS = []

# ============================================================
# GENERATE REALISTIC FAKE DATA
# ============================================================

FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", 
               "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
               "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
               "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
              "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker"]

COMPANY_NAMES = ["TechCorp Inc", "Global Solutions Ltd", "InnovateTech", "DataDriven Co",
                 "CloudSystems", "AI Dynamics", "NextGen Software", "Digital Frontier",
                 "CyberSecure Corp", "FutureTech Industries", "SmartScale LLC", "Apex Digital",
                 "Quantum Labs", "Pixel Perfect", "Streamline Services"]

DOMAINS = ["techcorp.com", "globalsolutions.io", "innovatetech.co", "datadriven.net",
           "cloudsystems.com", "aidynamics.io", "nextgen.software", "digitalfrontier.tech",
           "cybersecurecorp.com", "futuretech.industries", "smartscale.llc", "apex.digital"]

TITLES = ["CEO", "CTO", "CFO", "VP of Sales", "VP of Marketing", "Sales Director",
          "Marketing Manager", "Product Manager", "Engineering Lead", "Customer Success Manager",
          "Head of Operations", "Business Development Manager", "Account Executive",
          "Senior Developer", "DevOps Engineer", "Data Scientist"]

INDUSTRIES = ["Technology", "SaaS", "E-commerce", "Healthcare", "Finance", "Education",
              "Manufacturing", "Retail", "Consulting", "Media & Entertainment"]

TICKET_SUBJECTS = [
    "Unable to login to dashboard",
    "Feature request: Bulk export functionality",
    "Integration with Salesforce not working",
    "Billing discrepancy on invoice #4521",
    "How to set up automated workflows?",
    "API rate limiting issues",
    "Data sync delay between systems",
    "Custom field not appearing in reports",
    "SSO configuration help needed",
    "Performance degradation after update",
    "Mobile app crashes on iOS 17",
    "Webhook delivery failures",
    "User permission management questions",
    "Import failed - CSV format error",
    "Two-factor authentication problems"
]

TICKET_STATUSES = ["new", "open", "pending", "waiting_on_customer", "resolved", "closed"]
TICKET_PRIORITIES = ["low", "medium", "high", "urgent"]

DEAL_NAMES = [
    "Enterprise License - Q4 2026",
    "Annual Subscription Renewal",
    "Professional Services Engagement",
    "API Integration Project",
    "Training & Onboarding Package",
    "White-label Partnership Deal",
    "Volume Discount Agreement",
    "Technical Support Contract",
    "Custom Development Work",
    "Data Migration Services"
]

DEAL_STAGES = ["lead", "qualified", "proposal_sent", "negotiation", "closed_won", "closed_lost"]
PIPELINE_NAMES = ["Sales Pipeline", "Enterprise Deals", "SMB Pipeline"]

PRODUCT_NAMES = [
    "Pro Plan Monthly", "Enterprise Annual", "API Access Tier", 
    "Support Add-on", "Training Module", "Integration Pack",
    "Analytics Pro", "Security Suite", "Storage Extension", "User Seat"
]

NOTE_BODIES = [
    "Great call! They're interested in enterprise features.",
    "Follow up next week after their budget approval.",
    "Technical team reviewed requirements - feasible.",
    "Competitor is Salesforce - need to highlight our advantages.",
    "Decision maker is the CTO, timeline is Q1 2026.",
    "They requested a custom demo for next Tuesday.",
    "Pricing concern - may need discount approval.",
    "Existing system is legacy, migration will be complex."
]


def generate_fake_data():
    """Generate comprehensive fake CRM data"""
    
    # Generate Companies
    for i in range(15):
        company = {
            "id": f"company-{uuid.uuid4().hex[:8]}",
            "name": COMPANY_NAMES[i % len(COMPANY_NAMES)],
            "domain": DOMAINS[i % len(DOMAINS)],
            "industry": INDUSTRIES[random.randint(0, len(INDUSTRIES)-1)],
            "size": random.choice(["1-10", "11-50", "51-200", "201-500", "500+"]),
            "revenue": f"${random.randint(1, 1000)}M",
            "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
            "website": f"https://{DOMAINS[i % len(DOMAINS)]}",
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
            "is_customer": random.random() > 0.3,
            "lifecycle_stage": random.choice(["subscriber", "lead", "marketing_qualified_lead", "sales_qualified_lead", "opportunity", "customer", "churned"]),
            "address": {
                "street": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Park', 'Market', 'Industrial'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Ln'])}",
                "city": random.choice(["New York", "San Francisco", "Austin", "Chicago", "Seattle", "Boston", "Denver", "Miami"]),
                "state": random.choice(["NY", "CA", "TX", "IL", "WA", "MA", "CO", "FL"]),
                "zip_code": f"{random.randint(10000, 99999)}",
                "country": "US"
            }
        }
        DB["companies"].append(company)
    
    # Generate Contacts (linked to companies)
    for i in range(50):
        company = DB["companies"][i % len(DB["companies"])]
        contact = {
            "id": f"contact-{uuid.uuid4().hex[:8]}",
            "firstname": FIRST_NAMES[i % len(FIRST_NAMES)],
            "lastname": LAST_NAMES[i % len(LAST_NAMES)],
            "email": f"{FIRST_NAMES[i % len(FIRST_NAMES)].lower()}.{LAST_NAMES[i % len(LAST_NAMES)].lower()}@{company['domain']}",
            "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
            "jobtitle": TITLES[i % len(TITLES)],
            "company": company["name"],
            "company_id": company["id"],
            "industry": company["industry"],
            "lifecyclestage": random.choice(["subscriber", "lead", "mql", "sql", "opportunity", "customer", "evangelist"]),
            "lead_score": random.randint(0, 100),
            "source": random.choice(["organic_search", "paid_search", "social_media", "referral", "email_campaign", "direct", "event"]),
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
            "updated_at": datetime.now().isoformat(),
            "properties": {
                "hs_email_domain": company["domain"],
                "hs_is_contact": True,
                "num_unique_forms_filled": random.randint(0, 10),
                "num_pageviews": random.randint(0, 500),
                "last_form_fill_date": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat() if random.random() > 0.3 else None,
                "number_of_employees": random.choice(["1-10", "11-50", "51-200", "201-500", "500+"])
            },
            "engagement": {
                "emails_opened": random.randint(0, 50),
                "emails_clicked": random.randint(0, 30),
                "meetings_booked": random.randint(0, 5),
                "website_visits": random.randint(0, 100),
                "last_engagement_date": (datetime.now() - timedelta(days=random.randint(0, 60))).isoformat()
            }
        }
        DB["contacts"].append(contact)
    
    # Generate Deals (linked to contacts and companies)
    deal_id_counter = 1
    for i in range(25):
        contact = DB["contacts"][i * 2 % len(DB["contacts"])]
        company = DB["companies"][i % len(DB["companies"])]
        
        amount = random.choice([
            random.randint(500, 5000),   # Small deals
            random.randint(5000, 25000), # Medium deals
            random.randint(25000, 150000), # Large/Enterprise
        ])
        
        deal = {
            "id": f"deal-{deal_id_counter:05d}",
            "dealname": DEAL_NAMES[i % len(DEAL_NAMES)],
            "pipeline": PIPELINE_NAMES[i % len(PIPELINE_NAMES)],
            "dealstage": DEAL_STAGES[min(i % 7, len(DEAL_STAGES)-1)],
            "amount": amount,
            "currency": "USD",
            "closedate": (datetime.now() + timedelta(days=random.randint(-90, 180))).isoformat(),
            "probability": _get_stage_probability(DEAL_STAGES[min(i % 7, len(DEAL_STAGES)-1)]),
            "contact_id": contact["id"],
            "company_id": company["id"],
            "company_name": company["name"],
            "contact_name": f"{contact['firstname']} {contact['lastname']}",
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 120))).isoformat(),
            "updated_at": datetime.now().isoformat(),
            "owner": random.choice(["sales-rep-1", "sales-rep-2", "sales-rep-3", "ae-senior"]),
            "type": random.choice(["newbusiness", "existingbusiness", "upsell", "cross-sell"]),
            "description": f"Deal for {company['name']} - {DEAL_NAMES[i % len(DEAL_NAMES)].lower()}",
            "properties": {
                "days_to_close": random.randint(-30, 120),
                "num_associated_contacts": random.randint(1, 3),
                "num_notes": random.randint(0, 10),
                "num_meetings_booked": random.randint(0, 5),
                "deal_source": random.choice(["inbound", "outbound", "partner_referral", "event", "webinar"])
            }
        }
        DB["deals"].append(deal)
        deal_id_counter += 1
    
    # Generate Tickets (Support tickets like Zendesk/Freshdesk)
    ticket_id_counter = 1
    for i in range(35):
        contact = DB["contacts"][i * 3 % len(DB["contacts"])] if random.random() > 0.2 else None
        
        created = datetime.now() - timedelta(days=random.randint(0, 60))
        status = TICKET_STATUSES[min(random.randint(0, len(TICKET_STATUSES)-1), len(TICKET_STATUSES)-1)]
        
        # If resolved/closed, make sure it has an updated date
        if status in ["resolved", "closed"]:
            updated = created + timedelta(hours=random.randint(1, 168))
        else:
            updated = datetime.now()
        
        ticket = {
            "id": f"{ticket_id_counter:06d}",
            "subject": TICKET_SUBJECTS[i % len(TICKET_SUBJECTS)],
            "description": f"Detailed description about: {TICKET_SUBJECTS[i % len(TICKET_SUBJECTS)].lower()}. Customer needs assistance with this issue as soon as possible.",
            "status": status,
            "priority": TICKET_PRIORITIES[random.randint(0, len(TICKET_PRIORITIES)-1)],
            "type": random.choice(["question", "incident", "problem", "task", "feature_request"]),
            "requester": {
                "id": contact["id"] if contact else f"anonymous-{uuid.uuid4().hex[:6]}",
                "name": f"{contact['firstname']} {contact['lastname']}" if contact else "Anonymous User",
                "email": contact["email"] if contact else "anonymous@example.com"
            } if contact or random.random() > 0.3 else None,
            "assignee": random.choice(["agent-smith", "agent-johnson", "agent-williams", "agent-brown", None]),
            "group": random.choice(["support", "technical", "billing", "sales", None]),
            "created_at": created.isoformat(),
            "updated_at": updated.isoformat(),
            "due_at": (created + timedelta(days=random.randint(1, 14))).isoformat() if random.random() > 0.3 else None,
            "satisfaction_rating": random.choice([None, None, None, "good", "good", "excellent", "poor"]) if status == "closed" else None,
            "tags": random.sample(["urgent", "billing", "technical", "feature-request", "bug", "enterprise", "smb"], k=random.randint(1, 3)),
            "via": random.choice(["web", "email", "api", "chat", "telephony"]),
            "custom_fields": {
                "account_tier": random.choice(["free", "starter", "professional", "enterprise"]),
                "product_area": random.choice(["dashboard", "api", "integrations", "billing", "mobile", "reports"]),
                "environment": random.choice(["production", "staging", "development"])
            },
            "metrics": {
                "replies": random.randint(0, 15),
                "first_response_time_minutes": random.randint(5, 1440),
                "resolution_time_hours": random.randint(1, 168) if status in ["resolved", "closed"] else None,
                "reopens": random.randint(0, 3)
            }
        }
        DB["tickets"].append(ticket)
        ticket_id_counter += 1
    
    # Generate Orders (E-commerce style)
    order_id_counter = 1000
    for i in range(40):
        contact = DB["contacts"][i % len(DB["contacts"])]
        company = DB["companies"][i % len(DB["companies"])]
        
        created = datetime.now() - timedelta(days=random.randint(0, 180))
        items_count = random.randint(1, 5)
        item_price = random.choice([29, 49, 99, 199, 499, 999])
        
        order = {
            "id": f"ORD-{order_id_counter:06d}",
            "order_number": f"ORD-{order_id_counter:06d}",
            "contact_id": contact["id"],
            "contact_name": f"{contact['firstname']} {contact['lastname']}",
            "contact_email": contact["email"],
            "company_id": company["id"],
            "company_name": company["name"],
            "status": random.choice(["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]),
            "subtotal": items_count * item_price,
            "tax": round(items_count * item_price * 0.08, 2),
            "discount": round(items_count * item_price * random.choice([0, 0.1, 0.15, 0.2]), 2) if random.random() > 0.6 else 0,
            "total": 0,  # Will calculate below
            "currency": "USD",
            "items": [
                {
                    "name": PRODUCT_NAMES[j % len(PRODUCT_NAMES)],
                    "quantity": 1,
                    "price": item_price,
                    "product_id": f"prod-{j+1:03d}"
                }
                for j in range(items_count)
            ],
            "payment_method": random.choice(["credit_card", "paypal", "bank_transfer", "crypto"]),
            "payment_status": random.choice(["paid", "pending", "failed", "refunded"]),
            "created_at": created.isoformat(),
            "updated_at": (created + timedelta(hours=random.randint(1, 72))).isoformat(),
            "shipped_at": (created + timedelta(hours=random.randint(24, 168))).isoformat() if random.random() > 0.4 else None,
            "delivered_at": (created + timedelta(days=random.randint(3, 14))).isoformat() if random.random() > 0.5 else None,
            "shipping_address": {
                "street": f"{random.randint(100, 9999)} Delivery Dr",
                "city": contact.get("address", {}).get("city", "Unknown") if isinstance(contact.get("address"), dict) else "Unknown",
                "state": "CA",
                "zip_code": f"{random.randint(10000, 99999)}",
                "country": "US"
            },
            "tags": random.sample(["rush-order", "gift-wrap", "corporate", "subscription", "one-time"], k=random.randint(0, 2)),
            "source": random.choice(["website", "mobile_app", "api", "phone", "partner"]),
            "notes": "Order notes here" if random.random() > 0.7 else None
        }
        # Calculate total
        order["total"] = order["subtotal"] + order["tax"] - order["discount"]
        DB["orders"].append(order)
        order_id_counter += 1
    
    # Generate Products
    for i, name in enumerate(PRODUCT_NAMES):
        product = {
            "id": f"prod-{i+1:03d}",
            "name": name,
            "description": f"Premium {name} offering with full features and support included.",
            "price": [29, 49, 99, 199, 499, 999][i % 6],
            "currency": "USD",
            "category": random.choice(["subscription", "license", "service", "add-on"]),
            "active": True,
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat()
        }
        DB["products"].append(product)
    
    # Generate Notes/Activities
    for i in range(30):
        note_type = random.choice(["note", "call", "meeting", "email", "task"])
        note = {
            "id": f"note-{uuid.uuid4().hex[:8]}",
            "type": note_type,
            "body": NOTE_BODIES[i % len(NOTE_BODIES)] if note_type == "note" else f"{note_type.capitalize()} logged for follow-up.",
            "associated_type": random.choice(["contact", "deal", "company", "ticket"]),
            "associated_id": random.choice(DB["contacts"])["id"] if note_type in ["note", "email"] else random.choice(DB["deals"])["id"],
            "created_by": random.choice(["user-1", "user-2", "automation"]),
            "created_at": (datetime.now() - timedelta(days=random.randint(0, 90))).isoformat()
        }
        DB["notes"].append(note)


def _get_stage_probability(stage: str) -> int:
    probabilities = {
        "lead": 10,
        "qualified": 20,
        "proposal_sent": 40,
        "negotiation": 60,
        "closed_won": 100,
        "closed_lost": 0
    }
    return probabilities.get(stage, 25)


# Initialize data on startup
generate_fake_data()

print("=" * 60)
print("  🎭 FAKE CRM SERVER INITIALIZED")
print(f"  📊 Data Generated:")
print(f"     • Companies: {len(DB['companies'])}")
print(f"     • Contacts: {len(DB['contacts'])}")
print(f"     • Deals: {len(DB['deals'])}")
print(f"     • Tickets: {len(DB['tickets'])}")
print(f"     • Orders: {len(DB['orders'])}")
print(f"     • Products: {len(DB['products'])}")
print(f"     • Notes/Activities: {len(DB['notes'])}")
print("=" * 60)


# ============================================================
# OAUTH SIMULATION (Like HubSpot/OAuth2 providers)
# ============================================================

class OAuthAuthorizeRequest(BaseModel):
    client_id: str
    redirect_uri: str
    response_type: str = "code"
    scope: str = ""
    state: str = ""

class TokenRequest(BaseModel):
    grant_type: str
    code: str
    client_id: str
    client_secret: str
    redirect_uri: str


@app.get("/oauth/authorize")
async def oauth_authorize(client_id: str, redirect_uri: str, state: str = "", scope: str = ""):
    """
    Simulate OAuth authorization page (like HubSpot's OAuth screen)
    This is what users see when connecting an integration
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FakeCRM - Connect Your Account</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
            .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 450px; text-align: center; }}
            .logo {{ font-size: 48px; margin-bottom: 20px; }}
            h1 {{ color: #333; margin-bottom: 10px; }}
            p {{ color: #666; margin-bottom: 30px; }}
            .permissions {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: left; }}
            .permission-item {{ padding: 8px 0; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 10px; }}
            .permission-icon {{ color: #4CAF50; }}
            .btn {{ display: inline-block; padding: 14px 32px; font-size: 16px; border: none; border-radius: 6px; cursor: pointer; margin: 5px; text-decoration: none; }}
            .btn-connect {{ background: #FF6B35; color: white; }} 
            .btn-cancel {{ background: #e0e0e0; color: #666; }}
            .info {{ font-size: 12px; color: #999; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎭</div>
            <h1>FakeCRM</h1>
            <p>Parwa wants to access your FakeCRM account</p>
            
            <div class="permissions">
                <strong>This application will be able to:</strong>
                <div class="permission-item">
                    <span class="permission-icon">✓</span> Read your contacts
                </div>
                <div class="permission-item">
                    <span class="permission-icon">✓</span> Read your deals/pipelines
                </div>
                <div class="permission-item">
                    <span class="permission-icon">✓</span> Read your support tickets
                </div>
                <div class="permission-item">
                    <span class="permission-icon">✓</span> Read your orders data
                </div>
                <div class="permission-item">
                    <span class="permission-icon">✓</span> Create webhooks
                </div>
            </div>
            
            <a href="/oauth/approve?client_id={client_id}&redirect_uri={redirect_uri}&state={state}" class="btn btn-connect">
                ✨ Connect Account
            </a>
            <a href="/oauth/deny?redirect_uri={redirect_uri}&state={state}" class="btn btn-cancel">
                Cancel
            </a>
            
            <div class="info">
                <p>This is a <strong>TEST ENVIRONMENT</strong></p>
                <p>All data is fake and generated for testing purposes</p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/oauth/approve")
async def oauth_approve(client_id: str, redirect_uri: str, state: str = ""):
    """Simulate user approving OAuth connection"""
    auth_code = f"fake-auth-code-{secrets.token_hex(16)}"
    
    # Store the token info
    token_data = {
        "code": auth_code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "created_at": datetime.now().isoformat()
    }
    DB["oauth_tokens"].append(token_data)
    
    # Redirect back with authorization code
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{separator}code={auth_code}&state={state}")


@app.get("/oauth/deny")
async def oauth_deny(redirect_uri: str, state: str = ""):
    """Simulate user denying OAuth"""
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(url=f"{redirect_uri}{separator}error=access_denied&state={state}")


@app.post("/oauth/token")
async def oauth_token(request: TokenRequest):
    """
    Exchange authorization code for access token
    Simulates real OAuth token endpoint
    """
    # Verify code exists
    valid_token = next((t for t in DB["oauth_tokens"] if t["code"] == request.code), None)
    if not valid_token:
        raise HTTPException(status_code=400, detail="Invalid authorization code")
    
    # Generate fake tokens
    access_token = f"fake-access-token-{secrets.token_hex(32)}"
    refresh_token = f"fake-refresh-token-{secrets.token_hex(32)}"
    
    # Record this as a connected app
    CONNECTED_APPS.append({
        "client_id": request.client_id,
        "connected_at": datetime.now().isoformat(),
        "access_token": access_token
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_token": refresh_token,
        "scope": "contacts deals tickets orders webhooks read write"
    }


# ============================================================
# API ENDPOINTS (HubSpot-style REST API)
# ============================================================

def verify_token(authorization: str = None):
    """Simple token verification - accepts any bearer token for testing"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    return True


# ---- CONTACTS API ----

@app.get("/crm/v3/objects/contacts")
async def list_contacts(
    authorization: str = Header(None),
    limit: int = Query(100, ge=1, le=250),
    after: str = None,
    properties: str = None
):
    """List contacts - HubSpot style"""
    verify_token(authorization)
    
    props = properties.split(",") if properties else None
    contacts = DB["contacts"]
    
    # Apply pagination
    start_idx = 0
    if after:
        try:
            start_idx = next(i for i, c in enumerate(contacts) if c["id"] == after) + 1
        except StopIteration:
            pass
    
    paginated = contacts[start_idx:start_idx + limit]
    
    results = []
    for contact in paginated:
        result = {"id": contact["id"], "properties": {}}
        for key, value in contact.items():
            if key != "id":
                if isinstance(value, dict):
                    result["properties"][key] = json.dumps(value)
                elif isinstance(value, list):
                    result["properties"][key] = ",".join(str(v) for v in value)
                else:
                    result["properties"][key] = str(value)
        results.append(result)
    
    has_more = start_idx + limit < len(contacts)
    next_after = contacts[start_idx + limit]["id"] if has_more else None
    
    return {
        "results": results,
        "paging": {
            "next": {"after": next_after} if has_more else None
        }
    }


@app.get("/crm/v3/objects/contacts/{contact_id}")
async def get_contact(contact_id: str, authorization: str = Header(None)):
    """Get single contact"""
    verify_token(authorization)
    
    contact = next((c for c in DB["contacts"] if c["id"] == contact_id), None)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"id": contact["id"], "properties": contact}


@app.post("/crm/v3/objects/contacts/search")
async def search_contacts(request: Request, authorization: str = Header(None)):
    """Search contacts - used by CRM Analyzer"""
    verify_token(authorization)
    
    body = await request.json()
    filters = body.get("filters", [])
    limit = body.get("limit", 100)
    
    results = DB["contacts"]
    
    # Apply filters if provided
    for f in filters:
        prop_name = f.get("propertyName", "")
        value = f.get("value", "")
        operator = f.get("operator", "EQ")
        
        if operator == "EQ":
            results = [c for c in results if str(c.get(prop_name, "")) == str(value)]
        elif operator == "CONTAINS_TOKEN":
            results = [c for c in results if value.lower() in str(c.get(prop_name, "")).lower()]
    
    return {
        "total": len(results),
        "results": [{"id": c["id"], "properties": c} for c in results[:limit]]
    }


# ---- COMPANIES API ----

@app.get("/crm/v3/objects/companies")
async def list_companies(authorization: str = Header(None), limit: int = Query(100)):
    """List companies"""
    verify_token(authorization)
    
    return {
        "results": [{"id": c["id"], "properties": c} for c in DB["companies"][:limit]],
        "total": len(DB["companies"])
    }


# ---- DEALS API ----

@app.get("/crm/v3/objects/deals")
async def list_deals(authorization: str = Header(None), limit: int = Query(100)):
    """List deals/pipelines"""
    verify_token(authorization)
    
    return {
        "results": [{"id": d["id"], "properties": d} for d in DB["deals"][:limit]],
        "total": len(DB["deals"])
    }


@app.get("/crm/v3/pipelines/deals")
async def get_deal_pipelines(authorization: str = Header(None)):
    """Get deal pipeline stages"""
    verify_token(authorization)
    
    pipelines = [
        {
            "pipelineId": "default",
            "label": "Sales Pipeline",
            "stages": [
                {"stageId": "lead", "label": "Lead", "metadata": {"probability": 10}},
                {"stageId": "qualified", "label": "Qualified", "metadata": {"probability": 20}},
                {"stageId": "proposal_sent", "label": "Proposal Sent", "metadata": {"probability": 40}},
                {"stageId": "negotiation", "label": "Negotiation", "metadata": {"probability": 60}},
                {"stageId": "closed_won", "label": "Closed Won", "metadata": {"probability": 100}},
                {"stageId": "closed_lost", "label": "Closed Lost", "metadata": {"probability": 0}}
            ]
        }
    ]
    
    return {"results": pipelines}


# ---- TICKETS API (Zendesk-style) ----

@app.get("/api/v2/tickets")
async def list_tickets(
    authorization: str = Header(None),
    per_page: int = Query(30),
    page: int = Query(1),
    status: str = None
):
    """List support tickets - Zendesk style"""
    verify_token(authorization)
    
    tickets = DB["tickets"]
    
    if status:
        tickets = [t for t in tickets if t["status"] == status]
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated = tickets[start:end]
    
    return {
        "tickets": paginated,
        "count": len(tickets),
        "next_page": page + 1 if end < len(tickets) else None
    }


@app.get("/api/v2/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, authorization: str = Header(None)):
    """Get single ticket"""
    verify_token(authorization)
    
    ticket = next((t for t in DB["tickets"] if t["id"] == ticket_id), None)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return {"ticket": ticket}


@app.post("/api/v2/tickets")
async def create_ticket(request: Request, authorization: str = Header(None)):
    """Create new ticket"""
    verify_token(authorization)
    
    body = await request.json()
    ticket = {
        "id": str(len(DB["tickets"]) + 1).zfill(6),
        **body,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "new"
    }
    DB["tickets"].append(ticket)
    
    return {"ticket": ticket}, 201


# ---- ORDERS/E-COMMERCE API (Shopify-style) ----

@app.get("/admin/api/2024-01/orders.json")
async def list_orders(
    authorization: str = Header(None),
    limit: int = Query(50),
    status: str = None
):
    """List orders - Shopify style"""
    verify_token(authorization)
    
    orders = DB["orders"]
    
    if status:
        orders = [o for o in orders if o["status"] == status]
    
    return {
        "orders": orders[:limit],
        "count": len(orders)
    }


@app.get("/admin/api/2024-01/orders/{order_id}.json")
async def get_order(order_id: str, authorization: str = Header(None)):
    """Get single order"""
    verify_token(authorization)
    
    order = next((o for o in DB["orders"] if o["id"] == order_id or o["order_number"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {"order": order}


# ---- WEBHOOKS API ----

@app.post("/webhooks/subscribe")
async def subscribe_webhook(request: Request, authorization: str = Header(None)):
    """Subscribe to webhooks"""
    verify_token(authorization)
    
    body = await request.json()
    webhook = {
        "id": f"wh-{uuid.uuid4().hex[:8]}",
        "url": body.get("url"),
        "events": body.get("events", []),
        "created_at": datetime.now().isoformat(),
        "status": "active"
    }
    DB["webhooks"].append(webhook)
    
    return {"webhook": webhook}, 201


@app.get("/webhooks")
async def list_webhooks(authorization: str = Header(None)):
    """List active webhooks"""
    verify_token(authorization)
    return {"webhooks": DB["webhooks"]}


# ---- ANALYTICS/DASHBOARD API ----

@app.get("/analytics/overview")
async def get_analytics_overview(authorization: str = Header(None)):
    """
    Returns analytics summary - THIS IS WHAT PARWA'S CRM ANALYZER WILL READ
    This provides the data profile for analysis
    """
    verify_token(authorization)
    
    total_deal_value = sum(d["amount"] for d in DB["deals"] if d["dealstage"] not in ["closed_lost"])
    won_deal_value = sum(d["amount"] for d in DB["deals"] if d["dealstage"] == "closed_won")
    open_tickets = len([t for t in DB["tickets"] if t["status"] in ["new", "open", "pending"]])
    total_orders_value = sum(o["total"] for o in DB["orders"] if o["status"] in ["delivered", "shipped"])
    
    return {
        "summary": {
            "total_contacts": len(DB["contacts"]),
            "total_companies": len(DB["companies"]),
            "total_deals": len(DB["deals"]),
            "total_tickets": len(DB["tickets"]),
            "total_orders": len(DB["orders"]),
            "total_products": len(DB["products"]),
            "total_pipeline_value": total_deal_value,
            "won_deal_value": won_deal_value,
            "avg_deal_size": total_deal_value / max(len(DB["deals"]), 1),
            "open_tickets": open_tickets,
            "ticket_resolution_rate": len([t for t in DB["tickets"] if t["status"] == "closed"]) / max(len(DB["tickets"]), 1),
            "total_revenue": total_orders_value,
            "active_webhooks": len(DB["webhooks"]),
            "connected_apps": len(CONNECTED_APPS)
        },
        "breakdown": {
            "by_status": {
                "tickets": {status: len([t for t in DB["tickets"] if t["status"] == status]) for status in TICKET_STATUSES},
                "deals": {stage: len([d for d in DB["deals"] if d["dealstage"] == stage]) for stage in DEAL_STAGES},
                "orders": {status: len([o for o in DB["orders"] if o["status"] == status]) for status in ["pending", "processing", "shipped", "delivered", "cancelled"]}
            },
            "by_priority": {
                "tickets": {p: len([t for t in DB["tickets"] if t["priority"] == p]) for p in TICKET_PRIORITIES}
            },
            "by_industry": {
                ind: len([c for c in DB["contacts"] if c.get("industry") == ind]) for ind in INDUSTRIES
            }
        },
        "recent_activity": sorted(DB["notes"], key=lambda x: x["created_at"], reverse=True)[:10],
        "generated_at": datetime.now().isoformat(),
        "data_freshness": "realtime",
        "server_info": {
            "name": "FakeCRM Test Server",
            "version": "1.0.0-test",
            "purpose": "Testing Only - All Data is Fake",
            "disclaimer": "This is NOT a real CRM. For Parwa CRM Analyzer testing only."
        }
    }


# ---- HEALTH / STATUS ----

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "server": "FakeCRM Test Server",
        "version": "1.0.0-test",
        "timestamp": datetime.now().isoformat(),
        "data_stats": {
            "contacts": len(DB["contacts"]),
            "companies": len(DB["companies"]),
            "deals": len(DB["deals"]),
            "tickets": len(DB["tickets"]),
            "orders": len(DB["orders"]),
            "products": len(DB["products"]),
            "connected_apps": len(CONNECTED_APPS)
        },
        "warning": "THIS IS A TEST SERVER WITH FAKE DATA"
    }


@app.get("/")
async def root():
    """Root endpoint - Server info"""
    return {
        "name": "🎭 FakeCRM Server",
        "description": "Mock CRM platform for testing Parwa integrations",
        "version": "1.0.0-test",
        "status": "running",
        "purpose": "TESTING ONLY - All data is fake",
        "available_endpoints": {
            "oauth": "/oauth/authorize",
            "contacts": "/crm/v3/objects/contacts",
            "companies": "/crm/v3/objects/companies", 
            "deals": "/crm/v3/objects/deals",
            "pipelines": "/crm/v3/pipelines/deals",
            "tickets": "/api/v2/tickets",
            "orders": "/admin/api/2024-01/orders.json",
            "analytics": "/analytics/overview",
            "health": "/health"
        },
        "test_credentials": {
            "note": "Any Bearer token works for testing",
            "example_header": "Authorization: Bearer test-token-123"
        },
        "data_summary": {
            "contacts": len(DB["contacts"]),
            "companies": len(DB["companies"]),
            "deals": len(DB["deals"]),
            "tickets": len(DB["tickets"]),
            "orders": len(DB["orders"])
        }
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  🚀 Starting FakeCRM Server...")
    print("  📍 http://localhost:8888")
    print("  ⚠️  FOR TESTING ONLY - All data is fake!")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8888)
