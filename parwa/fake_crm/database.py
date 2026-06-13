"""Fake CRM Database — Realistic in-memory business data.

This is the backend that makes PARWA feel real. Every customer, order,
payment, and interaction is modeled here. The ActionExecutor will
actually modify this data — refunds reduce balances, cancellations
change order status, account modifications update records.

Think of this as the Salesforce/Zendesk/Shopify that PARWA plugs into.
"""

from __future__ import annotations

import copy
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any


# ─── Seed Data — 8 realistic customers with complex histories ──────────────────

_SEED_CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-1001": {
        "customer_id": "CUST-1001",
        "name": "Priya Sharma",
        "email": "priya.sharma@gmail.com",
        "phone": "+919652852014",
        "tier": "premium",
        "account_status": "active",
        "joined": "2023-03-15",
        "lifetime_value": 4520.00,
        "subscription": {"plan": "Pro Annual", "price": 599.00, "renewal_date": "2026-09-15", "status": "active"},
        "orders": [
            {"order_id": "ORD-2001", "date": "2026-06-01", "items": ["Premium Headphones", "USB-C Cable"], "total": 189.99, "status": "delivered", "tracking": "TRK-88291"},
            {"order_id": "ORD-2002", "date": "2026-06-05", "items": ["Wireless Charger"], "total": 49.99, "status": "shipped", "tracking": "TRK-88292"},
            {"order_id": "ORD-2003", "date": "2026-06-08", "items": ["Laptop Stand"], "total": 79.99, "status": "processing", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3001", "order_id": "ORD-2001", "amount": 189.99, "method": "credit_card", "card_last4": "4532", "status": "completed", "date": "2026-06-01"},
            {"payment_id": "PAY-3002", "order_id": "ORD-2001", "amount": 189.99, "method": "credit_card", "card_last4": "4532", "status": "completed", "date": "2026-06-01"},  # DUPLICATE
            {"payment_id": "PAY-3003", "order_id": "ORD-2002", "amount": 49.99, "method": "credit_card", "card_last4": "4532", "status": "completed", "date": "2026-06-05"},
            {"payment_id": "PAY-3004", "order_id": "ORD-2003", "amount": 79.99, "method": "paypal", "status": "completed", "date": "2026-06-08"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4001", "date": "2026-05-20", "subject": "Wrong item received", "status": "resolved", "resolution": "Replacement sent"},
        ],
        "notes": ["VIP customer — handle with priority", "Prefers email communication"],
    },
    "CUST-1002": {
        "customer_id": "CUST-1002",
        "name": "Marcus Johnson",
        "email": "marcus.j@outlook.com",
        "phone": "+1-555-012-3456",
        "tier": "standard",
        "account_status": "active",
        "joined": "2024-11-20",
        "lifetime_value": 890.00,
        "subscription": None,
        "orders": [
            {"order_id": "ORD-2010", "date": "2026-05-28", "items": ["Bluetooth Speaker"], "total": 129.99, "status": "delivered", "tracking": "TRK-77101"},
            {"order_id": "ORD-2011", "date": "2026-06-02", "items": ["Smart Watch"], "total": 299.99, "status": "cancelled", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3010", "order_id": "ORD-2010", "amount": 129.99, "method": "debit_card", "card_last4": "8901", "status": "completed", "date": "2026-05-28"},
            {"payment_id": "PAY-3011", "order_id": "ORD-2011", "amount": 299.99, "method": "debit_card", "card_last4": "8901", "status": "refunded", "date": "2026-06-03"},
        ],
        "tickets": [],
        "notes": [],
    },
    "CUST-1003": {
        "customer_id": "CUST-1003",
        "name": "Aisha Patel",
        "email": "aisha.patel@company.co.in",
        "phone": "+91-99887-76655",
        "tier": "enterprise",
        "account_status": "active",
        "joined": "2022-08-10",
        "lifetime_value": 28750.00,
        "subscription": {"plan": "Enterprise", "price": 2499.00, "renewal_date": "2026-12-10", "status": "active", "seats": 50},
        "orders": [
            {"order_id": "ORD-2020", "date": "2026-05-15", "items": ["Office License Pack x50", "Support Add-on"], "total": 4999.00, "status": "delivered", "tracking": "TRK-66001"},
            {"order_id": "ORD-2021", "date": "2026-06-01", "items": ["Additional 10 Seats"], "total": 499.90, "status": "processing", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3020", "order_id": "ORD-2020", "amount": 4999.00, "method": "wire_transfer", "status": "completed", "date": "2026-05-15"},
            {"payment_id": "PAY-3021", "order_id": "ORD-2021", "amount": 499.90, "method": "invoice", "status": "pending", "date": "2026-06-01"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4010", "date": "2026-04-10", "subject": "Invoice discrepancy", "status": "resolved", "resolution": "Credit issued"},
            {"ticket_id": "TKT-4011", "date": "2026-05-22", "subject": "Need bulk license key", "status": "resolved", "resolution": "Keys provided"},
        ],
        "notes": ["Enterprise account — $2,8750 LTV", "Dedicated account manager: Raj K.", "Net-30 payment terms"],
    },
    "CUST-1004": {
        "customer_id": "CUST-1004",
        "name": "Chen Wei",
        "email": "chen.wei@tech.cn",
        "phone": "+86-138-0013-8000",
        "tier": "premium",
        "account_status": "suspended",
        "joined": "2024-02-28",
        "lifetime_value": 1250.00,
        "subscription": {"plan": "Pro Monthly", "price": 59.99, "renewal_date": "2026-06-15", "status": "past_due"},
        "orders": [
            {"order_id": "ORD-2030", "date": "2026-05-10", "items": ["Cloud Storage 1TB"], "total": 99.99, "status": "delivered", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3030", "order_id": "ORD-2030", "amount": 99.99, "method": "credit_card", "card_last4": "1122", "status": "completed", "date": "2026-05-10"},
            {"payment_id": "PAY-3030D", "order_id": "ORD-2030", "amount": 99.99, "method": "credit_card", "card_last4": "1122", "status": "completed", "date": "2026-06-01"},  # DUPLICATE CHARGE
            {"payment_id": "PAY-3031", "order_id": None, "amount": 59.99, "method": "credit_card", "card_last4": "1122", "status": "failed", "date": "2026-06-15", "failure_reason": "Card declined"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4020", "date": "2026-06-01", "subject": "Account suspended", "status": "open"},
        ],
        "notes": ["Account suspended due to payment failure on 6/15", "Card ending 1122 declined 3 times"],
    },
    "CUST-1005": {
        "customer_id": "CUST-1005",
        "name": "Sarah Mitchell",
        "email": "sarah.m@startup.io",
        "phone": "+1-555-987-6543",
        "tier": "standard",
        "account_status": "active",
        "joined": "2025-06-01",
        "lifetime_value": 340.00,
        "subscription": None,
        "orders": [
            {"order_id": "ORD-2040", "date": "2026-06-10", "items": ["Mechanical Keyboard"], "total": 159.99, "status": "shipped", "tracking": "TRK-55401", "estimated_delivery": "2026-06-14"},
            {"order_id": "ORD-2041", "date": "2026-06-10", "items": ["Mouse Pad"], "total": 24.99, "status": "shipped", "tracking": "TRK-55401", "estimated_delivery": "2026-06-14"},
        ],
        "payments": [
            {"payment_id": "PAY-3040", "order_id": "ORD-2040", "amount": 159.99, "method": "apple_pay", "status": "completed", "date": "2026-06-10"},
            {"payment_id": "PAY-3041", "order_id": "ORD-2041", "amount": 24.99, "method": "apple_pay", "status": "completed", "date": "2026-06-10"},
        ],
        "tickets": [],
        "notes": [],
    },
    "CUST-1006": {
        "customer_id": "CUST-1006",
        "name": "Rajesh Kumar",
        "email": "rajesh.k@enterprise.in",
        "phone": "+91-88776-65544",
        "tier": "enterprise",
        "account_status": "active",
        "joined": "2021-01-15",
        "lifetime_value": 52300.00,
        "subscription": {"plan": "Enterprise Plus", "price": 4999.00, "renewal_date": "2027-01-15", "status": "active", "seats": 200},
        "orders": [
            {"order_id": "ORD-2050", "date": "2026-01-20", "items": ["200 Enterprise Licenses", "Priority Support", "Custom Integration"], "total": 15999.00, "status": "delivered", "tracking": None},
            {"order_id": "ORD-2051", "date": "2026-04-15", "items": ["50 Additional Seats"], "total": 2499.50, "status": "delivered", "tracking": None},
            {"order_id": "ORD-2052", "date": "2026-06-01", "items": ["API Access Tier 3"], "total": 999.00, "status": "processing", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3050", "order_id": "ORD-2050", "amount": 15999.00, "method": "wire_transfer", "status": "completed", "date": "2026-01-20"},
            {"payment_id": "PAY-3051", "order_id": "ORD-2051", "amount": 2499.50, "method": "wire_transfer", "status": "completed", "date": "2026-04-15"},
            {"payment_id": "PAY-3052", "order_id": "ORD-2052", "amount": 999.00, "method": "invoice", "status": "pending", "date": "2026-06-01"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4030", "date": "2026-03-01", "subject": "Integration not working", "status": "resolved", "resolution": "API key regenerated"},
        ],
        "notes": ["Top 5 enterprise account", "Dedicated team: Sunita + Arjun", "Custom SLA: 1hr response time"],
    },
    "CUST-1007": {
        "customer_id": "CUST-1007",
        "name": "Emily Rodriguez",
        "email": "emily.r@design.co",
        "phone": "+1-555-234-5678",
        "tier": "premium",
        "account_status": "active",
        "joined": "2023-07-20",
        "lifetime_value": 2100.00,
        "subscription": {"plan": "Creative Pro", "price": 29.99, "renewal_date": "2026-07-20", "status": "active"},
        "orders": [
            {"order_id": "ORD-2060", "date": "2026-05-30", "items": ["Design Software License", "Plugin Pack"], "total": 249.98, "status": "delivered", "tracking": None},
        ],
        "payments": [
            {"payment_id": "PAY-3060", "order_id": "ORD-2060", "amount": 249.98, "method": "credit_card", "card_last4": "7788", "status": "completed", "date": "2026-05-30"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4040", "date": "2026-06-05", "subject": "Plugin crashes on launch", "status": "open"},
            {"ticket_id": "TKT-4041", "date": "2026-06-08", "subject": "License activation issue", "status": "open"},
        ],
        "notes": ["Experiencing multiple issues — frustration rising", "Has been a loyal customer for 3 years"],
    },
    "CUST-1008": {
        "customer_id": "CUST-1008",
        "name": "Yuki Tanaka",
        "email": "yuki.t@corp.jp",
        "phone": "+81-90-1234-5678",
        "tier": "standard",
        "account_status": "active",
        "joined": "2025-12-01",
        "lifetime_value": 599.00,
        "subscription": {"plan": "Basic Monthly", "price": 9.99, "renewal_date": "2026-07-01", "status": "active"},
        "orders": [
            {"order_id": "ORD-2070", "date": "2026-05-15", "items": ["Portable Monitor"], "total": 349.99, "status": "returned", "tracking": None, "return_reason": "Defective screen"},
            {"order_id": "ORD-2071", "date": "2026-06-01", "items": ["Replacement Monitor"], "total": 349.99, "status": "shipped", "tracking": "TRK-33101", "estimated_delivery": "2026-06-13"},
        ],
        "payments": [
            {"payment_id": "PAY-3070", "order_id": "ORD-2070", "amount": 349.99, "method": "credit_card", "card_last4": "3344", "status": "refunded", "date": "2026-05-20"},
            {"payment_id": "PAY-3071", "order_id": "ORD-2071", "amount": 349.99, "method": "credit_card", "card_last4": "3344", "status": "completed", "date": "2026-06-01"},
        ],
        "tickets": [
            {"ticket_id": "TKT-4050", "date": "2026-05-16", "subject": "Monitor has dead pixels", "status": "resolved", "resolution": "Return accepted, replacement shipped"},
        ],
        "notes": [],
    },
}

_SEED_PRODUCTS: dict[str, dict[str, Any]] = {
    "Premium Headphones": {"sku": "SKU-HP-001", "price": 149.99, "category": "Audio", "warranty_months": 24, "return_policy_days": 30},
    "USB-C Cable": {"sku": "SKU-CB-001", "price": 14.99, "category": "Accessories", "warranty_months": 12, "return_policy_days": 15},
    "Wireless Charger": {"sku": "SKU-WC-001", "price": 49.99, "category": "Accessories", "warranty_months": 12, "return_policy_days": 30},
    "Laptop Stand": {"sku": "SKU-LS-001", "price": 79.99, "category": "Ergonomics", "warranty_months": 36, "return_policy_days": 30},
    "Bluetooth Speaker": {"sku": "SKU-BS-001", "price": 129.99, "category": "Audio", "warranty_months": 24, "return_policy_days": 30},
    "Smart Watch": {"sku": "SKU-SW-001", "price": 299.99, "category": "Wearables", "warranty_months": 12, "return_policy_days": 14},
    "Mechanical Keyboard": {"sku": "SKU-MK-001", "price": 159.99, "category": "Input", "warranty_months": 36, "return_policy_days": 30},
    "Mouse Pad": {"sku": "SKU-MP-001", "price": 24.99, "category": "Accessories", "warranty_months": 6, "return_policy_days": 15},
    "Portable Monitor": {"sku": "SKU-PM-001", "price": 349.99, "category": "Displays", "warranty_months": 24, "return_policy_days": 30},
    "Design Software License": {"sku": "SKU-DL-001", "price": 199.99, "category": "Software", "warranty_months": 0, "return_policy_days": 30},
    "Plugin Pack": {"sku": "SKU-PP-001", "price": 49.99, "category": "Software", "warranty_months": 0, "return_policy_days": 30},
    "Cloud Storage 1TB": {"sku": "SKU-CS-001", "price": 99.99, "category": "Cloud", "warranty_months": 0, "return_policy_days": 0},
}

_SEED_FAQS: dict[str, dict[str, str]] = {
    "refund_policy": {
        "id": "refund_policy",
        "question": "What is your refund policy?",
        "answer": "Full refunds are available within 30 days of purchase for all physical products. Software/digital products can be refunded within 14 days if not activated. Duplicate charges are refunded immediately. Refunds take 3-5 business days to appear on your statement.",
    },
    "shipping_policy": {
        "id": "shipping_policy",
        "question": "What are the shipping options and timelines?",
        "answer": "Standard shipping: 5-7 business days (free over $50). Express: 2-3 business days ($9.99). Overnight: next business day ($19.99). International: 7-14 business days ($14.99+). Tracking provided for all orders.",
    },
    "return_policy": {
        "id": "return_policy",
        "question": "How do I return an item?",
        "answer": "Initiate a return within the return window (varies by product, typically 14-30 days). Item must be in original condition. Print a return label from your account or request one from support. Refund issued after item is received and inspected.",
    },
    "cancellation_policy": {
        "id": "cancellation_policy",
        "question": "Can I cancel my order?",
        "answer": "Orders can be cancelled before they ship (usually within 2 hours of placing the order). After shipping, a return must be initiated instead. Subscription cancellations take effect at the end of the current billing period.",
    },
    "account_security": {
        "id": "account_security",
        "question": "How do I secure my account?",
        "answer": "Enable two-factor authentication in Account Settings. Use a strong, unique password. We never ask for your password via email. If you suspect unauthorized access, contact support immediately and change your password.",
    },
    "subscription_faq": {
        "id": "subscription_faq",
        "question": "How do subscriptions work?",
        "answer": "Subscriptions auto-renew at the end of each billing period. You can cancel anytime. Annual plans offer a 20% discount. Upgrades take effect immediately; downgrades take effect at next renewal.",
    },
    "warranty_faq": {
        "id": "warranty_faq",
        "question": "What does the warranty cover?",
        "answer": "Warranties cover manufacturing defects and hardware failures under normal use. Does not cover accidental damage, misuse, or normal wear. File a warranty claim through support with your order number.",
    },
    "enterprise_support": {
        "id": "enterprise_support",
        "question": "What support options are available for enterprise?",
        "answer": "Enterprise accounts get: dedicated account manager, priority support (1-hour response SLA), custom integrations, bulk licensing, and quarterly business reviews. Contact your account manager or enterprise-support@company.com.",
    },
}

_SEED_KNOWLEDGE_BASE: list[dict[str, str]] = [
    {"id": "KB-001", "title": "Duplicate Charge Resolution", "content": "When a customer reports a duplicate charge: 1) Verify in payment records — look for same amount on same date. 2) If confirmed, process immediate refund for the duplicate. 3) Send confirmation email with refund timeline. 4) No need for customer to provide evidence — CRM data is sufficient."},
    {"id": "KB-002", "title": "Failed Payment Recovery", "content": "When a payment fails: 1) Check card details and try again after 24 hours. 2) If card declined 3+ times, suspend account and notify customer. 3) Offer alternative payment methods. 4) For subscriptions, provide 7-day grace period before suspension. 5) Enterprise accounts: contact account manager before any suspension."},
    {"id": "KB-003", "title": "Order Cancellation Procedure", "content": "To cancel an order: 1) Check if order has shipped — if not, cancel immediately and refund. 2) If shipped, customer must initiate return. 3) For digital products, check if license has been activated — unactivated licenses can be cancelled. 4) Enterprise bulk orders require account manager approval for cancellation."},
    {"id": "KB-004", "title": "Account Suspension Policy", "content": "Account suspension triggers: Failed payment (3+ attempts), Terms of Service violation, or customer request. Process: 1) Notify customer 48 hours before suspension. 2) Provide grace period for payment issues. 3) Suspend access but retain data for 90 days. 4) After 90 days, data may be permanently deleted. 5) Reactivation: resolve the issue and request reactivation through support."},
    {"id": "KB-005", "title": "Shipping Delay Compensation", "content": "If shipping is delayed beyond estimated delivery: 1) Apologize and provide updated tracking. 2) For delays of 3+ days, offer $10 store credit. 3) For delays of 7+ days, offer free express shipping on next order. 4) For perishable or time-sensitive items, offer full refund or replacement. 5) Enterprise: honor SLA penalties as per contract."},
    {"id": "KB-006", "title": "Defective Product Handling", "content": "For defective products: 1) Offer immediate replacement or full refund — customer's choice. 2) No need to return defective item for items under $50. 3) For items over $50, provide prepaid return label. 4) If replacement is out of stock, offer upgrade at no extra cost. 5) File warranty claim if within warranty period."},
    {"id": "KB-007", "title": "Subscription Change and Cancellation", "content": "Subscription changes: Upgrades take effect immediately with prorated billing. Downgrades take effect at next renewal. Cancellation: Effective at end of current period, no partial refunds for annual plans. Enterprise: Custom terms per contract — always consult account manager."},
    {"id": "KB-008", "title": "Escalation Triggers", "content": "Escalate to human agent when: 1) Legal threat or attorney mention. 2) Customer explicitly requests manager. 3) Issue involves more than $500. 4) Customer has had 3+ unresolved tickets. 5) Enterprise account with SLA requirements. 6) Security breach or data concern. 7) Any situation where AI confidence is below 0.5."},
    {"id": "KB-009", "title": "VIP Customer Protocol", "content": "For premium/enterprise customers: 1) Priority response within 1 hour. 2) Offer goodwill gestures proactively (discounts, credits). 3) Never suspend without account manager approval. 4) Provide direct contact for their dedicated support. 5) Consider LTV when making decisions — high-LTV customers get more flexibility."},
    {"id": "KB-010", "title": "Multi-Issue Ticket Handling", "content": "When a customer has multiple issues: 1) Address each issue separately in the reasoning chain. 2) Create an action plan for each issue. 3) Prioritize by urgency (payment issues > access issues > general questions). 4) Consider connections between issues (e.g., failed payment caused account suspension). 5) Resolve root causes, not just symptoms."},
]


class FakeCRM:
    """In-memory CRM with full business operations.

    Thread-safe. Supports: customer lookup, order management,
    payment processing, refunds, cancellations, account modifications,
    note creation, and FAQ/KB retrieval.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._customers: dict[str, dict[str, Any]] = {}
        self._products: dict[str, dict[str, Any]] = {}
        self._faqs: dict[str, dict[str, str]] = {}
        self._kb: list[dict[str, str]] = []
        self._audit_log: list[dict[str, Any]] = []
        self._action_log: list[dict[str, Any]] = []
        self._reset_to_seed()

    def _reset_to_seed(self) -> None:
        """Reset all data to seed values."""
        self._customers = copy.deepcopy(_SEED_CUSTOMERS)
        self._products = copy.deepcopy(_SEED_PRODUCTS)
        self._faqs = copy.deepcopy(_SEED_FAQS)
        self._kb = copy.deepcopy(_SEED_KNOWLEDGE_BASE)
        self._audit_log = []
        self._action_log = []

    # ─── Customer Operations ────────────────────────────────────────────────

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Look up a customer by ID. Returns None if not found."""
        with self._lock:
            return copy.deepcopy(self._customers.get(customer_id))

    def get_customer_by_email(self, email: str) -> dict[str, Any] | None:
        """Look up a customer by email."""
        with self._lock:
            for cust in self._customers.values():
                if cust.get("email", "").lower() == email.lower():
                    return copy.deepcopy(cust)
        return None

    def get_customer_by_name(self, name: str) -> list[dict[str, Any]]:
        """Search customers by name (partial match)."""
        results = []
        name_lower = name.lower()
        with self._lock:
            for cust in self._customers.values():
                if name_lower in cust.get("name", "").lower():
                    results.append(copy.deepcopy(cust))
        return results

    def update_customer(self, customer_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update customer fields. Returns updated customer or raises."""
        with self._lock:
            if customer_id not in self._customers:
                raise ValueError(f"Customer {customer_id} not found")
            cust = self._customers[customer_id]
            for k, v in updates.items():
                if k != "customer_id":  # don't allow changing ID
                    cust[k] = v
            self._log_action("update_customer", {"customer_id": customer_id, "updates": updates})
            return copy.deepcopy(cust)

    # ─── Order Operations ───────────────────────────────────────────────────

    def get_order(self, customer_id: str, order_id: str) -> dict[str, Any] | None:
        """Get a specific order for a customer."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                return None
            for order in cust.get("orders", []):
                if order.get("order_id") == order_id:
                    return copy.deepcopy(order)
        return None

    def get_orders(self, customer_id: str) -> list[dict[str, Any]]:
        """Get all orders for a customer."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                return []
            return copy.deepcopy(cust.get("orders", []))

    def cancel_order(self, customer_id: str, order_id: str, reason: str = "") -> dict[str, Any]:
        """Cancel an order. Returns updated order or raises."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")
            for order in cust.get("orders", []):
                if order.get("order_id") == order_id:
                    if order.get("status") in ("cancelled",):
                        return {"status": "already_cancelled", "order_id": order_id}
                    if order.get("status") in ("delivered", "returned"):
                        return {"status": "cannot_cancel", "reason": f"Order already {order['status']}. Initiate a return instead."}
                    order["status"] = "cancelled"
                    order["cancellation_reason"] = reason
                    order["cancelled_at"] = datetime.utcnow().isoformat()
                    self._log_action("cancel_order", {"customer_id": customer_id, "order_id": order_id, "reason": reason})
                    return copy.deepcopy(order)
            raise ValueError(f"Order {order_id} not found for customer {customer_id}")

    def get_order_status(self, customer_id: str, order_id: str) -> dict[str, Any]:
        """Get order status with tracking info."""
        order = self.get_order(customer_id, order_id)
        if not order:
            return {"found": False, "error": "Order not found"}
        return {
            "found": True,
            "order_id": order.get("order_id"),
            "status": order.get("status"),
            "tracking": order.get("tracking"),
            "estimated_delivery": order.get("estimated_delivery"),
            "items": order.get("items", []),
            "total": order.get("total"),
        }

    # ─── Payment Operations ─────────────────────────────────────────────────

    def get_payments(self, customer_id: str) -> list[dict[str, Any]]:
        """Get all payments for a customer."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                return []
            return copy.deepcopy(cust.get("payments", []))

    def find_duplicate_payments(self, customer_id: str) -> list[list[dict[str, Any]]]:
        """Find duplicate payments (same amount, same date, same order)."""
        payments = self.get_payments(customer_id)
        duplicates = []
        seen: dict[str, list[dict]] = {}
        for p in payments:
            if p.get("status") != "completed":
                continue
            key = f"{p.get('order_id')}|{p.get('amount')}|{p.get('date')}"
            if key not in seen:
                seen[key] = []
            seen[key].append(p)
        for key, group in seen.items():
            if len(group) > 1:
                duplicates.append(group)
        return duplicates

    def process_refund(self, customer_id: str, payment_id: str, amount: float, reason: str = "") -> dict[str, Any]:
        """Process a refund against a payment. Actually modifies payment status."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")

            for payment in cust.get("payments", []):
                if payment.get("payment_id") == payment_id:
                    if payment.get("status") == "refunded":
                        return {"status": "already_refunded", "payment_id": payment_id, "amount": payment.get("amount")}
                    if amount > payment.get("amount", 0):
                        return {"status": "error", "reason": f"Refund amount ${amount} exceeds payment amount ${payment.get('amount', 0)}"}

                    payment["status"] = "refunded"
                    payment["refunded_amount"] = amount
                    payment["refunded_at"] = datetime.utcnow().isoformat()
                    payment["refund_reason"] = reason

                    # Update customer lifetime value
                    cust["lifetime_value"] = cust.get("lifetime_value", 0) - amount

                    refund_id = f"REF-{uuid.uuid4().hex[:6].upper()}"
                    self._log_action("process_refund", {
                        "customer_id": customer_id, "payment_id": payment_id,
                        "refund_id": refund_id, "amount": amount, "reason": reason,
                    })
                    return {
                        "status": "refunded",
                        "refund_id": refund_id,
                        "amount": amount,
                        "payment_id": payment_id,
                        "message": f"Refund of ${amount:.2f} processed. Refund ID: {refund_id}. Will appear in 3-5 business days.",
                    }

            raise ValueError(f"Payment {payment_id} not found for customer {customer_id}")

    # ─── Account Operations ─────────────────────────────────────────────────

    def modify_account(self, customer_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Modify account settings. Supports: email change, plan change, add/remove seats, etc."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")

            results = []
            for field, value in changes.items():
                if field == "email":
                    old = cust.get("email")
                    cust["email"] = value
                    results.append(f"Email updated from {old} to {value}")
                elif field == "phone":
                    old = cust.get("phone")
                    cust["phone"] = value
                    results.append(f"Phone updated from {old} to {value}")
                elif field == "plan" and cust.get("subscription"):
                    old_plan = cust["subscription"].get("plan")
                    cust["subscription"]["plan"] = value
                    results.append(f"Subscription plan changed from {old_plan} to {value}")
                elif field == "add_seats" and cust.get("subscription"):
                    current = cust["subscription"].get("seats", 0)
                    cust["subscription"]["seats"] = current + value
                    results.append(f"Added {value} seats (now {current + value} total)")
                elif field == "reactivate":
                    cust["account_status"] = "active"
                    if cust.get("subscription"):
                        cust["subscription"]["status"] = "active"
                    results.append("Account reactivated")
                elif field == "reset_password":
                    results.append("Password reset link sent to registered email")
                else:
                    results.append(f"Field '{field}' updated to {value}")

            self._log_action("modify_account", {"customer_id": customer_id, "changes": changes, "results": results})
            return {"status": "modified", "customer_id": customer_id, "changes_made": results}

    def suspend_account(self, customer_id: str, reason: str = "") -> dict[str, Any]:
        """Suspend an account."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")
            cust["account_status"] = "suspended"
            if cust.get("subscription"):
                cust["subscription"]["status"] = "suspended"
            self._log_action("suspend_account", {"customer_id": customer_id, "reason": reason})
            return {"status": "suspended", "customer_id": customer_id}

    def reactivate_account(self, customer_id: str) -> dict[str, Any]:
        """Reactivate a suspended account."""
        return self.modify_account(customer_id, {"reactivate": True})

    # ─── Notes & Tickets ────────────────────────────────────────────────────

    def add_note(self, customer_id: str, note: str) -> dict[str, Any]:
        """Add a note to a customer's record."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")
            if "notes" not in cust:
                cust["notes"] = []
            cust["notes"].append(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {note}")
            self._log_action("add_note", {"customer_id": customer_id, "note": note})
            return {"status": "note_added", "customer_id": customer_id}

    def create_ticket(self, customer_id: str, subject: str) -> dict[str, Any]:
        """Create a new support ticket in the CRM."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")
            ticket_id = f"TKT-{uuid.uuid4().hex[:4].upper()}"
            ticket = {
                "ticket_id": ticket_id,
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "subject": subject,
                "status": "open",
            }
            if "tickets" not in cust:
                cust["tickets"] = []
            cust["tickets"].append(ticket)
            self._log_action("create_ticket", {"customer_id": customer_id, "ticket_id": ticket_id, "subject": subject})
            return ticket

    def resolve_ticket(self, customer_id: str, ticket_id: str, resolution: str) -> dict[str, Any]:
        """Mark a ticket as resolved."""
        with self._lock:
            cust = self._customers.get(customer_id)
            if not cust:
                raise ValueError(f"Customer {customer_id} not found")
            for ticket in cust.get("tickets", []):
                if ticket.get("ticket_id") == ticket_id:
                    ticket["status"] = "resolved"
                    ticket["resolution"] = resolution
                    ticket["resolved_at"] = datetime.utcnow().isoformat()
                    self._log_action("resolve_ticket", {"customer_id": customer_id, "ticket_id": ticket_id})
                    return copy.deepcopy(ticket)
            raise ValueError(f"Ticket {ticket_id} not found for customer {customer_id}")

    # ─── FAQ & KB ───────────────────────────────────────────────────────────

    def search_faqs(self, query: str, top_k: int = 3) -> list[dict[str, str]]:
        """Search FAQs by keyword matching (simulates semantic search)."""
        query_lower = query.lower()
        scored = []
        for faq_id, faq in self._faqs.items():
            score = 0.0
            # Check question match
            if query_lower in faq.get("question", "").lower():
                score += 0.5
            # Check answer keywords
            answer_lower = faq.get("answer", "").lower()
            for word in query_lower.split():
                if len(word) > 3 and word in answer_lower:
                    score += 0.1
            # Specific keyword boosts
            if "refund" in query_lower and "refund" in faq_id:
                score += 0.3
            elif "ship" in query_lower and "ship" in faq_id:
                score += 0.3
            elif "cancel" in query_lower and "cancel" in faq_id:
                score += 0.3
            elif "return" in query_lower and "return" in faq_id:
                score += 0.3
            elif "account" in query_lower and "account" in faq_id:
                score += 0.3
            elif "subscription" in query_lower and "subscription" in faq_id:
                score += 0.3
            elif "warranty" in query_lower and "warranty" in faq_id:
                score += 0.3
            elif "enterprise" in query_lower and "enterprise" in faq_id:
                score += 0.3

            if score > 0.1:
                scored.append({"relevance_score": min(1.0, score), **faq})

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def search_kb(self, query: str, top_k: int = 3) -> list[dict[str, str]]:
        """Search knowledge base by keyword matching."""
        query_lower = query.lower()
        scored = []
        for article in self._kb:
            score = 0.0
            title_lower = article.get("title", "").lower()
            content_lower = article.get("content", "").lower()
            for word in query_lower.split():
                if len(word) > 3 and word in title_lower:
                    score += 0.3
                if len(word) > 3 and word in content_lower:
                    score += 0.1
            if score > 0.1:
                scored.append({"relevance_score": min(1.0, score), **article})

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    # ─── Product Info ───────────────────────────────────────────────────────

    def get_product(self, product_name: str) -> dict[str, Any] | None:
        """Get product information by name."""
        return copy.deepcopy(self._products.get(product_name))

    # ─── Audit & Logging ────────────────────────────────────────────────────

    def get_action_log(self) -> list[dict[str, Any]]:
        """Get the log of all actions performed on the CRM."""
        with self._lock:
            return copy.deepcopy(self._action_log)

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get the audit log."""
        with self._lock:
            return copy.deepcopy(self._audit_log)

    def _log_action(self, action: str, details: dict[str, Any]) -> None:
        """Log an action to the CRM action log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details,
        }
        self._action_log.append(entry)

    # ─── Data Export (for debugging) ────────────────────────────────────────

    def export_customer_summary(self, customer_id: str) -> dict[str, Any]:
        """Export a summary of customer data for the pipeline."""
        cust = self.get_customer(customer_id)
        if not cust:
            return {"found": False, "customer_id": customer_id}

        return {
            "found": True,
            "customer_id": cust.get("customer_id"),
            "name": cust.get("name"),
            "email": cust.get("email"),
            "tier": cust.get("tier"),
            "account_status": cust.get("account_status"),
            "lifetime_value": cust.get("lifetime_value"),
            "subscription": cust.get("subscription"),
            "orders": cust.get("orders", []),
            "payments": cust.get("payments", []),
            "open_tickets": [t for t in cust.get("tickets", []) if t.get("status") == "open"],
            "notes": cust.get("notes", []),
        }


# ─── Singleton ──────────────────────────────────────────────────────────────

_crm_instance: FakeCRM | None = None
_crm_lock = threading.Lock()


def get_crm() -> FakeCRM:
    """Get the singleton FakeCRM instance."""
    global _crm_instance
    if _crm_instance is None:
        with _crm_lock:
            if _crm_instance is None:
                _crm_instance = FakeCRM()
    return _crm_instance


def reset_crm() -> FakeCRM:
    """Reset the CRM to seed data and return the fresh instance."""
    global _crm_instance
    with _crm_lock:
        _crm_instance = FakeCRM()
    return _crm_instance
