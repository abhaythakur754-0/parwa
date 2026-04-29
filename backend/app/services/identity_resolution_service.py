"""
PARWA Identity Resolution Service - Cross-Channel Customer Matching (Day 30)

Implements F-070: Identity resolution with:
- Match by email (exact + fuzzy)
- Match by phone (exact)
- Match by social_id (exact)
- Confidence scoring
- PS14: Grandfathered tickets support

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.services.customer_service import CustomerService
from database.models.tickets import (
    Customer,
    IdentityMatchLog,
    Ticket,
)


class IdentityResolutionService:
    """Cross-channel customer identity resolution."""

    # Confidence scores for different match types
    CONFIDENCE_EMAIL = 0.9
    CONFIDENCE_EMAIL_FUZZY = 0.7
    CONFIDENCE_PHONE = 0.8
    CONFIDENCE_SOCIAL = 0.7
    CONFIDENCE_DEVICE = 0.5

    # Minimum confidence to auto-link
    AUTO_LINK_THRESHOLD = 0.85

    # Fuzzy match threshold for emails
    FUZZY_EMAIL_THRESHOLD = 0.85

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self.customer_service = CustomerService(db, company_id)

    # ── IDENTITY RESOLUTION ─────────────────────────────────────────────────

    def resolve_identity(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        social_id: Optional[str] = None,
        device_id: Optional[str] = None,
        auto_create: bool = True,
        auto_link_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Resolve customer identity from multiple identifiers.

        Tries to match existing customer by any provided identifier.
        Creates new customer if no match and auto_create is True.

        Args:
            email: Email address to match
            phone: Phone number to match
            social_id: Social media identifier
            device_id: Device fingerprint
            auto_create: Create new customer if no match
            auto_link_threshold: Confidence threshold for auto-linking

        Returns:
            Dict with matched_customer_id, match_method, confidence, action_taken
        """
        threshold = auto_link_threshold or self.AUTO_LINK_THRESHOLD

        # Try exact matches first (highest confidence)
        matches = []

        if email:
            match = self._match_by_email(email)
            if match:
                matches.append(match)

        if phone:
            match = self._match_by_phone(phone)
            if match:
                matches.append(match)

        if social_id:
            match = self._match_by_social_id(social_id)
            if match:
                matches.append(match)

        if device_id:
            match = self._match_by_device_id(device_id)
            if match:
                matches.append(match)

        # Log the resolution attempt
        log_entry = self._log_resolution_attempt(
            email=email,
            phone=phone,
            matches=matches,
        )

        # Determine best match
        if matches:
            best_match = max(matches, key=lambda m: m["confidence"])

            # If confidence is high enough, return the match
            if best_match["confidence"] >= threshold:
                log_entry.matched_customer_id = best_match["customer_id"]
                log_entry.match_method = best_match["method"]
                log_entry.confidence_score = best_match["confidence"]
                log_entry.action_taken = "matched"
                self.db.commit()

                return {
                    "matched_customer_id": best_match["customer_id"],
                    "match_method": best_match["method"],
                    "confidence_score": best_match["confidence"],
                    "action_taken": "linked",
                }

            # Lower confidence - suggest merge
            log_entry.matched_customer_id = best_match["customer_id"]
            log_entry.match_method = best_match["method"]
            log_entry.confidence_score = best_match["confidence"]
            log_entry.action_taken = "suggested"
            self.db.commit()

            return {
                "matched_customer_id": best_match["customer_id"],
                "match_method": best_match["method"],
                "confidence_score": best_match["confidence"],
                "action_taken": "suggested",
            }

        # No match found - create new customer if auto_create
        if auto_create:
            customer = self.customer_service.create_customer(
                email=email,
                phone=phone,
            )

            log_entry.matched_customer_id = customer.id
            log_entry.match_method = "none"
            log_entry.confidence_score = 0.0
            log_entry.action_taken = "created"
            self.db.commit()

            return {
                "matched_customer_id": customer.id,
                "match_method": "none",
                "confidence_score": 0.0,
                "action_taken": "created",
            }

        # No match, no auto-create
        log_entry.match_method = "none"
        log_entry.confidence_score = 0.0
        log_entry.action_taken = "none"
        self.db.commit()

        return {
            "matched_customer_id": None,
            "match_method": "none",
            "confidence_score": 0.0,
            "action_taken": "none",
        }

    def _match_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Match customer by email (exact then fuzzy).

        Args:
            email: Email address to match

        Returns:
            Match dict or None
        """
        normalized = email.strip().lower()

        # Exact match
        customer = self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
            func.lower(Customer.email) == normalized,
        ).first()

        if customer:
            return {
                "customer_id": customer.id,
                "method": "email",
                "confidence": self.CONFIDENCE_EMAIL,
            }

        # Fuzzy match on email
        customers = self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
            Customer.email.isnot(None),
        ).all()

        for c in customers:
            if c.email:
                similarity = SequenceMatcher(
                    None, normalized, c.email.lower()
                ).ratio()

                if similarity >= self.FUZZY_EMAIL_THRESHOLD:
                    return {
                        "customer_id": c.id,
                        "method": "email_fuzzy",
                        "confidence": self.CONFIDENCE_EMAIL_FUZZY * similarity,
                    }

        return None

    def _match_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Match customer by phone (exact only).

        Args:
            phone: Phone number to match

        Returns:
            Match dict or None
        """
        normalized = self._normalize_phone(phone)

        customer = self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
            Customer.phone == normalized,
        ).first()

        if customer:
            return {
                "customer_id": customer.id,
                "method": "phone",
                "confidence": self.CONFIDENCE_PHONE,
            }

        return None

    def _match_by_social_id(self, social_id: str) -> Optional[Dict[str, Any]]:
        """Match customer by social media ID via CustomerChannel.

        Args:
            social_id: Social media identifier

        Returns:
            Match dict or None
        """
        # Social media channels have been removed; this method is kept
        # for backward compatibility but will not match any records.
        return None

    def _match_by_device_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Match customer by device fingerprint.

        Args:
            device_id: Device fingerprint

        Returns:
            Match dict or None
        """
        # Device IDs are stored in customer metadata
        customers = self.db.query(Customer).filter(
            Customer.company_id == self.company_id,
        ).all()

        for customer in customers:
            metadata = json.loads(customer.metadata_json or "{}")
            device_ids = metadata.get("device_ids", [])

            if device_id in device_ids:
                return {
                    "customer_id": customer.id,
                    "method": "device",
                    "confidence": self.CONFIDENCE_DEVICE,
                }

        return None

    def _log_resolution_attempt(
        self,
        email: Optional[str],
        phone: Optional[str],
        matches: List[Dict[str, Any]],
    ) -> IdentityMatchLog:
        """Log the resolution attempt.

        Args:
            email: Input email
            phone: Input phone
            matches: List of matches found

        Returns:
            IdentityMatchLog entry
        """
        log_entry = IdentityMatchLog(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            input_email=email,
            input_phone=phone,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(log_entry)
        self.db.flush()

        return log_entry

    # ── DUPLICATE DETECTION ─────────────────────────────────────────────────

    def find_potential_duplicates(
        self,
        customer_id: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Find potential duplicate customers.

        Args:
            customer_id: Check duplicates for specific customer (None for all)
            min_confidence: Minimum confidence threshold

        Returns:
            List of potential duplicate pairs
        """
        duplicates = []

        if customer_id:
            customers = [self.customer_service.get_customer(customer_id)]
        else:
            customers = self.db.query(Customer).filter(
                Customer.company_id == self.company_id,
            ).all()

        for i, c1 in enumerate(customers):
            for c2 in customers[i + 1:]:
                confidence, method = self._calculate_duplicate_confidence(
                    c1, c2)

                if confidence >= min_confidence:
                    duplicates.append({
                        "customer_1_id": c1.id,
                        "customer_1_email": c1.email,
                        "customer_1_phone": c1.phone,
                        "customer_1_name": c1.name,
                        "customer_2_id": c2.id,
                        "customer_2_email": c2.email,
                        "customer_2_phone": c2.phone,
                        "customer_2_name": c2.name,
                        "confidence": confidence,
                        "match_method": method,
                    })

        return sorted(duplicates, key=lambda d: d["confidence"], reverse=True)

    def _calculate_duplicate_confidence(
        self,
        c1: Customer,
        c2: Customer,
    ) -> Tuple[float, str]:
        """Calculate confidence that two customers are duplicates.

        Args:
            c1: First customer
            c2: Second customer

        Returns:
            Tuple of (confidence, method)
        """
        # Email match
        if c1.email and c2.email:
            if c1.email.lower() == c2.email.lower():
                return self.CONFIDENCE_EMAIL, "email_exact"

            similarity = SequenceMatcher(
                None, c1.email.lower(), c2.email.lower()
            ).ratio()

            if similarity >= self.FUZZY_EMAIL_THRESHOLD:
                return self.CONFIDENCE_EMAIL_FUZZY * similarity, "email_fuzzy"

        # Phone match
        if c1.phone and c2.phone:
            if self._normalize_phone(
                    c1.phone) == self._normalize_phone(
                    c2.phone):
                return self.CONFIDENCE_PHONE, "phone"

        # Name similarity (lower confidence)
        if c1.name and c2.name:
            name_similarity = SequenceMatcher(
                None, c1.name.lower(), c2.name.lower()
            ).ratio()

            if name_similarity >= 0.9:
                return 0.5 * name_similarity, "name"

        return 0.0, "none"

    # ── MATCH LOGS ──────────────────────────────────────────────────────────

    def get_match_logs(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[IdentityMatchLog], int]:
        """Get identity match logs.

        Args:
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (logs list, total count)
        """
        query = self.db.query(IdentityMatchLog).filter(
            IdentityMatchLog.company_id == self.company_id,
        )

        total = query.count()
        logs = query.order_by(desc(IdentityMatchLog.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return logs, total

    # ── PS14: GRANDFATHERED TICKETS ─────────────────────────────────────────

    def get_grandfathered_tickets(
        self,
        customer_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """PS14: Get tickets with grandfathered plan tiers.

        Open tickets retain the plan tier at creation time.
        This is stored in ticket.plan_snapshot.

        Args:
            customer_id: Filter by customer (optional)

        Returns:
            List of grandfathered tickets
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.plan_snapshot.isnot(None),
            Ticket.plan_snapshot != "{}",
        )

        if customer_id:
            query = query.filter(Ticket.customer_id == customer_id)

        tickets = query.all()

        result = []
        for ticket in tickets:
            plan_snapshot = json.loads(ticket.plan_snapshot or "{}")

            if plan_snapshot.get("grandfathered"):
                result.append({
                    "ticket_id": ticket.id,
                    "customer_id": ticket.customer_id,
                    "status": ticket.status,
                    "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                    "plan_tier": plan_snapshot.get("plan_tier"),
                    "grandfathered_since": plan_snapshot.get("grandfathered_since"),
                })

        return result

    def snapshot_plan_for_ticket(
        self,
        ticket: Ticket,
        plan_tier: str,
    ) -> None:
        """PS14: Snapshot plan tier for a ticket at creation.

        Args:
            ticket: Ticket object
            plan_tier: Current plan tier
        """
        plan_snapshot = {
            "plan_tier": plan_tier,
            "grandfathered": True,
            "grandfathered_since": datetime.now(timezone.utc).isoformat(),
        }

        ticket.plan_snapshot = json.dumps(plan_snapshot)

    # ── PRIVATE HELPERS ─────────────────────────────────────────────────────

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison."""
        return re.sub(r"[\s\-\(\)]", "", phone.strip())
