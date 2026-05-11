"""
Tech Diagnostics Engine — Diagnostic Tools + Known Issue Detection + Severity Scoring.

Improvement Target: Technical Support L1 82% → 90% automation.

Components:
  1. Diagnostic Tool Integration: Simulated diagnostic steps that the AI
     can walk customers through (clear cache, check connectivity, verify
     settings, test functionality). Produces step-by-step troubleshooting.
  2. Known Issue Auto-Detection: Pattern matching against a knowledge base
     of known issues (service outages, bugs, maintenance windows). When a
     known issue matches, auto-informs the customer with ETA.
  3. Escalation Severity Scoring: Multi-factor scoring to determine if
     an issue needs L2/L3 escalation vs. L1 self-resolution. Factors in
     technical complexity, business impact, and customer tier.

Architecture:
  Called from smart_enrichment node to detect known issues and assess
  severity. Called from auto_action node to generate diagnostic steps
  and trigger escalation if needed.

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("tech_diagnostics")


# ══════════════════════════════════════════════════════════════════
# KNOWN ISSUES DATABASE
# ══════════════════════════════════════════════════════════════════

KNOWN_ISSUES: Dict[str, Dict[str, Any]] = {
    "service_outage": {
        "keywords": [
            "site down", "service down", "not loading", "can't access",
            "server error", "503", "502", "500 error", "maintenance",
            "outage", "unavailable", "offline", "not responding",
        ],
        "severity": "high",
        "auto_communicate": True,
        "resolution_type": "wait_for_fix",
        "eta_hours": 4,
        "message_template": (
            "We're aware of a service disruption affecting some users. "
            "Our engineering team is actively working on a fix. "
            "Estimated restoration: within {eta_hours} hours. "
            "We apologize for the inconvenience."
        ),
    },
    "login_issues": {
        "keywords": [
            "can't log in", "login not working", "can't sign in",
            "password not working", "login error", "authentication failed",
            "locked out", "can't access account",
        ],
        "severity": "medium",
        "auto_communicate": True,
        "resolution_type": "self_service_steps",
        "eta_hours": 0,
        "message_template": (
            "We can help you regain access. Let's try a few steps: "
            "1) Reset your password via the 'Forgot Password' link, "
            "2) Clear your browser cookies, "
            "3) Try an incognito/private window. "
            "If these don't work, we'll escalate to our security team."
        ),
    },
    "payment_processing": {
        "keywords": [
            "payment failed", "can't pay", "checkout error",
            "payment not processing", "transaction failed",
            "card declined", "payment error",
        ],
        "severity": "high",
        "auto_communicate": True,
        "resolution_type": "self_service_steps",
        "eta_hours": 0,
        "message_template": (
            "Payment processing issues are usually resolved quickly. "
            "Try: 1) Use a different payment method, "
            "2) Clear your browser cache, "
            "3) Ensure your billing address matches your card. "
            "If the issue persists, our billing team will investigate."
        ),
    },
    "sync_issues": {
        "keywords": [
            "not syncing", "data not updating", "out of sync",
            "sync error", "data mismatch", "stale data",
            "changes not reflecting", "delayed sync",
        ],
        "severity": "medium",
        "auto_communicate": True,
        "resolution_type": "self_service_steps",
        "eta_hours": 1,
        "message_template": (
            "Sync issues often resolve with a refresh. Try: "
            "1) Log out and back in, "
            "2) Force-refresh (Ctrl+Shift+R), "
            "3) Check your internet connection. "
            "If data is still not syncing, we'll investigate further."
        ),
    },
    "api_errors": {
        "keywords": [
            "api error", "rate limit", "429", "timeout",
            "api not working", "endpoint error", "api down",
            "integration error", "webhook failed",
        ],
        "severity": "medium",
        "auto_communicate": True,
        "resolution_type": "wait_for_fix",
        "eta_hours": 2,
        "message_template": (
            "We're aware of intermittent API issues. "
            "If you're hitting rate limits, try reducing request frequency. "
            "Our team is monitoring the situation. "
            "Expected resolution: within {eta_hours} hours."
        ),
    },
    "mobile_app_issues": {
        "keywords": [
            "app crashing", "mobile not working", "app error",
            "mobile app", "ios issue", "android issue",
            "app freeze", "app won't open",
        ],
        "severity": "low",
        "auto_communicate": True,
        "resolution_type": "self_service_steps",
        "eta_hours": 0,
        "message_template": (
            "Mobile app issues can often be resolved quickly. Try: "
            "1) Force-close and reopen the app, "
            "2) Update to the latest version, "
            "3) Clear app cache in your device settings, "
            "4) Uninstall and reinstall if needed."
        ),
    },
}

# Diagnostic step templates
DIAGNOSTIC_STEPS: Dict[str, Dict[str, Any]] = {
    "connectivity": {
        "name": "Connectivity Check",
        "steps": [
            {"step": 1, "action": "Verify internet connection is active", "check": "Can you load other websites?"},
            {"step": 2, "action": "Check for VPN/proxy interference", "check": "Are you using a VPN or proxy?"},
            {"step": 3, "action": "Test DNS resolution", "check": "Try accessing via a different browser"},
        ],
        "applies_to": ["service_outage", "sync_issues", "api_errors"],
    },
    "browser": {
        "name": "Browser Troubleshooting",
        "steps": [
            {"step": 1, "action": "Clear browser cache and cookies", "check": "Press Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)"},
            {"step": 2, "action": "Disable browser extensions", "check": "Try in an incognito/private window"},
            {"step": 3, "action": "Update browser to latest version", "check": "Check Help > About in your browser"},
            {"step": 4, "action": "Try a different browser", "check": "Chrome, Firefox, Safari, or Edge"},
        ],
        "applies_to": ["login_issues", "payment_processing", "service_outage"],
    },
    "account": {
        "name": "Account Verification",
        "steps": [
            {"step": 1, "action": "Verify email address is correct", "check": "Check the email you're using to log in"},
            {"step": 2, "action": "Reset password if needed", "check": "Use the 'Forgot Password' link"},
            {"step": 3, "action": "Check for account lockout", "check": "Have you tried logging in multiple times?"},
            {"step": 4, "action": "Verify 2FA settings", "check": "Is two-factor authentication enabled?"},
        ],
        "applies_to": ["login_issues"],
    },
    "payment": {
        "name": "Payment Troubleshooting",
        "steps": [
            {"step": 1, "action": "Verify card details are correct", "check": "Check card number, expiry, and CVV"},
            {"step": 2, "action": "Check available balance/credit", "check": "Ensure sufficient funds are available"},
            {"step": 3, "action": "Try alternative payment method", "check": "Use a different card or payment option"},
            {"step": 4, "action": "Verify billing address", "check": "Ensure billing address matches card statement"},
        ],
        "applies_to": ["payment_processing"],
    },
}

# Escalation severity criteria
SEVERITY_FACTORS: Dict[str, Dict[str, Any]] = {
    "business_impact": {
        "critical_keywords": ["revenue", "production", "live", "customers affected", "down"],
        "high_keywords": ["workflow", "team", "deadline", "important"],
        "medium_keywords": ["inconvenience", "annoying", "workaround"],
        "weight": 0.35,
    },
    "technical_complexity": {
        "critical_keywords": ["data loss", "security", "breach", "corruption"],
        "high_keywords": ["integration", "api", "database", "migration"],
        "medium_keywords": ["display", "formatting", "sync", "cache"],
        "weight": 0.30,
    },
    "customer_tier": {
        "enterprise": 0.9,
        "growth": 0.7,
        "starter": 0.5,
        "free": 0.3,
        "weight": 0.20,
    },
    "resolution_urgency": {
        "immediate_keywords": ["now", "urgent", "asap", "critical", "emergency"],
        "high_keywords": ["today", "soon", "quickly", "deadline"],
        "medium_keywords": ["when possible", "convenient", "no rush"],
        "weight": 0.15,
    },
}


class TechDiagnosticsEngine:
    """Tech Diagnostics Engine for L1 technical support automation.

    Provides:
      - Known issue detection against knowledge base
      - Step-by-step diagnostic generation
      - Escalation severity scoring
      - Self-service resolution guidance

    Usage:
        engine = TechDiagnosticsEngine()
        known = engine.detect_known_issue(query)
        diag = engine.generate_diagnostics(query, known_issue)
        severity = engine.score_severity(query, signals, customer_tier)
    """

    def __init__(self) -> None:
        """Initialize the tech diagnostics engine."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        try:
            for issue_id, config in KNOWN_ISSUES.items():
                patterns = []
                for kw in config["keywords"]:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_patterns[issue_id] = patterns
        except Exception:
            logger.exception("tech_pattern_compilation_failed")

    def detect_known_issue(
        self,
        query: str,
        classification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Detect if the query matches a known issue in the knowledge base.

        Args:
            query: Customer's raw message.
            classification: Classification result.

        Returns:
            Known issue detection dict:
              - known_issue_detected: bool
              - issue_id: str
              - severity: str
              - auto_communicate: bool
              - resolution_type: str
              - eta_hours: int
              - message: str
              - confidence: float
        """
        try:
            if not query:
                return self._default_known_issue()

            query_lower = query.lower()

            best_issue = None
            best_confidence = 0.0
            best_match_count = 0

            for issue_id, patterns in self._compiled_patterns.items():
                match_count = 0
                for pattern in patterns:
                    if pattern.search(query_lower):
                        match_count += 1

                if match_count > 0:
                    confidence = min(1.0, match_count * 0.25 + 0.3)
                    if match_count > best_match_count or (
                        match_count == best_match_count and confidence > best_confidence
                    ):
                        best_issue = issue_id
                        best_confidence = confidence
                        best_match_count = match_count

            if best_issue and best_confidence >= 0.3:
                issue_config = KNOWN_ISSUES[best_issue]
                message = issue_config.get("message_template", "")
                eta = issue_config.get("eta_hours", 0)
                if "{eta_hours}" in message:
                    message = message.format(eta_hours=eta)

                return {
                    "known_issue_detected": True,
                    "issue_id": best_issue,
                    "severity": issue_config.get("severity", "medium"),
                    "auto_communicate": issue_config.get("auto_communicate", True),
                    "resolution_type": issue_config.get("resolution_type", "self_service_steps"),
                    "eta_hours": eta,
                    "message": message,
                    "confidence": round(best_confidence, 3),
                }

            return self._default_known_issue()

        except Exception:
            logger.exception("known_issue_detection_failed")
            return self._default_known_issue()

    def generate_diagnostics(
        self,
        query: str,
        known_issue: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate step-by-step diagnostic guidance for the customer.

        Args:
            query: Customer's raw message.
            known_issue: Output from detect_known_issue().

        Returns:
            Diagnostic dict:
              - diagnostic_steps: List[Dict] (ordered steps)
              - diagnostic_categories: List[str]
              - prompt_addition: str
              - estimated_resolution_time: str
        """
        try:
            applicable_diagnostics: List[Dict[str, Any]] = []
            categories: List[str] = []

            # If known issue, use its resolution type to select diagnostics
            issue_id = None
            if known_issue and known_issue.get("known_issue_detected"):
                issue_id = known_issue.get("issue_id", "")

            # Select applicable diagnostic categories
            for diag_id, diag_config in DIAGNOSTIC_STEPS.items():
                if issue_id and issue_id in diag_config.get("applies_to", []):
                    applicable_diagnostics.append({
                        "category": diag_id,
                        "name": diag_config["name"],
                        "steps": diag_config["steps"],
                    })
                    categories.append(diag_id)

            # If no specific diagnostics matched, provide browser + connectivity
            if not applicable_diagnostics:
                # Default: check if query suggests tech issue
                tech_indicators = [
                    "not working", "error", "broken", "issue", "problem",
                    "bug", "crash", "fail", "can't", "doesn't work",
                ]
                query_lower = query.lower() if query else ""
                is_tech = any(ind in query_lower for ind in tech_indicators)

                if is_tech:
                    for diag_id in ["connectivity", "browser"]:
                        diag = DIAGNOSTIC_STEPS[diag_id]
                        applicable_diagnostics.append({
                            "category": diag_id,
                            "name": diag["name"],
                            "steps": diag["steps"],
                        })
                        categories.append(diag_id)

            # Build combined steps list
            all_steps: List[Dict[str, Any]] = []
            step_num = 1
            for diag in applicable_diagnostics:
                for step in diag["steps"]:
                    all_steps.append({
                        "step": step_num,
                        "category": diag["name"],
                        "action": step["action"],
                        "check": step["check"],
                    })
                    step_num += 1

            # Generate prompt addition
            prompt = self._diagnostic_prompt(all_steps, known_issue)

            # Estimate resolution time
            if known_issue and known_issue.get("known_issue_detected"):
                eta = known_issue.get("eta_hours", 0)
                if eta > 0:
                    est_time = f"within {eta} hours (known issue fix ETA)"
                else:
                    est_time = "immediate (self-service steps provided)"
            else:
                est_time = "5-15 minutes (self-service diagnostics)"

            return {
                "diagnostic_steps": all_steps,
                "diagnostic_categories": categories,
                "prompt_addition": prompt,
                "estimated_resolution_time": est_time,
            }

        except Exception:
            logger.exception("diagnostic_generation_failed")
            return {
                "diagnostic_steps": [],
                "diagnostic_categories": [],
                "prompt_addition": "",
                "estimated_resolution_time": "unknown",
            }

    def score_severity(
        self,
        query: str,
        signals: Optional[Dict[str, Any]] = None,
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Score the escalation severity of a technical issue.

        Multi-factor scoring:
          - Business impact (35%): How much does this affect the customer's business?
          - Technical complexity (30%): How complex is the underlying issue?
          - Customer tier (20%: Enterprise > Growth > Starter > Free)
          - Resolution urgency (15%): How quickly does this need to be fixed?

        Args:
            query: Customer's raw message.
            signals: Extracted signals.
            customer_tier: Customer subscription tier.

        Returns:
            Severity scoring dict:
              - severity_score: float (0.0-1.0)
              - severity_level: str (low/medium/high/critical)
              - escalation_path: str (l1_self_service/l2_specialist/l3_engineering/emergency)
              - factors: Dict[str, float]
              - recommended_actions: List[str]
        """
        try:
            if not query:
                return self._default_severity()

            query_lower = query.lower()

            # Factor 1: Business Impact
            business_score = 0.3  # baseline
            for level, keywords in [
                ("critical", SEVERITY_FACTORS["business_impact"]["critical_keywords"]),
                ("high", SEVERITY_FACTORS["business_impact"]["high_keywords"]),
                ("medium", SEVERITY_FACTORS["business_impact"]["medium_keywords"]),
            ]:
                for kw in keywords:
                    if kw in query_lower:
                        score_map = {"critical": 0.9, "high": 0.7, "medium": 0.5}
                        business_score = max(business_score, score_map[level])
                        break

            # Factor 2: Technical Complexity
            tech_score = 0.3
            for level, keywords in [
                ("critical", SEVERITY_FACTORS["technical_complexity"]["critical_keywords"]),
                ("high", SEVERITY_FACTORS["technical_complexity"]["high_keywords"]),
                ("medium", SEVERITY_FACTORS["technical_complexity"]["medium_keywords"]),
            ]:
                for kw in keywords:
                    if kw in query_lower:
                        score_map = {"critical": 0.95, "high": 0.7, "medium": 0.5}
                        tech_score = max(tech_score, score_map[level])
                        break

            # Factor 3: Customer Tier
            tier_score = SEVERITY_FACTORS["customer_tier"].get(customer_tier, 0.3)

            # Factor 4: Resolution Urgency
            urgency_score = 0.3
            for level, keywords in [
                ("immediate", SEVERITY_FACTORS["resolution_urgency"]["immediate_keywords"]),
                ("high", SEVERITY_FACTORS["resolution_urgency"]["high_keywords"]),
                ("medium", SEVERITY_FACTORS["resolution_urgency"]["medium_keywords"]),
            ]:
                for kw in keywords:
                    if kw in query_lower:
                        score_map = {"immediate": 0.9, "high": 0.7, "medium": 0.5}
                        urgency_score = max(urgency_score, score_map[level])
                        break

            # Factor in signals
            if signals:
                frustration = signals.get("frustration_score", 0)
                if frustration > 70:
                    urgency_score = min(1.0, urgency_score * 1.2)
                complexity = signals.get("complexity", 0.5)
                tech_score = min(1.0, tech_score * (0.7 + complexity * 0.3))

            # Weighted composite score
            severity_score = (
                business_score * SEVERITY_FACTORS["business_impact"]["weight"]
                + tech_score * SEVERITY_FACTORS["technical_complexity"]["weight"]
                + tier_score * SEVERITY_FACTORS["customer_tier"]["weight"]
                + urgency_score * SEVERITY_FACTORS["resolution_urgency"]["weight"]
            )

            # Determine severity level
            if severity_score >= 0.75:
                severity_level = "critical"
            elif severity_score >= 0.55:
                severity_level = "high"
            elif severity_score >= 0.35:
                severity_level = "medium"
            else:
                severity_level = "low"

            # Determine escalation path
            if severity_score >= 0.75:
                escalation_path = "emergency"
            elif severity_score >= 0.55:
                escalation_path = "l3_engineering"
            elif severity_score >= 0.35:
                escalation_path = "l2_specialist"
            else:
                escalation_path = "l1_self_service"

            # Recommended actions
            recommended: List[str] = []
            if escalation_path == "l1_self_service":
                recommended = ["provide_diagnostics", "self_service_steps", "follow_up_if_unresolved"]
            elif escalation_path == "l2_specialist":
                recommended = ["provide_initial_diagnostics", "escalate_to_l2", "schedule_callback"]
            elif escalation_path == "l3_engineering":
                recommended = ["acknowledge_severity", "escalate_to_l3", "provide_workaround", "hourly_updates"]
            elif escalation_path == "emergency":
                recommended = ["immediate_escalation", "management_notification", "dedicated_engineer", "real_time_updates"]

            return {
                "severity_score": round(severity_score, 3),
                "severity_level": severity_level,
                "escalation_path": escalation_path,
                "factors": {
                    "business_impact": round(business_score, 3),
                    "technical_complexity": round(tech_score, 3),
                    "customer_tier": round(tier_score, 3),
                    "resolution_urgency": round(urgency_score, 3),
                },
                "recommended_actions": recommended,
            }

        except Exception:
            logger.exception("severity_scoring_failed")
            return self._default_severity()

    def get_tech_actions(
        self,
        known_issue: Dict[str, Any],
        diagnostics: Dict[str, Any],
        severity: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automated tech support actions.

        Args:
            known_issue: Output from detect_known_issue().
            diagnostics: Output from generate_diagnostics().
            severity: Output from score_severity().

        Returns:
            List of action dicts for auto_action node.
        """
        try:
            actions: List[Dict[str, Any]] = []
            escalation_path = severity.get("escalation_path", "l1_self_service")

            # Known issue auto-communication
            if known_issue.get("known_issue_detected") and known_issue.get("auto_communicate"):
                actions.append({
                    "action_type": "communicate_known_issue",
                    "action_data": {
                        "issue_id": known_issue.get("issue_id"),
                        "message": known_issue.get("message", ""),
                        "eta_hours": known_issue.get("eta_hours", 0),
                    },
                    "priority": "high" if known_issue.get("severity") == "high" else "medium",
                    "automated": True,
                })

            # Escalation actions
            if escalation_path in ("l2_specialist", "l3_engineering", "emergency"):
                actions.append({
                    "action_type": "escalate_to_specialist",
                    "action_data": {
                        "escalation_path": escalation_path,
                        "severity_score": severity.get("severity_score", 0.0),
                        "severity_level": severity.get("severity_level", "low"),
                        "recommended_actions": severity.get("recommended_actions", []),
                    },
                    "priority": "critical" if escalation_path == "emergency" else "high",
                    "automated": True,
                })

            # Follow-up scheduling
            if escalation_path == "l1_self_service":
                actions.append({
                    "action_type": "schedule_tech_followup",
                    "action_data": {
                        "delay_hours": 24,
                        "channel": "email",
                        "check_resolution": True,
                    },
                    "priority": "low",
                    "automated": True,
                })

            return actions

        except Exception:
            logger.exception("tech_action_generation_failed")
            return []

    def generate_diagnostic_result(
        self,
        query: str,
        known_issue: Dict[str, Any],
        diagnostics: Dict[str, Any],
        severity: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive diagnostic result summary.

        Args:
            query: Customer's raw message.
            known_issue: Output from detect_known_issue().
            diagnostics: Output from generate_diagnostics().
            severity: Output from score_severity().

        Returns:
            Diagnostic result dict:
              - steps_provided: int
              - known_issue_match: bool
              - severity_assessment: str
              - auto_fix_available: bool
              - resolution_path: str
        """
        try:
            steps_count = len(diagnostics.get("diagnostic_steps", []))
            known_match = known_issue.get("known_issue_detected", False)
            severity_level = severity.get("severity_level", "low")
            escalation_path = severity.get("escalation_path", "l1_self_service")

            # Auto-fix available if known issue with self-service resolution
            auto_fix = (
                known_match
                and known_issue.get("resolution_type") == "self_service_steps"
            ) or (escalation_path == "l1_self_service" and steps_count > 0)

            # Determine resolution path
            if known_match and known_issue.get("eta_hours", 0) > 0:
                resolution_path = "wait_for_known_issue_fix"
            elif auto_fix:
                resolution_path = "self_service_diagnostics"
            elif escalation_path in ("l2_specialist", "l3_engineering"):
                resolution_path = "escalate_to_specialist"
            elif escalation_path == "emergency":
                resolution_path = "emergency_escalation"
            else:
                resolution_path = "self_service_diagnostics"

            return {
                "steps_provided": steps_count,
                "known_issue_match": known_match,
                "severity_assessment": severity_level,
                "auto_fix_available": auto_fix,
                "resolution_path": resolution_path,
            }
        except Exception:
            logger.exception("diagnostic_result_generation_failed")
            return {
                "steps_provided": 0,
                "known_issue_match": False,
                "severity_assessment": "low",
                "auto_fix_available": False,
                "resolution_path": "self_service_diagnostics",
            }

    def decide_escalation(
        self,
        severity: Dict[str, Any],
        known_issue: Dict[str, Any],
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Make escalation decision based on severity, known issues, and customer tier.

        Args:
            severity: Output from score_severity().
            known_issue: Output from detect_known_issue().
            customer_tier: Customer subscription tier.

        Returns:
            Escalation decision dict:
              - escalate: bool
              - escalation_level: str
              - severity_factors: Dict[str, float]
              - recommended_actions: List[str]
        """
        try:
            severity_score = severity.get("severity_score", 0.2)
            escalation_path = severity.get("escalation_path", "l1_self_service")
            factors = severity.get("factors", {})
            recommended = severity.get("recommended_actions", [])

            escalate = escalation_path not in ("l1_self_service",)

            # Determine escalation level
            level_map = {
                "l1_self_service": "none",
                "l2_specialist": "specialist",
                "l3_engineering": "engineering",
                "emergency": "management",
            }
            escalation_level = level_map.get(escalation_path, "none")

            # Boost for known issues with high severity
            if known_issue.get("known_issue_detected") and known_issue.get("severity") == "high":
                if not escalate:
                    escalate = True
                    escalation_level = "specialist"

            # Boost for enterprise customers
            if customer_tier == "enterprise" and severity_score > 0.4:
                if escalation_level == "specialist":
                    escalation_level = "engineering"

            return {
                "escalate": escalate,
                "escalation_level": escalation_level,
                "severity_factors": factors,
                "recommended_actions": recommended,
            }
        except Exception:
            logger.exception("escalation_decision_failed")
            return {
                "escalate": False,
                "escalation_level": "none",
                "severity_factors": {},
                "recommended_actions": [],
            }

    def _diagnostic_prompt(
        self,
        steps: List[Dict[str, Any]],
        known_issue: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate diagnostic context prompt for the LLM."""
        try:
            parts: List[str] = []

            if known_issue and known_issue.get("known_issue_detected"):
                parts.append(
                    f"This is a known issue ({known_issue.get('issue_id', '')}). "
                    f"Inform the customer that we're aware of it and share the ETA. "
                    f"Still provide the diagnostic steps as they may help in the meantime."
                )

            if steps:
                step_descriptions = [
                    f"Step {s['step']}: {s['action']} (Verify: {s['check']})"
                    for s in steps[:6]  # Limit to 6 steps
                ]
                parts.append(
                    "Walk the customer through these diagnostic steps naturally. "
                    "Present them as suggestions, not commands. "
                    "After each step, ask if it helped before moving to the next. "
                    "Steps: " + "; ".join(step_descriptions)
                )

            return " ".join(parts) if parts else ""

        except Exception:
            return ""

    def _default_known_issue(self) -> Dict[str, Any]:
        """Return default no-known-issue result."""
        return {
            "known_issue_detected": False,
            "issue_id": "",
            "severity": "low",
            "auto_communicate": False,
            "resolution_type": "",
            "eta_hours": 0,
            "message": "",
            "confidence": 0.0,
        }

    def _default_severity(self) -> Dict[str, Any]:
        """Return default low severity result."""
        return {
            "severity_score": 0.2,
            "severity_level": "low",
            "escalation_path": "l1_self_service",
            "factors": {
                "business_impact": 0.3,
                "technical_complexity": 0.3,
                "customer_tier": 0.3,
                "resolution_urgency": 0.3,
            },
            "recommended_actions": ["provide_diagnostics", "self_service_steps"],
        }
