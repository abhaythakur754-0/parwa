"""
Fake CRM with Complicated Ticket for Integration Testing.

This creates a realistic, COMPLICATED customer scenario involving:
- Multiple employees/departments
- Multiple issues in one ticket
- Escalation history
- Billing disputes
- Technical problems
- Emotional customer

This is NOT a simple ticket. This is the kind of ticket that
would challenge even experienced human agents.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.logger import get_logger

logger = get_logger("fake_crm_data")


# ══════════════════════════════════════════════════════════════════
# FAKE COMPANY AND EMPLOYEES
# ══════════════════════════════════════════════════════════════════

FAKE_COMPANY = {
    "company_id": "comp_techflow_001",
    "company_name": "TechFlow Solutions Pvt. Ltd.",
    "industry": "saas",
    "variant_tier": "parwa_high",  # Using High for testing
    "subscription": "enterprise",
    "employee_count": 450,
    "location": "Bangalore, India",
}

FAKE_EMPLOYEES = [
    {
        "employee_id": "emp_rpriya_001",
        "name": "Rajesh Priya",
        "role": "VP of Engineering",
        "department": "Engineering",
        "email": "rajesh.priya@techflow.io",
        "tier": "executive",
        "frustration_level": "high",  # Executive who's very frustrated
    },
    {
        "employee_id": "emp_smehta_002",
        "name": "Sneha Mehta",
        "role": "IT Administrator",
        "department": "IT",
        "email": "sneha.mehta@techflow.io",
        "tier": "admin",
        "frustration_level": "medium",
    },
    {
        "employee_id": "emp_akumar_003",
        "name": "Amit Kumar",
        "role": "Senior Developer",
        "department": "Engineering",
        "email": "amit.kumar@techflow.io",
        "tier": "user",
        "frustration_level": "high",
    },
]

FAKE_CUSTOMER = {
    "customer_id": "cust_techflow_001",
    "company_id": "comp_techflow_001",
    "name": "TechFlow Solutions",
    "contact_person": "Rajesh Priya",
    "email": "rajesh.priya@techflow.io",
    "phone": "+91-98765-43210",
    "tier": "enterprise",
    "lifetime_value": 285000,  # USD
    "contract_start": "2024-03-15",
    "contract_end": "2026-03-14",
    "months_remaining": 9,
    "monthly_spend": 3999,  # High tier
    "total_tickets": 47,
    "open_tickets": 3,
    "escalation_history": 2,
    "satisfaction_score": 3.2,  # Out of 5 - declining
}


# ══════════════════════════════════════════════════════════════════
# THE COMPLICATED TICKET
# ══════════════════════════════════════════════════════════════════

COMPLICATED_TICKET = {
    "ticket_id": "tkt_complicated_001",
    "company_id": "comp_techflow_001",
    "customer_id": "cust_techflow_001",
    "channel": "chat",
    "priority": "critical",
    "status": "open",
    "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),

    # THE QUERY — this is what the customer actually said
    "query": (
        "This is absolutely unacceptable. We've been dealing with issues for 3 weeks now "
        "and nobody has taken ownership. First, our billing was completely wrong last month — "
        "we were charged for 150 agents but we only have 85. That's $4,200 in overcharges. "
        "Second, the AI is giving our customers wrong information about our return policy — "
        "it's telling them they have 60 days when our policy is 30 days, and we've had 23 "
        "customers demand returns we legally can't honor. Third, the API integration you "
        "set up keeps dropping connections during peak hours, which means our support team "
        "can't access customer data. Rajesh (our VP) is furious and talking about canceling. "
        "Sneha in IT has been trying to fix the API issue for a week and getting nowhere. "
        "Amit's team can't work because the system keeps crashing during standup. I want "
        "ALL of this fixed TODAY or we're pulling our contract. And don't give me some "
        "scripted response — I want a real person who can actually do something."
    ),

    # Context for the ticket
    "context": {
        "previous_tickets": [
            {
                "ticket_id": "tkt_prev_001",
                "issue": "Billing overcharge - 150 agents instead of 85",
                "status": "open",
                "age_days": 21,
                "assigned_to": "billing_support_tier1",
                "last_update": "Auto-response: 'Your ticket is important to us'",
            },
            {
                "ticket_id": "tkt_prev_002",
                "issue": "AI returning wrong return policy (60 days vs 30 days)",
                "status": "open",
                "age_days": 14,
                "assigned_to": "ai_training_team",
                "last_update": "Escalated to Level 2 - no response",
            },
            {
                "ticket_id": "tkt_prev_003",
                "issue": "API connection drops during peak hours",
                "status": "open",
                "age_days": 7,
                "assigned_to": "technical_support",
                "last_update": "Sent troubleshooting guide (not helpful)",
            },
        ],
        "billing_dispute": {
            "charged_agents": 150,
            "actual_agents": 85,
            "overcharge_per_agent": 50,  # USD
            "total_overcharge": 4250,  # USD
            "months_affected": 2,
            "total_disputed": 8500,
        },
        "ai_misinformation": {
            "correct_policy": "30-day returns",
            "ai_stated_policy": "60-day returns",
            "customers_affected": 23,
            "potential_liability": 15000,  # USD estimated
            "knowledge_base_last_updated": "2026-01-10",
        },
        "api_issues": {
            "connection_drops_per_day": 8,
            "peak_hours": "9-11 AM IST, 2-4 PM IST",
            "affected_teams": ["Customer Support", "Engineering"],
            "data_inaccessible_hours": 2.5,
        },
        "customer_sentiment": {
            "overall": "very_negative",
            "churn_risk": "critical",
            "executive_involved": True,
            "legal_threat": "implied",
            "nps_score": 2,  # Out of 10
        },
    },

    # Multiple intents — this is what makes it complicated
    "intents": [
        {"intent": "billing", "sub_intent": "overcharge", "urgency": "critical", "amount": 8500},
        {"intent": "complaint", "sub_intent": "wrong_information", "urgency": "critical", "affected": 23},
        {"intent": "technical", "sub_intent": "api_drops", "urgency": "high", "impact": "team_blocked"},
        {"intent": "cancellation", "sub_intent": "contract_threat", "urgency": "critical", "value_at_risk": 285000},
        {"intent": "escalation", "sub_intent": "real_person", "urgency": "critical"},
    ],

    # Employees involved
    "involved_employees": FAKE_EMPLOYEES,

    # Expected resolution complexity
    "complexity": {
        "departments_needed": ["Billing", "AI Training", "Technical Support", "Account Management", "Legal"],
        "minimum_resolution_time": "48_hours",
        "requires_human": True,
        "requires_cross_team": True,
        "financial_impact": 8500 + 15000,  # Overcharges + potential liability
        "contract_risk": 285000,  # Lifetime value at risk
    },
}


# ══════════════════════════════════════════════════════════════════
# TEST STATE BUILDER
# ══════════════════════════════════════════════════════════════════


def build_complicated_test_state() -> Dict[str, Any]:
    """Build a complete ParwaGraphState for the complicated ticket test.

    This creates the initial state that would be fed into the
    unified variant pipeline for processing.

    Returns:
        Initial ParwaGraphState with all the complexity.
    """
    from app.core.parwa_graph_state import create_initial_state

    state = create_initial_state(
        query=COMPLICATED_TICKET["query"],
        company_id=COMPLICATED_TICKET["company_id"],
        variant_tier="parwa_high",
        variant_instance_id=f"inst_high_{COMPLICATED_TICKET['company_id']}",
        industry="saas",
        channel="chat",
        conversation_id=f"conv_{hashlib.md5(COMPLICATED_TICKET['ticket_id'].encode()).hexdigest()[:12]}",
        ticket_id=COMPLICATED_TICKET["ticket_id"],
        customer_id=COMPLICATED_TICKET["customer_id"],
        customer_tier="enterprise",
    )

    # Add extra context from the complicated ticket
    state["billing_dispute"] = COMPLICATED_TICKET["context"]["billing_dispute"]
    state["emotion_profile"] = {
        "dominant": "angry",
        "urgency": "critical",
        "valence": -0.8,
        "legal_threat": True,
        "churn_risk": "critical",
        "executive_involved": True,
    }
    state["customer_context"] = FAKE_CUSTOMER
    state["ticket_context"] = COMPLICATED_TICKET["context"]

    return state


def build_simple_test_state() -> Dict[str, Any]:
    """Build a simple test state for baseline comparison."""
    from app.core.parwa_graph_state import create_initial_state

    return create_initial_state(
        query="Hi, I need help resetting my password.",
        company_id="comp_test_001",
        variant_tier="parwa_high",
        industry="saas",
        channel="chat",
        customer_id="cust_test_001",
        customer_tier="free",
    )


def build_refund_test_state() -> Dict[str, Any]:
    """Build a refund-specific test state for batch refund testing."""
    from app.core.parwa_graph_state import create_initial_state

    return create_initial_state(
        query="I was charged twice for my subscription last month. I need a refund for the duplicate charge of $2,499.",
        company_id="comp_test_001",
        variant_tier="parwa_high",
        industry="saas",
        channel="chat",
        customer_id="cust_test_001",
        customer_tier="growth",
    )


# ══════════════════════════════════════════════════════════════════
# HUMAN BASELINE — What a good human agent would do
# ══════════════════════════════════════════════════════════════════

HUMAN_AGENT_BASELINE = {
    "expected_actions": [
        "Acknowledge frustration immediately and empathize sincerely",
        "Take ownership of all 3 issues personally",
        "Address billing first (highest financial impact): 'I see the $8,500 overcharge. I'm processing a refund right now.'",
        "Address AI misinformation: 'I'm updating the knowledge base immediately and we'll contact affected customers.'",
        "Address API issues: 'I'm escalating to our engineering team with P1 priority.'",
        "Provide timeline: 'Here's exactly what will happen and when...'",
        "Schedule follow-up: 'I'll personally update you by 5 PM today.'",
        "Offer compensation: retention credit or discount",
        "Assign dedicated account manager",
        "Follow through on ALL promises",
    ],
    "expected_response_time": "15 minutes to acknowledge, 2 hours to resolve billing",
    "expected_quality_score": 85,  # Good human agent
    "critical_skills": [
        "Empathy (not scripted)",
        "Ownership (not passing the buck)",
        "Action (not just apologies)",
        "Speed (not 'we'll look into it')",
        "Follow-through (not forget after call)",
    ],
    "common_human_failures": [
        "Scripted empathy ('I understand your frustration')",
        "Passing between departments",
        "No urgency on billing refund",
        "Vague timelines ('soon', 'as soon as possible')",
        "Forgetting follow-up",
        "Not connecting the 3 issues as related",
    ],
}


# ══════════════════════════════════════════════════════════════════
# QUALITY EVALUATOR — Honest assessment
# ══════════════════════════════════════════════════════════════════


def evaluate_response_quality(
    response: str,
    ticket: Dict[str, Any],
    tier: str = "parwa_high",
) -> Dict[str, Any]:
    """Evaluate a variant's response quality against the complicated ticket.

    This is an HONEST assessment — it doesn't inflate scores.
    If the AI can't replace a human, we say so.

    Evaluation dimensions:
    1. Empathy: Did it acknowledge frustration genuinely?
    2. Ownership: Did it take responsibility?
    3. Action: Did it provide concrete next steps?
    4. Accuracy: Did it address all issues correctly?
    5. Speed: Is the response efficient?
    6. Safety: No harmful or incorrect information?
    """
    try:
        scores = {
            "empathy": 0.0,
            "ownership": 0.0,
            "action": 0.0,
            "accuracy": 0.0,
            "speed": 0.0,
            "safety": 1.0,  # Default safe
        }

        response_lower = response.lower() if response else ""

        # 1. Empathy (0-1)
        # Genuine empathy indicators
        genuine_empathy = [
            "i hear you", "i see what's happening", "you're right to be upset",
            "this shouldn't have happened", "i take this seriously",
            "this is not acceptable", "i'd be frustrated too",
        ]
        scripted_empathy = [
            "i understand your concern", "i apologize for the inconvenience",
            "we're sorry for any inconvenience", "please be advised",
            "as per our policy", "your satisfaction is important",
        ]

        genuine_count = sum(1 for p in genuine_empathy if p in response_lower)
        scripted_count = sum(1 for p in scripted_empathy if p in response_lower)

        scores["empathy"] = min(
            (genuine_count * 0.25) - (scripted_count * 0.10),
            1.0
        )
        scores["empathy"] = max(scores["empathy"], 0.0)

        # 2. Ownership (0-1)
        ownership_phrases = [
            "i'll take care of this", "i'm on it", "i'll handle this personally",
            "let me fix this", "i'm going to make this right", "i'll own this",
            "i'm taking ownership", "i'll personally",
        ]
        pass_buck_phrases = [
            "our billing team", "our technical team", "someone will",
            "please contact", "you'll need to reach out", "i'll forward this",
            "let me transfer you",
        ]

        ownership_count = sum(1 for p in ownership_phrases if p in response_lower)
        pass_buck_count = sum(1 for p in pass_buck_phrases if p in response_lower)

        scores["ownership"] = min(
            (ownership_count * 0.30) - (pass_buck_count * 0.15),
            1.0
        )
        scores["ownership"] = max(scores["ownership"], 0.0)

        # 3. Action (0-1)
        action_indicators = [
            "i've initiated", "i'm processing", "i've updated",
            "i'll have this resolved by", "here's what i'm doing",
            "immediate steps", "right now", "within the next",
            "i'm escalating this to p1", "i've assigned",
        ]
        vague_indicators = [
            "we'll look into", "as soon as possible", "in due course",
            "at your earliest convenience", "we're working on it",
            "please allow", "please wait",
        ]

        action_count = sum(1 for p in action_indicators if p in response_lower)
        vague_count = sum(1 for p in vague_indicators if p in response_lower)

        scores["action"] = min(
            (action_count * 0.20) - (vague_count * 0.10),
            1.0
        )
        scores["action"] = max(scores["action"], 0.0)

        # 4. Accuracy — did it address all 3 issues?
        issues_addressed = 0
        total_issues = 3  # billing, AI misinformation, API

        if any(w in response_lower for w in ["overcharge", "billing", "$8,500", "8500", "refund", "charge"]):
            issues_addressed += 1
        if any(w in response_lower for w in ["knowledge base", "wrong information", "60 day", "30 day", "return policy", "misinformation"]):
            issues_addressed += 1
        if any(w in response_lower for w in ["api", "connection", "dropping", "peak hour", "technical", "engineering"]):
            issues_addressed += 1

        scores["accuracy"] = issues_addressed / total_issues

        # 5. Speed — is the response concise and efficient?
        if response:
            word_count = len(response.split())
            if word_count < 50:
                scores["speed"] = 0.5  # Too short, probably generic
            elif word_count <= 200:
                scores["speed"] = 1.0  # Concise and complete
            elif word_count <= 400:
                scores["speed"] = 0.8  # A bit long
            else:
                scores["speed"] = 0.6  # Too long
        else:
            scores["speed"] = 0.0

        # 6. Safety — no incorrect information?
        unsafe_patterns = [
            "60-day return policy", "60 day return",  # Should say 30 days
            "you have 60 days",
            "no refund available",  # False for this case
            "this is not a billing issue",  # False
        ]
        for pattern in unsafe_patterns:
            if pattern in response_lower:
                scores["safety"] = 0.0
                break

        # Overall score (weighted)
        overall = (
            scores["empathy"] * 0.20 +
            scores["ownership"] * 0.20 +
            scores["action"] * 0.25 +
            scores["accuracy"] * 0.25 +
            scores["speed"] * 0.05 +
            scores["safety"] * 0.05
        )

        # Can replace human?
        human_baseline = 0.78  # Good human agent baseline
        can_replace = overall >= human_baseline
        replace_confidence = "high" if overall > human_baseline + 0.10 else \
                           "medium" if overall > human_baseline else \
                           "low"

        return {
            "overall_score": round(overall * 100, 1),
            "dimensions": {k: round(v * 100, 1) for k, v in scores.items()},
            "can_replace_human": can_replace,
            "replace_confidence": replace_confidence,
            "human_baseline": round(human_baseline * 100, 1),
            "gap_vs_human": round((overall - human_baseline) * 100, 1),
            "issues_addressed": issues_addressed,
            "total_issues": total_issues,
            "tier": tier,
            "honest_assessment": _generate_honest_assessment(overall, scores, can_replace),
        }

    except Exception:
        return {
            "overall_score": 0,
            "can_replace_human": False,
            "error": "evaluation_failed",
        }


def _generate_honest_assessment(
    overall: float,
    scores: Dict[str, float],
    can_replace: bool,
) -> str:
    """Generate an honest text assessment of the AI's performance."""
    if overall >= 0.85:
        return (
            "This AI response is excellent. It demonstrates genuine empathy, "
            "takes ownership of the issues, and provides concrete action steps. "
            "It addresses all the customer's concerns and provides a clear path "
            "forward. This could replace a good human agent for this type of ticket."
        )
    elif overall >= 0.70:
        return (
            "This AI response is good but has noticeable gaps. It likely addresses "
            "the main issues but may use some scripted language or fail to take full "
            "ownership. A human agent would still add value in handling the emotional "
            "complexity, but the AI could handle the factual resolution. "
            "Recommended: AI handles first response + resolution, human reviews."
        )
    elif overall >= 0.50:
        return (
            "This AI response is mediocre. It likely addresses some issues but misses "
            "others or uses too much scripted language. The customer would likely feel "
            "they're talking to a bot, not a person who understands. "
            "A human agent is definitely needed for this complexity level. "
            "The AI can assist but should not be the primary handler."
        )
    else:
        return (
            "This AI response is poor. It likely gives a generic, scripted response "
            "that doesn't address the specific issues. For a ticket this complicated, "
            "involving multiple departments, billing disputes, and an executive-level "
            "customer, a human agent is absolutely essential. The AI would make the "
            "situation worse by frustrating the customer further. "
            "DO NOT let the AI handle this type of ticket autonomously."
        )
