"""
OOO Detection Service — Week 13 Day 3 (F-122)

Detects Out-of-Office (OOO) auto-responder emails using:
1. Email header analysis (X-Auto-Response-Suppress, Auto-Submitted, etc.)
2. Subject line heuristics
3. Body pattern matching (common OOO phrases in 10+ languages)
4. Custom tenant detection rules (F-122)
5. Sender profile tracking (frequency analysis)
6. Confidence scoring (header=high, subject=medium, body=low)

When an OOO email is detected:
- Do NOT create a ticket (BC-006: avoid noise)
- Log the OOO event with classification and signals
- Update sender's OOO profile (ooo_until date)
- Update OOO detection log for analytics
- Pause AI follow-ups for the customer until OOO ends

Building Codes:
- BC-001: Multi-tenant isolation
- BC-006: Don't create tickets for auto-responders
- BC-010: GDPR — respect customer availability signals
- BC-012: Detection failure never blocks legitimate email processing
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session


logger = logging.getLogger("parwa.ooo_detection")

# ── Header-based OOO indicators (RFC 3834) ──────────────────────

OOO_HEADER_FIELDS = [
    "x-auto-response-suppress",
    "auto-submitted",
    "x-auto-reply",
    "x-noriday",
    "x-ms-exchange-organization-scl",
]

OOO_AUTO_SUBMITTED_VALUES = [
    "auto-replied", "auto-generated", "autoreplied",
]

OOO_X_AUTO_RESPONSE_VALUES = [
    "oo", "dr", "autoreply", "all",
]

# ── Body pattern matching ────────────────────────────────────────

# OOO patterns organized by language/category
OOO_BODY_PATTERNS = [
    # English
    re.compile(r"out\s+(of|o[fn])\s+(the\s+)?office", re.IGNORECASE),
    re.compile(r"OOO\s*:", re.IGNORECASE),
    re.compile(r"auto(?:-?)reply\s*:", re.IGNORECASE),
    re.compile(r"automatic\s+reply", re.IGNORECASE),
    re.compile(
        r"i(?:'m| am)\s+(away|out|on vacation|on leave|travelling)",
        re.IGNORECASE),
    re.compile(
        r"will\s+be\s+(away|out|unavailable|on vacation|on leave)",
        re.IGNORECASE),
    re.compile(r"return(?:ing)?\s+(on|to|by)\s+", re.IGNORECASE),
    re.compile(r"back\s+in\s+(the\s+)?office", re.IGNORECASE),
    re.compile(
        r"no\s+(longer|access|response)\s+(to\s+)?(?:email|mail)",
        re.IGNORECASE),
    re.compile(
        r"(?:thank|thanks)\s+for\s+(?:your|the)\s+(?:email|message)",
        re.IGNORECASE),
    re.compile(r"this\s+is\s+an\s+automated", re.IGNORECASE),
    re.compile(
        r"please\s+contact\s+(?:my|another)\s+(?:colleague|manager|coworker)",
        re.IGNORECASE),
    re.compile(r"limited\s+(?:internet|email)\s+access", re.IGNORECASE),
    re.compile(
        r"response\s+time\s+may\s+be\s+(?:delayed|slow)",
        re.IGNORECASE),
    # German
    re.compile(
        r"(?:abwesend|urlaubsabwesenheit|automatische(?:r|s)?\s+antwort)",
        re.IGNORECASE),
    re.compile(
        r"bin\s+(?:abwesend|im\s+urlaub|nicht\s+im\s+b(?:ü|ue)ro)",
        re.IGNORECASE),
    # French
    re.compile(
        r"(?:absence|absent|cong(?:é|e)|r(?:é|e)ponse\s+automatique)",
        re.IGNORECASE),
    re.compile(r"je\s+suis\s+(?:absent|en\s+cong(?:é|e))", re.IGNORECASE),
    # Spanish
    re.compile(
        r"(?:fuera\s+de|ausente|respuesta\s+autom(?:á|a)tica)",
        re.IGNORECASE),
    # Portuguese
    re.compile(
        r"(?:fora\s+do\s+escrit(?:ó|o)rio|resposta\s+autom(?:á|a)tica)",
        re.IGNORECASE),
    # Italian
    re.compile(
        r"(?:fuori\s+(?: dall'?|dall')?ufficio|risposta\s+automatica)",
        re.IGNORECASE),
    # Dutch
    re.compile(r"(?:afwezig|automatisch\s+antwoord)", re.IGNORECASE),
    # Japanese
    re.compile(r"(?:不在|自動返信|外出中)", re.IGNORECASE),
    # Chinese
    re.compile(r"(?:不在|自动回复|外出|休假)", re.IGNORECASE),
    # Arabic
    re.compile(r"(?:غير(?:\s+)?موجود|رد\s+تلقائي)", re.IGNORECASE),
]

# ── Subject patterns ─────────────────────────────────────────────

OOO_SUBJECT_PATTERNS = [
    re.compile(r"^auto(?:-?)reply\s*:", re.IGNORECASE),
    re.compile(r"^out\s+of\s+office", re.IGNORECASE),
    re.compile(r"^OOO\s*:", re.IGNORECASE),
    re.compile(r"^away\s*:", re.IGNORECASE),
    re.compile(r"^vacation\s+auto", re.IGNORECASE),
    re.compile(r"^autoreply\s*:", re.IGNORECASE),
]

# Minimum body length to check for OOO patterns (avoid false positives)
MIN_BODY_LENGTH_FOR_PATTERN_CHECK = 20

# Body detection: minimum pattern matches required (prevents false positives)
BODY_MIN_PATTERN_MATCHES = 2

# Confidence thresholds for body-only detection (BC-012)
BODY_CONFIDENCE_HIGH_THRESHOLD = 4   # 4+ patterns = high
BODY_CONFIDENCE_MEDIUM_THRESHOLD = 2  # 2-3 patterns = medium


class OOODetectionService:
    """Detects and handles Out-of-Office auto-responder emails.

    Usage:
        service = OOODetectionService(db)
        result = service.detect_ooo(email_data, company_id)
        if result["is_ooo"]:
            service.log_ooo_event(company_id, email_data, result)
            service.update_sender_profile(company_id, email_data, result)
    """

    def __init__(self, db: Session):
        self.db = db

    def detect_ooo(self, email_data: dict, company_id: str) -> dict:
        """Detect if an email is an Out-of-Office auto-response.

        Checks in order:
        1. RFC 3834 headers (X-Auto-Response-Suppress, Auto-Submitted)
        2. Subject line patterns
        3. Body text patterns (multi-language)
        4. Custom tenant rules (from ooo_detection_rules table)
        5. Sender profile (frequency analysis)

        Args:
            email_data: Dict with headers_json, subject, body_text, body_html,
                sender_email, message_id.
            company_id: Tenant company ID.

        Returns:
            Dict with:
            - is_ooo: bool
            - is_auto_reply: bool
            - type: str (ooo/auto_reply/cyclic/spam or None)
            - reason: str (why it was detected)
            - detection_source: str (header/subject/body/rule/sender_profile)
            - ooo_until: Optional[str] (ISO date if extracted)
            - confidence: str (high/medium/low)
            - detected_signals: list[str]
            - rule_ids_matched: list[str]
        """
        detected_signals = []
        rule_ids_matched = []

        # Parse headers
        headers_str = email_data.get("headers_json", "")
        headers = {}
        if headers_str:
            try:
                headers = json.loads(headers_str) if isinstance(
                    headers_str, str) else headers_str
            except (json.JSONDecodeError, TypeError):
                pass

        # Step 1: Check headers (highest confidence)
        header_result = self._check_headers(headers)
        if header_result["is_ooo"]:
            header_result["type"] = "auto_reply"
            header_result["is_auto_reply"] = True
            detected_signals.append(
                f"header:{
                    header_result.get(
                        'reason', '')[
                        :50]}")
            ooo_until = self._extract_return_date(
                email_data.get(
                    "body_text", "") or email_data.get(
                    "body_html", ""), )
            header_result["ooo_until"] = ooo_until
            header_result["detected_signals"] = detected_signals
            header_result["rule_ids_matched"] = rule_ids_matched
            return header_result

        # Step 2: Check subject line (medium confidence)
        subject = email_data.get("subject", "")
        subject_result = self._check_subject(subject)
        if subject_result["is_ooo"]:
            subject_result["type"] = "auto_reply"
            subject_result["is_auto_reply"] = True
            detected_signals.append(
                f"subject:{
                    subject_result.get(
                        'reason', '')[
                        :50]}")
            ooo_until = self._extract_return_date(
                email_data.get(
                    "body_text", "") or email_data.get(
                    "body_html", ""), )
            subject_result["ooo_until"] = ooo_until
            subject_result["detected_signals"] = detected_signals
            subject_result["rule_ids_matched"] = rule_ids_matched
            return subject_result

        # Step 3: Check body (medium-low confidence — needs 2+ pattern matches)
        body = email_data.get("body_text", "") or ""
        body_result = self._check_body(body)
        if body_result["is_ooo"]:
            body_result["type"] = "ooo"
            body_result["is_auto_reply"] = True
            detected_signals.append(
                f"body:{
                    body_result.get(
                        'reason', '')[
                        :50]}")
            ooo_until = self._extract_return_date(
                email_data.get(
                    "body_text", "") or email_data.get(
                    "body_html", ""), )
            body_result["ooo_until"] = ooo_until
            body_result["detected_signals"] = detected_signals
            body_result["rule_ids_matched"] = rule_ids_matched
            return body_result

        # Step 4: Check custom tenant rules (F-122)
        custom_result = self._check_custom_rules(company_id, email_data)
        if custom_result["is_ooo"]:
            detected_signals.extend(custom_result.get("detected_signals", []))
            rule_ids_matched.extend(custom_result.get("rule_ids_matched", []))
            ooo_until = self._extract_return_date(
                email_data.get(
                    "body_text", "") or email_data.get(
                    "body_html", ""), )
            custom_result["ooo_until"] = ooo_until
            custom_result["detected_signals"] = detected_signals
            custom_result["rule_ids_matched"] = rule_ids_matched
            return custom_result

        # Step 5: Check sender profile (frequency analysis)
        sender_email = email_data.get("sender_email", "")
        if sender_email:
            profile_result = self._check_sender_profile(
                company_id, sender_email)
            if profile_result["is_ooo"]:
                profile_result["detected_signals"] = detected_signals
                profile_result["rule_ids_matched"] = rule_ids_matched
                return profile_result

        return {
            "is_ooo": False,
            "is_auto_reply": False,
            "type": None,
            "reason": None,
            "detection_source": None,
            "ooo_until": None,
            "confidence": None,
            "detected_signals": detected_signals,
            "rule_ids_matched": rule_ids_matched,
        }

    def log_ooo_event(
        self,
        company_id: str,
        email_data: dict,
        detection: dict,
    ) -> dict:
        """Log an OOO detection event to the database.

        Creates entries in both ooo_detection_log and email_delivery_event tables.

        Args:
            company_id: Tenant company ID.
            email_data: Original email data dict.
            detection: Result from detect_ooo().

        Returns:
            Dict with event_id and status.
        """
        from database.models.email_delivery_event import EmailDeliveryEvent
        from database.models.ooo_detection import OOODetectionLog

        ooo_until = None
        if detection.get("ooo_until"):
            try:
                ooo_until = datetime.fromisoformat(detection["ooo_until"])
            except (ValueError, TypeError):
                pass

        # Log in EmailDeliveryEvent for delivery tracking
        event = EmailDeliveryEvent(
            company_id=company_id,
            event_type="ooo",
            recipient_email=email_data.get("sender_email", ""),
            recipient_name=email_data.get("sender_name", ""),
            brevo_message_id=email_data.get("message_id", ""),
            reason=detection.get("reason", "OOO detected"),
            ooo_until=ooo_until,
            is_processed=True,
            provider_data={
                "detection_source": detection.get("detection_source"),
                "confidence": detection.get("confidence"),
                "type": detection.get("type"),
                "subject": email_data.get("subject", ""),
            },
        )
        self.db.add(event)

        # Log in OOODetectionLog for structured analytics
        confidence_val = 1.0
        conf = detection.get("confidence")
        if conf == "high":
            confidence_val = 1.0
        elif conf == "medium":
            confidence_val = 0.75
        elif conf == "low":
            confidence_val = 0.5

        log = OOODetectionLog(
            company_id=company_id,
            sender_email=email_data.get("sender_email", ""),
            classification=detection.get("type", "ooo"),
            confidence=confidence_val,
            detected_signals=detection.get("detected_signals", []),
            rule_ids_matched=detection.get("rule_ids_matched", []),
            action_taken="tagged",
            message_id=email_data.get("message_id", ""),
        )
        self.db.add(log)

        self.db.commit()
        self.db.refresh(event)
        self.db.refresh(log)

        logger.info(
            "ooo_detected_and_logged",
            extra={
                "company_id": company_id,
                "sender_email": email_data.get("sender_email"),
                "event_id": str(event.id),
                "log_id": str(log.id),
                "detection_source": detection.get("detection_source"),
                "ooo_until": str(ooo_until) if ooo_until else None,
            },
        )

        return {
            "status": "ooo_logged",
            "event_id": str(event.id),
            "log_id": str(log.id),
            "is_ooo": True,
        }

    def update_sender_profile(
        self,
        company_id: str,
        email_data: dict,
        detection: dict,
    ) -> dict:
        """Update sender's OOO profile after detection.

        Creates or updates OOO sender profile with detection count,
        last OOO date, and extracted return date.

        Args:
            company_id: Tenant company ID.
            email_data: Original email data dict.
            detection: Result from detect_ooo().

        Returns:
            Dict with profile status.
        """
        from database.models.ooo_detection import OOOSenderProfile

        sender_email = email_data.get("sender_email", "").lower().strip()
        if not sender_email:
            return {"status": "skipped", "reason": "No sender email"}

        now = datetime.now(timezone.utc)

        # Find or create sender profile
        profile = (
            self.db.query(OOOSenderProfile)
            .filter(
                OOOSenderProfile.company_id == company_id,
                OOOSenderProfile.sender_email == sender_email,
            )
            .first()
        )

        if not profile:
            profile = OOOSenderProfile(
                company_id=company_id,
                sender_email=sender_email,
            )
            self.db.add(profile)

        # Update profile
        profile.ooo_detected_count = (profile.ooo_detected_count or 0) + 1
        profile.last_ooo_at = now
        profile.active_ooo = True

        # Set return date if extracted
        ooo_until_str = detection.get("ooo_until")
        if ooo_until_str:
            try:
                ooo_until = datetime.fromisoformat(ooo_until_str)
                profile.ooo_until = ooo_until
            except (ValueError, TypeError):
                pass

        self.db.commit()
        self.db.refresh(profile)

        logger.info(
            "ooo_sender_profile_updated",
            extra={
                "company_id": company_id,
                "sender_email": sender_email,
                "ooo_count": profile.ooo_detected_count,
                "ooo_until": str(
                    profile.ooo_until) if profile.ooo_until else None,
            },
        )

        return {
            "status": "profile_updated",
            "sender_email": sender_email,
            "ooo_count": profile.ooo_detected_count,
            "ooo_until": str(profile.ooo_until) if profile.ooo_until else None,
        }

    def is_customer_ooo(self, company_id: str, email: str) -> Optional[dict]:
        """Check if a customer currently has an active OOO status.

        Looks for the most recent OOO event for the customer that
        hasn't expired (ooo_until is in the future or None).

        Args:
            company_id: Tenant company ID.
            email: Customer email address.

        Returns:
            Dict with OOO details if active, None otherwise.
        """
        from database.models.ooo_detection import OOOSenderProfile

        now = datetime.now(timezone.utc)

        # Check sender profile first (more accurate)
        profile = (
            self.db.query(OOOSenderProfile)
            .filter(
                OOOSenderProfile.company_id == company_id,
                OOOSenderProfile.sender_email == email.lower().strip(),
                OOOSenderProfile.active_ooo,
            )
            .first()
        )

        if profile:
            # Check if OOO has expired
            if profile.ooo_until and profile.ooo_until < now:
                # Auto-expire
                profile.active_ooo = False
                self.db.commit()
                return None

            return {
                "is_ooo": True,
                "event_id": str(
                    profile.id),
                "ooo_until": profile.ooo_until.isoformat() if profile.ooo_until else None,
                "reason": "Active OOO profile",
                "ooo_count": profile.ooo_detected_count,
                "detected_at": profile.last_ooo_at.isoformat() if profile.last_ooo_at else None,
            }

        # Fallback: check email_delivery_event table
        from database.models.email_delivery_event import EmailDeliveryEvent

        event = (
            self.db.query(EmailDeliveryEvent)
            .filter(
                EmailDeliveryEvent.company_id == company_id,
                EmailDeliveryEvent.recipient_email == email.lower().strip(),
                EmailDeliveryEvent.event_type == "ooo",
            )
            .order_by(EmailDeliveryEvent.created_at.desc())
            .first()
        )

        if not event:
            return None

        # Check if OOO has expired
        if event.ooo_until and event.ooo_until < now:
            return None

        return {
            "is_ooo": True,
            "event_id": str(
                event.id),
            "ooo_until": event.ooo_until.isoformat() if event.ooo_until else None,
            "reason": event.reason,
            "detected_at": event.created_at.isoformat() if event.created_at else None,
        }

    # ── Custom Rules CRUD (F-122) ───────────────────────────────

    def list_rules(self, company_id: str) -> dict:
        """List OOO detection rules for a tenant.

        Returns both tenant-specific and global rules.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with custom_rules and global_rules_count.
        """
        from database.models.ooo_detection import OOODetectionRule

        # Tenant-specific rules
        custom_rules = (
            self.db.query(OOODetectionRule)
            .filter(OOODetectionRule.company_id == company_id)
            .order_by(OOODetectionRule.created_at.desc())
            .all()
        )

        # Count global rules
        global_count = (
            self.db.query(func.count(OOODetectionRule.id))
            .filter(OOODetectionRule.company_id == None)  # noqa: E711
            .scalar()
        ) or 0

        return {
            "custom_rules": [
                {
                    "id": str(r.id),
                    "company_id": r.company_id,
                    "rule_type": r.rule_type,
                    "pattern": r.pattern,
                    "pattern_type": r.pattern_type,
                    "classification": r.classification,
                    "active": r.active,
                    "match_count": r.match_count or 0,
                    "last_matched_at": r.last_matched_at.isoformat() if r.last_matched_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in custom_rules
            ],
            "global_rules_count": global_count,
        }

    def create_rule(
        self,
        company_id: str,
        pattern: str,
        pattern_type: str = "regex",
        rule_type: str = "body",
        classification: str = "ooo",
        active: bool = True,
    ) -> dict:
        """Create a custom OOO detection rule.

        Args:
            company_id: Tenant company ID.
            pattern: Detection pattern.
            pattern_type: regex/substring/contains.
            rule_type: header/body/sender_behavior/frequency.
            classification: ooo/auto_reply/cyclic/spam.
            active: Whether rule is active.

        Returns:
            Dict with rule_id and status.
        """
        from database.models.ooo_detection import OOODetectionRule

        # Validate regex pattern
        if pattern_type == "regex":
            try:
                re.compile(pattern)
            except re.error as exc:
                return {
                    "status": "error",
                    "error": f"Invalid regex: {
                        str(exc)}"}

        rule = OOODetectionRule(
            company_id=company_id,
            rule_type=rule_type,
            pattern=pattern,
            pattern_type=pattern_type,
            classification=classification,
            active=active,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        logger.info(
            "ooo_rule_created",
            extra={
                "company_id": company_id,
                "rule_id": str(rule.id),
                "pattern": pattern[:50],
            },
        )

        return {"rule_id": str(rule.id), "status": "created"}

    def update_rule(
        self,
        company_id: str,
        rule_id: str,
        updates: dict,
    ) -> dict:
        """Update a custom OOO detection rule.

        Args:
            company_id: Tenant company ID.
            rule_id: Rule UUID.
            updates: Dict of fields to update.

        Returns:
            Dict with rule_id and status.
        """
        from database.models.ooo_detection import OOODetectionRule

        rule = (
            self.db.query(OOODetectionRule)
            .filter(
                OOODetectionRule.id == rule_id,
                OOODetectionRule.company_id == company_id,
            )
            .first()
        )

        if not rule:
            return {"status": "error", "error": "Rule not found"}

        # Validate regex if pattern is being updated
        if updates.get("pattern") and updates.get(
                "pattern_type", rule.pattern_type) == "regex":
            try:
                re.compile(updates["pattern"])
            except re.error as exc:
                return {
                    "status": "error",
                    "error": f"Invalid regex: {
                        str(exc)}"}

        for field, value in updates.items():
            if hasattr(rule, field) and value is not None:
                setattr(rule, field, value)

        self.db.commit()
        self.db.refresh(rule)

        return {"rule_id": str(rule.id), "status": "updated"}

    def delete_rule(self, company_id: str, rule_id: str) -> dict:
        """Delete a custom OOO detection rule.

        Args:
            company_id: Tenant company ID.
            rule_id: Rule UUID.

        Returns:
            Dict with status.
        """
        from database.models.ooo_detection import OOODetectionRule

        rule = (
            self.db.query(OOODetectionRule)
            .filter(
                OOODetectionRule.id == rule_id,
                OOODetectionRule.company_id == company_id,
            )
            .first()
        )

        if not rule:
            return {"status": "error", "error": "Rule not found"}

        self.db.delete(rule)
        self.db.commit()

        return {"rule_id": rule_id, "status": "deleted"}

    def get_stats(self, company_id: str, range_days: int = 7) -> dict:
        """Get OOO detection statistics for a tenant.

        Args:
            company_id: Tenant company ID.
            range_days: Number of days to look back.

        Returns:
            Dict with detection counts, by type breakdown, top senders.
        """
        from database.models.ooo_detection import OOODetectionLog

        since = datetime.now(timezone.utc) - timedelta(days=range_days)

        # Total detections
        total = (
            self.db.query(func.count(OOODetectionLog.id))
            .filter(
                OOODetectionLog.company_id == company_id,
                OOODetectionLog.created_at >= since,
            )
            .scalar()
        ) or 0

        # By classification type
        by_type_rows = (
            self.db.query(
                OOODetectionLog.classification,
                func.count(OOODetectionLog.id),
            )
            .filter(
                OOODetectionLog.company_id == company_id,
                OOODetectionLog.created_at >= since,
            )
            .group_by(OOODetectionLog.classification)
            .all()
        )
        by_type = {cls: count for cls, count in by_type_rows}

        # Top senders
        top_senders_rows = (
            self.db.query(
                OOODetectionLog.sender_email,
                func.count(OOODetectionLog.id).label("count"),
            )
            .filter(
                OOODetectionLog.company_id == company_id,
                OOODetectionLog.created_at >= since,
            )
            .group_by(OOODetectionLog.sender_email)
            .order_by(func.count(OOODetectionLog.id).desc())
            .limit(10)
            .all()
        )
        top_senders = [{"email": email, "count": count}
                       for email, count in top_senders_rows]

        # Count loop-prevented (cyclic classification)
        loop_prevented = by_type.get("cyclic", 0)

        return {
            "detected_count": total,
            "by_type": by_type,
            "top_senders": top_senders,
            "loop_prevented_count": loop_prevented,
            "range_days": range_days,
        }

    def cleanup_expired_profiles(
            self, company_id: Optional[str] = None) -> int:
        """Clean up expired OOO sender profiles (BC-004 Celery beat).

        Resets active_ooo=false for profiles where ooo_until has passed.

        Args:
            company_id: Optional tenant filter.

        Returns:
            Number of profiles cleaned up.
        """
        from database.models.ooo_detection import OOOSenderProfile

        now = datetime.now(timezone.utc)
        query = (
            self.db.query(OOOSenderProfile)
            .filter(
                OOOSenderProfile.active_ooo,
            )
        )
        if company_id:
            query = query.filter(OOOSenderProfile.company_id == company_id)

        expired_profiles = query.all()
        count = 0
        for profile in expired_profiles:
            if profile.ooo_until and profile.ooo_until < now:
                profile.active_ooo = False
                count += 1

        if count > 0:
            self.db.commit()
            logger.info(
                "ooo_profiles_cleaned",
                extra={
                    "company_id": company_id,
                    "cleaned_count": count,
                },
            )

        return count

    # ── Private Methods ─────────────────────────────────────────

    @staticmethod
    def _check_headers(headers: dict) -> dict:
        """Check email headers for OOO indicators (RFC 3834).

        Returns dict with is_ooo, reason, detection_source, confidence.
        """
        # Check Auto-Submitted header
        auto_submitted = str(
            headers.get(
                "auto-submitted",
                "") or headers.get(
                "auto_submitted",
                "")).strip().lower()
        if auto_submitted in OOO_AUTO_SUBMITTED_VALUES:
            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "reason": f"Auto-Submitted header: {auto_submitted}",
                "detection_source": "header",
                "confidence": "high",
            }

        # Check X-Auto-Response-Suppress
        suppress = str(
            headers.get(
                "x-auto-response-suppress",
                "")).strip().lower()
        if suppress in OOO_X_AUTO_RESPONSE_VALUES:
            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "reason": f"X-Auto-Response-Suppress: {suppress}",
                "detection_source": "header",
                "confidence": "high",
            }

        # Check X-Auto-Reply header
        auto_reply = headers.get("x-auto-reply", "")
        if auto_reply:
            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "reason": "X-Auto-Reply header present",
                "detection_source": "header",
                "confidence": "high",
            }

        # Check Precedence: auto_reply (BC-006)
        precedence = str(headers.get("precedence", "")).strip().lower()
        if "auto" in precedence or "list" in precedence or "bulk" in precedence:
            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "reason": f"Precedence header: {precedence}",
                "detection_source": "header",
                "confidence": "high",
            }

        return {"is_ooo": False, "is_auto_reply": False}

    @staticmethod
    def _check_subject(subject: str) -> dict:
        """Check subject line for OOO patterns.

        Returns dict with is_ooo, reason, detection_source, confidence.
        """
        if not subject or len(subject) < 4:
            return {"is_ooo": False, "is_auto_reply": False}

        for pattern in OOO_SUBJECT_PATTERNS:
            if pattern.search(subject):
                return {
                    "is_ooo": True,
                    "is_auto_reply": True,
                    "reason": f"OOO subject pattern: {pattern.pattern[:50]}",
                    "detection_source": "subject",
                    "confidence": "medium",
                }

        return {"is_ooo": False, "is_auto_reply": False}

    @staticmethod
    def _check_body(body: str) -> dict:
        """Check body text for OOO patterns.

        Requires at least 2 pattern matches to reduce false positives.
        Returns confidence based on number of matches.

        Returns dict with is_ooo, reason, detection_source, confidence.
        """
        if not body or len(body) < MIN_BODY_LENGTH_FOR_PATTERN_CHECK:
            return {"is_ooo": False, "is_auto_reply": False}

        matches = []
        for pattern in OOO_BODY_PATTERNS:
            match = pattern.search(body)
            if match:
                matches.append({
                    "pattern": pattern.pattern[:60],
                    "matched_text": match.group()[:80],
                })

        if len(matches) >= BODY_MIN_PATTERN_MATCHES:
            # Confidence scoring based on match count
            if len(matches) >= BODY_CONFIDENCE_HIGH_THRESHOLD:
                confidence = "high"
            elif len(matches) >= BODY_CONFIDENCE_MEDIUM_THRESHOLD:
                confidence = "medium"
            else:
                confidence = "low"

            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "type": "ooo",
                "reason": f"OOO body patterns matched ({
                    len(matches)}): {
                    matches[0]['matched_text']}",
                "detection_source": "body",
                "confidence": confidence,
            }

        return {"is_ooo": False, "is_auto_reply": False}

    def _check_custom_rules(self, company_id: str, email_data: dict) -> dict:
        """Check tenant-specific OOO detection rules.

        Args:
            company_id: Tenant company ID.
            email_data: Email data dict.

        Returns:
            Detection result dict.
        """
        try:
            from database.models.ooo_detection import OOODetectionRule

            # Load active rules (tenant-specific + global)
            rules = (
                self.db.query(OOODetectionRule)
                .filter(
                    or_(
                        OOODetectionRule.company_id == company_id,
                        OOODetectionRule.company_id == None,  # noqa: E711
                    ),
                    OOODetectionRule.active == True,
                )
                .all()
            )
        except Exception:
            return {"is_ooo": False}

        if not rules or not hasattr(rules, '__iter__'):
            return {"is_ooo": False}

        headers_str = email_data.get("headers_json", "")
        headers = {}
        if headers_str:
            try:
                headers = json.loads(headers_str) if isinstance(
                    headers_str, str) else headers_str
            except (json.JSONDecodeError, TypeError):
                pass

        body = email_data.get("body_text", "") or ""
        subject = email_data.get("subject", "") or ""

        detected_signals = []
        rule_ids_matched = []

        for rule in rules:
            matched = False
            text_to_check = ""

            if rule.rule_type == "header":
                # Check against all header values
                for key, value in headers.items():
                    if self._match_pattern(
                            value or "", rule.pattern, rule.pattern_type):
                        matched = True
                        text_to_check = f"header:{key}={value}"
                        break
            elif rule.rule_type == "subject":
                text_to_check = subject
                matched = self._match_pattern(
                    subject, rule.pattern, rule.pattern_type)
            elif rule.rule_type == "body":
                text_to_check = body
                matched = self._match_pattern(
                    body, rule.pattern, rule.pattern_type)
            elif rule.rule_type == "sender_behavior":
                # Check sender email against pattern
                text_to_check = email_data.get("sender_email", "")
                matched = self._match_pattern(
                    text_to_check, rule.pattern, rule.pattern_type)

            if matched:
                detected_signals.append(f"rule:{rule.pattern[:50]}")
                rule_ids_matched.append(str(rule.id))

                # Update rule match count
                rule.match_count = (rule.match_count or 0) + 1
                rule.last_matched_at = datetime.now(timezone.utc)

        self.db.flush()

        if detected_signals:
            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "type": rules[0].classification if rule_ids_matched else "ooo",
                "reason": f"Custom rules matched: {len(detected_signals)}",
                "detection_source": "rule",
                "confidence": "high",
                "detected_signals": detected_signals,
                "rule_ids_matched": rule_ids_matched,
            }

        return {"is_ooo": False}

    @staticmethod
    def _match_pattern(text: str, pattern: str, pattern_type: str) -> bool:
        """Match text against a detection pattern.

        Args:
            text: Text to check.
            pattern: Detection pattern.
            pattern_type: regex/substring/contains.

        Returns:
            True if pattern matches.
        """
        if not text or not pattern:
            return False

        if pattern_type == "regex":
            try:
                return bool(re.search(pattern, text, re.IGNORECASE))
            except re.error:
                return False
        elif pattern_type == "substring":
            return pattern.lower() in text.lower()
        elif pattern_type == "contains":
            # Any word in pattern (space-separated) matches
            words = pattern.lower().split()
            text_lower = text.lower()
            return any(word in text_lower for word in words)

        return False

    def _check_sender_profile(
        self, company_id: str, sender_email: str,
    ) -> dict:
        """Check sender's OOO profile for frequency-based detection.

        If the same sender has 3+ OOO detections in the last 7 days,
        classify as cyclic auto-reply.

        Args:
            company_id: Tenant company ID.
            sender_email: Sender email address.

        Returns:
            Detection result dict.
        """
        try:
            from database.models.ooo_detection import OOOSenderProfile

            profile = (
                self.db.query(OOOSenderProfile) .filter(
                    OOOSenderProfile.company_id == company_id,
                    OOOSenderProfile.sender_email == sender_email.lower().strip(),
                ) .first())

            if not profile or not getattr(profile, "active_ooo", False):
                return {"is_ooo": False}

            return {
                "is_ooo": True,
                "is_auto_reply": True,
                "type": "cyclic",
                "reason": f"Sender has active OOO profile (count: {
                    profile.ooo_detected_count})",
                "detection_source": "sender_profile",
                "confidence": "high",
            }
        except Exception:
            return {"is_ooo": False}

    @staticmethod
    def _extract_return_date(text: str) -> Optional[str]:
        """Try to extract a return date from OOO email body.

        Looks for common date patterns like:
        - "return on January 15, 2026"
        - "back on 2026-01-15"
        - "returning Mon Jan 15"
        - "until 15/01/2026"

        Args:
            text: Email body text.

        Returns:
            ISO date string if found, None otherwise.
        """
        if not text:
            return None

        date_patterns = [
            # "January 15, 2026" / "15 January 2026" / "Jan 15, 2026"
            re.compile(
                r"(?:return(?:ing)?|back)\s+(?:on\s+)?"
                r"(\w+\s+\d{1,2}(?:,?\s+\d{4})?)",
                re.IGNORECASE,
            ),
            # "2026-01-15" / "15/01/2026" / "15.01.2026" / "until 2026-01-15"
            re.compile(
                r"(?:until|return\s+(?:on|by))\s*(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
                re.IGNORECASE,
            ),
            # "15th of January"
            re.compile(
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(\w+)\s*(?:,?\s*(\d{4}))?",
                re.IGNORECASE,
            ),
        ]

        # Try each pattern
        for pattern in date_patterns:
            match = pattern.search(text[:2000])  # Search first 2000 chars
            if match:
                matched_text = match.group(1)
                # Try multiple date formats
                for fmt in [
                    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
                    "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
                    "%d %B %Y", "%d %b %Y", "%m/%d/%Y",
                    "%B %d", "%b %d", "%d %B", "%d %b",
                ]:
                    try:
                        parsed = datetime.strptime(matched_text.strip(), fmt)
                        # If no year, assume current or next year
                        if parsed.year == 1900:
                            parsed = parsed.replace(year=datetime.now().year)
                            if parsed < datetime.now():
                                parsed = parsed.replace(
                                    year=datetime.now().year + 1)
                        return parsed.isoformat()
                    except ValueError:
                        continue

        return None
