"""
Emotional Intelligence Engine — EI Layer + Service Recovery Playbooks.

Improvement Target: Complaint Handling 65% → 82% automation.

Components:
  1. Emotion Profiler: Multi-dimensional emotion detection beyond simple
     keyword matching. Detects primary/secondary emotions, intensity,
     escalation trajectory, and emotional needs.
  2. Service Recovery Playbook: Decision tree for complaint resolution
     based on emotion profile + complaint severity. Auto-selects the
     appropriate recovery strategy (apology + fix, apology + credit,
     escalation to senior, etc.).
  3. De-escalation Prompts: Pre-built prompt additions that guide the
     LLM to de-escalate tense situations while maintaining brand voice.

Architecture:
  Called from smart_enrichment node to build emotion context before
  generation. Called from auto_action node to trigger recovery actions
  (credits, escalations, follow-ups).

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("emotional_intelligence")


# ══════════════════════════════════════════════════════════════════
# EMOTION TAXONOMY
# ══════════════════════════════════════════════════════════════════

# Primary emotions with intensity weight (higher = more distressed)
PRIMARY_EMOTIONS: Dict[str, Dict[str, Any]] = {
    "angry": {
        "intensity": 0.9,
        "keywords": [
            "angry", "furious", "outraged", "mad", "livid", "unacceptable",
            "ridiculous", "appalling", "disgusted", "worst", "horrible",
            "terrible", "absurd", "joke", "scam", "cheat", "fraud",
        ],
        "needs": ["acknowledgment", "validation", "concrete_action"],
        "risk": "high",
    },
    "frustrated": {
        "intensity": 0.7,
        "keywords": [
            "frustrated", "annoyed", "irritated", "fed up", "can't stand",
            "sick of", "had enough", "not working", "broken", "again",
            "still not", "repeatedly", "multiple times", "every time",
        ],
        "needs": ["acknowledgment", "explanation", "resolution"],
        "risk": "medium",
    },
    "disappointed": {
        "intensity": 0.6,
        "keywords": [
            "disappointed", "let down", "expected better", "not what i expected",
            "underwhelmed", "unsatisfied", "unhappy", "not satisfied",
            "doesn't work", "not worth", "waste",
        ],
        "needs": ["empathy", "correction", "compensation"],
        "risk": "medium",
    },
    "anxious": {
        "intensity": 0.65,
        "keywords": [
            "worried", "anxious", "concerned", "nervous", "uncertain",
            "what if", "will i", "afraid", "scared", "hope not",
            "please help", "don't know what to do",
        ],
        "needs": ["reassurance", "clarity", "timeline"],
        "risk": "low",
    },
    "confused": {
        "intensity": 0.4,
        "keywords": [
            "confused", "don't understand", "unclear", "lost", "help me",
            "can't figure out", "what does this mean", "how do i",
            "where is", "can't find",
        ],
        "needs": ["clarification", "guidance", "patience"],
        "risk": "low",
    },
    "sad": {
        "intensity": 0.55,
        "keywords": [
            "sad", "heartbroken", "devastated", "upset", "crying",
            "depressed", "hopeless", "missed", "lost", "gone",
        ],
        "needs": ["empathy", "support", "gentle_guidance"],
        "risk": "medium",
    },
    "betrayed": {
        "intensity": 0.95,
        "keywords": [
            "betrayed", "lied to", "misled", "deceived", "false promise",
            "bait and switch", "not what was promised", "trust", "loyalty",
        ],
        "needs": ["validation", "accountability", "restoration"],
        "risk": "critical",
    },
}

# Secondary emotions (layered on top of primary)
SECONDARY_EMOTIONS: Dict[str, Dict[str, Any]] = {
    "urgent": {
        "keywords": [
            "urgent", "asap", "emergency", "immediately", "right now",
            "critical", "deadline", "time-sensitive", "running out of time",
        ],
        "amplifier": 1.3,
    },
    "repeated_issue": {
        "keywords": [
            "again", "still", "not fixed", "same problem", "multiple times",
            "repeatedly", "second time", "third time", "still waiting",
        ],
        "amplifier": 1.4,
    },
    "public_threat": {
        "keywords": [
            "review", "social media", "twitter", "reddit", "facebook",
            "blog", "youtube", "expose", "tell everyone", "warn others",
        ],
        "amplifier": 1.5,
    },
    "financial_impact": {
        "keywords": [
            "money", "cost", "charged", "refund", "payment", "billing",
            "expensive", "overpriced", "lost money", "can't afford",
        ],
        "amplifier": 1.2,
    },
}


# ══════════════════════════════════════════════════════════════════
# SERVICE RECOVERY PLAYBOOKS
# ══════════════════════════════════════════════════════════════════

RECOVERY_PLAYBOOKS: Dict[str, Dict[str, Any]] = {
    "minor_inconvenience": {
        "trigger": {"max_intensity": 0.4, "risk": "low"},
        "strategy": "acknowledge_and_resolve",
        "actions": ["acknowledge_issue", "provide_resolution", "confirm_satisfaction"],
        "compensation": None,
        "escalation": False,
        "prompt_addition": (
            "The customer has a minor concern. Address it directly and concisely. "
            "Show understanding, provide a clear solution, and confirm they're satisfied."
        ),
    },
    "moderate_complaint": {
        "trigger": {"max_intensity": 0.7, "risk": "medium"},
        "strategy": "empathize_explain_compensate",
        "actions": [
            "acknowledge_issue", "validate_feelings", "explain_what_happened",
            "provide_resolution", "offer_small_compensation", "confirm_satisfaction",
        ],
        "compensation": "small_credit",
        "escalation": False,
        "prompt_addition": (
            "The customer is moderately upset. Lead with empathy, then explain what "
            "happened and why. Offer a resolution and a small goodwill gesture (e.g., "
            "discount on next purchase, free shipping). Make them feel heard."
        ),
    },
    "serious_complaint": {
        "trigger": {"max_intensity": 0.85, "risk": "high"},
        "strategy": "apologize_fix_compensate_escalate",
        "actions": [
            "sincere_apology", "acknowledge_impact", "immediate_fix",
            "offer_significant_compensation", "schedule_follow_up",
            "escalate_to_senior",
        ],
        "compensation": "significant_credit",
        "escalation": True,
        "prompt_addition": (
            "The customer is very upset. This is a serious complaint. Start with a "
            "sincere apology that acknowledges the specific impact. Take immediate "
            "action to fix the issue. Offer meaningful compensation (credit, refund, "
            "free upgrade). Promise follow-up and deliver on it."
        ),
    },
    "critical_complaint": {
        "trigger": {"max_intensity": 1.0, "risk": "critical"},
        "strategy": "senior_escalation_full_recovery",
        "actions": [
            "sincere_apology", "acknowledge_breach_of_trust", "immediate_escalation",
            "full_remediation", "generous_compensation", "personal_follow_up",
            "management_notification",
        ],
        "compensation": "full_credit_or_refund",
        "escalation": True,
        "prompt_addition": (
            "This is a critical situation. The customer feels betrayed or deeply wronged. "
            "Acknowledge the breach of trust directly. Escalate immediately to a senior "
            "team member. Offer full remediation and generous compensation. Promise "
            "personal follow-up from management. This is a relationship-saving moment."
        ),
    },
}

# De-escalation phrases to inject into LLM prompts
DE_ESCALATION_PROMPTS: Dict[str, str] = {
    "acknowledge_first": (
        "Start by explicitly acknowledging the customer's feelings before "
        "addressing the issue. Use phrases like 'I hear you' or 'I understand "
        "how you feel' or 'You're absolutely right to feel that way.'"
    ),
    "avoid_minimizing": (
        "NEVER minimize the customer's concern. Avoid phrases like 'it's just' "
        "or 'simply' or 'all you need to do.' Their concern is valid regardless "
        "of how it appears from the technical side."
    ),
    "own_the_mistake": (
        "If the company made an error, own it directly. Use 'We made a mistake' "
        "or 'We got this wrong' rather than passive voice like 'An error occurred.'"
    ),
    "give_control_back": (
        "Give the customer control over the resolution. Offer choices: "
        "'Would you prefer A or B?' This reduces helplessness and restores agency."
    ),
    "set_clear_expectations": (
        "Be specific about timelines and next steps. Replace 'soon' with "
        "'within 2 hours.' Replace 'we'll look into it' with 'I'll personally "
        "investigate and email you by 5 PM today.'"
    ),
}


class EmotionalIntelligenceEngine:
    """Emotional Intelligence Engine for complaint handling automation.

    Provides:
      - Emotion profiling (primary + secondary emotions, intensity, trajectory)
      - Service recovery playbook selection
      - De-escalation prompt generation
      - Recovery action recommendations

    Usage:
        engine = EmotionalIntelligenceEngine()
        profile = engine.profile_emotion(query, empathy_score, empathy_flags)
        playbook = engine.select_recovery_playbook(profile)
        prompts = engine.generate_de_escalation_prompts(profile)
    """

    def __init__(self) -> None:
        """Initialize the EI engine."""
        self._compiled_primary_patterns: Dict[str, List[re.Pattern]] = {}
        self._compiled_secondary_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        try:
            for emotion, config in PRIMARY_EMOTIONS.items():
                patterns = []
                for kw in config["keywords"]:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_primary_patterns[emotion] = patterns

            for emotion, config in SECONDARY_EMOTIONS.items():
                patterns = []
                for kw in config["keywords"]:
                    if " " in kw:
                        patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
                    else:
                        patterns.append(re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                self._compiled_secondary_patterns[emotion] = patterns

        except Exception:
            logger.exception("ei_pattern_compilation_failed")

    def profile_emotion(
        self,
        query: str,
        empathy_score: float = 0.5,
        empathy_flags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a multi-dimensional emotion profile from the customer query.

        Args:
            query: The customer's message.
            empathy_score: Pre-computed empathy score from empathy_check node.
            empathy_flags: Pre-computed empathy flags from empathy_check node.

        Returns:
            Emotion profile dict with:
              - primary_emotion: str
              - secondary_emotions: List[str]
              - intensity: float (0.0-1.0)
              - risk_level: str (low/medium/high/critical)
              - emotional_needs: List[str]
              - escalation_trajectory: str (stable/escalating/critical)
              - de_escalation_priority: float (0.0-1.0)
              - matched_keywords: Dict[str, List[str]]
        """
        try:
            if not query:
                return self._default_profile()

            query_lower = query.lower()

            # Detect primary emotion
            primary_emotion = "neutral"
            primary_intensity = 0.3
            primary_risk = "low"
            primary_needs: List[str] = []
            matched_primary: Dict[str, List[str]] = {}

            for emotion, config in PRIMARY_EMOTIONS.items():
                matches = []
                for pattern in self._compiled_primary_patterns.get(emotion, []):
                    found = pattern.findall(query_lower)
                    if found:
                        matches.extend(found)

                if matches:
                    matched_primary[emotion] = matches
                    # Select the emotion with highest intensity if multiple match
                    if config["intensity"] > primary_intensity:
                        primary_emotion = emotion
                        primary_intensity = config["intensity"]
                        primary_risk = config["risk"]
                        primary_needs = config["needs"]

            # Detect secondary emotions (amplifiers)
            secondary_emotions: List[str] = []
            amplifier = 1.0
            matched_secondary: Dict[str, List[str]] = {}

            for emotion, config in SECONDARY_EMOTIONS.items():
                matches = []
                for pattern in self._compiled_secondary_patterns.get(emotion, []):
                    found = pattern.findall(query_lower)
                    if found:
                        matches.extend(found)

                if matches:
                    secondary_emotions.append(emotion)
                    amplifier *= config["amplifier"]
                    matched_secondary[emotion] = matches

            # Adjust intensity with amplifier (cap at 1.0)
            adjusted_intensity = min(1.0, primary_intensity * amplifier)

            # Factor in empathy score (lower empathy = more distressed)
            if empathy_score < 0.3:
                adjusted_intensity = min(1.0, adjusted_intensity * 1.2)
            elif empathy_score > 0.6:
                adjusted_intensity = max(0.1, adjusted_intensity * 0.9)

            # Determine escalation trajectory
            trajectory = "stable"
            if adjusted_intensity > 0.8 or "repeated_issue" in secondary_emotions:
                trajectory = "escalating"
            if adjusted_intensity > 0.9 or "public_threat" in secondary_emotions:
                trajectory = "critical"

            # Determine de-escalation priority
            de_escalation_priority = 0.0
            if adjusted_intensity > 0.5:
                de_escalation_priority = min(1.0, adjusted_intensity * 1.1)

            # Adjust risk level based on trajectory
            if trajectory == "critical":
                primary_risk = "critical"
            elif trajectory == "escalating" and primary_risk == "medium":
                primary_risk = "high"

            # Also factor in empathy flags
            if empathy_flags:
                flag_risk_map = {
                    "angry": "high",
                    "frustrated": "medium",
                    "urgent": "medium",
                }
                for flag in empathy_flags:
                    if flag in flag_risk_map:
                        flag_risk = flag_risk_map[flag]
                        risk_order = ["low", "medium", "high", "critical"]
                        if risk_order.index(flag_risk) > risk_order.index(primary_risk):
                            primary_risk = flag_risk

            return {
                "primary_emotion": primary_emotion,
                "secondary_emotions": secondary_emotions,
                "intensity": round(adjusted_intensity, 3),
                "risk_level": primary_risk,
                "emotional_needs": primary_needs,
                "escalation_trajectory": trajectory,
                "de_escalation_priority": round(de_escalation_priority, 3),
                "matched_keywords": {**matched_primary, **matched_secondary},
                "empathy_score_input": empathy_score,
            }

        except Exception:
            logger.exception("emotion_profiling_failed")
            return self._default_profile()

    def select_recovery_playbook(
        self,
        emotion_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Select the appropriate service recovery playbook based on emotion profile.

        Args:
            emotion_profile: Output from profile_emotion().

        Returns:
            Recovery playbook dict with:
              - strategy: str
              - actions: List[str]
              - compensation: Optional[str]
              - escalation: bool
              - prompt_addition: str
              - playbook_name: str
        """
        try:
            intensity = emotion_profile.get("intensity", 0.3)
            risk = emotion_profile.get("risk_level", "low")

            # Match against playbook triggers
            for playbook_name, playbook in RECOVERY_PLAYBOOKS.items():
                trigger = playbook["trigger"]
                max_intensity = trigger["max_intensity"]
                trigger_risk = trigger["risk"]

                # Check if this playbook matches
                risk_order = ["low", "medium", "high", "critical"]
                risk_meets = risk_order.index(risk) <= risk_order.index(trigger_risk)

                if intensity <= max_intensity and risk_meets:
                    return {
                        **playbook,
                        "playbook_name": playbook_name,
                        "matched_intensity": intensity,
                        "matched_risk": risk,
                    }

            # Fallback: serious complaint playbook
            fallback = RECOVERY_PLAYBOOKS["serious_complaint"]
            return {
                **fallback,
                "playbook_name": "serious_complaint",
                "matched_intensity": intensity,
                "matched_risk": risk,
            }

        except Exception:
            logger.exception("playbook_selection_failed")
            return {
                "strategy": "acknowledge_and_resolve",
                "actions": ["acknowledge_issue", "provide_resolution"],
                "compensation": None,
                "escalation": False,
                "prompt_addition": "Address the customer's concern directly.",
                "playbook_name": "fallback",
                "matched_intensity": 0.0,
                "matched_risk": "unknown",
            }

    def generate_de_escalation_prompts(
        self,
        emotion_profile: Dict[str, Any],
    ) -> str:
        """Generate de-escalation prompt additions for the LLM.

        Args:
            emotion_profile: Output from profile_emotion().

        Returns:
            Combined de-escalation prompt string to append to the system prompt.
        """
        try:
            intensity = emotion_profile.get("intensity", 0.3)
            trajectory = emotion_profile.get("escalation_trajectory", "stable")
            needs = emotion_profile.get("emotional_needs", [])

            prompts: List[str] = []

            # Always add acknowledge_first if intensity > 0.3
            if intensity > 0.3:
                prompts.append(DE_ESCALATION_PROMPTS["acknowledge_first"])

            # Add avoid_minimizing for moderate+ intensity
            if intensity > 0.5:
                prompts.append(DE_ESCALATION_PROMPTS["avoid_minimizing"])

            # Add own_the_mistake if trajectory is escalating
            if trajectory in ("escalating", "critical"):
                prompts.append(DE_ESCALATION_PROMPTS["own_the_mistake"])

            # Add give_control_back if needs include validation or restoration
            if "validation" in needs or "restoration" in needs:
                prompts.append(DE_ESCALATION_PROMPTS["give_control_back"])

            # Add set_clear_expectations always
            prompts.append(DE_ESCALATION_PROMPTS["set_clear_expectations"])

            return "\n\n".join(prompts) if prompts else ""

        except Exception:
            logger.exception("de_escalation_prompt_generation_failed")
            return ""

    def get_recovery_actions(
        self,
        emotion_profile: Dict[str, Any],
        playbook: Dict[str, Any],
        classification: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get automated recovery actions to execute.

        Args:
            emotion_profile: Output from profile_emotion().
            playbook: Output from select_recovery_playbook().
            classification: Classification result from classify node.

        Returns:
            List of action dicts, each with:
              - action_type: str
              - action_data: Dict
              - priority: str (low/medium/high/critical)
              - automated: bool (whether it can be executed without human)
        """
        try:
            actions: List[Dict[str, Any]] = []
            risk = emotion_profile.get("risk_level", "low")
            playbook_actions = playbook.get("actions", [])

            for action in playbook_actions:
                if action == "sincere_apology":
                    actions.append({
                        "action_type": "send_apology",
                        "action_data": {
                            "risk_level": risk,
                            "template": "sincere_apology",
                        },
                        "priority": "high",
                        "automated": True,
                    })

                elif action == "offer_small_compensation":
                    actions.append({
                        "action_type": "apply_compensation",
                        "action_data": {
                            "compensation_type": "small_credit",
                            "suggested_amount": "10%_discount_or_free_shipping",
                        },
                        "priority": "medium",
                        "automated": True,
                    })

                elif action == "offer_significant_compensation":
                    actions.append({
                        "action_type": "apply_compensation",
                        "action_data": {
                            "compensation_type": "significant_credit",
                            "suggested_amount": "full_refund_or_50%_credit",
                        },
                        "priority": "high",
                        "automated": True,
                    })

                elif action == "schedule_follow_up":
                    actions.append({
                        "action_type": "schedule_followup",
                        "action_data": {
                            "delay_hours": 24,
                            "channel": "email",
                        },
                        "priority": "medium",
                        "automated": True,
                    })

                elif action == "escalate_to_senior":
                    actions.append({
                        "action_type": "escalate",
                        "action_data": {
                            "escalation_level": "senior_agent",
                            "reason": f"complaint_{risk}_risk",
                            "emotion_intensity": emotion_profile.get("intensity", 0.0),
                        },
                        "priority": "high",
                        "automated": True,
                    })

                elif action == "immediate_escalation":
                    actions.append({
                        "action_type": "escalate",
                        "action_data": {
                            "escalation_level": "manager",
                            "reason": "critical_complaint",
                            "emotion_intensity": emotion_profile.get("intensity", 0.0),
                            "immediate": True,
                        },
                        "priority": "critical",
                        "automated": True,
                    })

                elif action == "personal_follow_up":
                    actions.append({
                        "action_type": "schedule_followup",
                        "action_data": {
                            "delay_hours": 4,
                            "channel": "phone",
                            "from_level": "manager",
                        },
                        "priority": "high",
                        "automated": True,
                    })

                elif action == "management_notification":
                    actions.append({
                        "action_type": "notify",
                        "action_data": {
                            "notify_level": "management",
                            "reason": "critical_complaint_requires_oversight",
                        },
                        "priority": "critical",
                        "automated": True,
                    })

            return actions

        except Exception:
            logger.exception("recovery_action_generation_failed")
            return []

    def assess_sentiment_escalation(
        self,
        emotion_profile: Dict[str, Any],
        classification: Optional[Dict[str, Any]] = None,
        conversation_turns: int = 1,
    ) -> Dict[str, Any]:
        """Assess if sentiment requires escalation beyond standard handling.

        Args:
            emotion_profile: Output from profile_emotion().
            classification: Classification result.
            conversation_turns: Number of turns in this conversation.

        Returns:
            Sentiment escalation dict:
              - escalation_needed: bool
              - escalation_level: str (none/supervisor/manager/director)
              - trigger_reason: str
              - priority_score: float (0.0-1.0)
        """
        try:
            intensity = emotion_profile.get("intensity", 0.3)
            trajectory = emotion_profile.get("escalation_trajectory", "stable")
            risk = emotion_profile.get("risk_level", "low")

            escalation_needed = False
            escalation_level = "none"
            trigger_reason = "standard_handling"
            priority_score = intensity * 0.5

            # Critical intensity always escalates
            if intensity > 0.85:
                escalation_needed = True
                escalation_level = "manager"
                trigger_reason = "critical_emotional_intensity"
                priority_score = 0.9
            # High intensity + escalating trajectory
            elif intensity > 0.7 and trajectory in ("escalating", "critical"):
                escalation_needed = True
                escalation_level = "supervisor"
                trigger_reason = "escalating_emotional_state"
                priority_score = 0.7
            # Repeated issue (multiple turns) with moderate intensity
            elif conversation_turns >= 3 and intensity > 0.5:
                escalation_needed = True
                escalation_level = "supervisor"
                trigger_reason = "repeated_issue_escalation"
                priority_score = 0.65
            # Public threat always escalates to manager
            secondary = emotion_profile.get("secondary_emotions", [])
            if "public_threat" in secondary:
                escalation_needed = True
                escalation_level = "manager"
                trigger_reason = "public_exposure_risk"
                priority_score = max(priority_score, 0.85)

            return {
                "escalation_needed": escalation_needed,
                "escalation_level": escalation_level,
                "trigger_reason": trigger_reason,
                "priority_score": round(priority_score, 3),
            }
        except Exception:
            logger.exception("sentiment_escalation_assessment_failed")
            return {
                "escalation_needed": False,
                "escalation_level": "none",
                "trigger_reason": "assessment_failed",
                "priority_score": 0.0,
            }

    def resolve_complaint(
        self,
        emotion_profile: Dict[str, Any],
        playbook: Dict[str, Any],
        classification: Optional[Dict[str, Any]] = None,
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Generate deep complaint resolution with strategy and confidence.

        Args:
            emotion_profile: Output from profile_emotion().
            playbook: Output from select_recovery_playbook().
            classification: Classification result.
            customer_tier: Customer subscription tier.

        Returns:
            Complaint resolution dict:
              - resolution_strategy: str
              - de_escalation_applied: bool
              - compensation_type: str
              - follow_up_scheduled: bool
              - escalation_triggered: bool
              - resolution_confidence: float
        """
        try:
            strategy = playbook.get("strategy", "acknowledge_and_resolve")
            intensity = emotion_profile.get("intensity", 0.3)
            risk = emotion_profile.get("risk_level", "low")

            # Determine compensation
            compensation = "none"
            if intensity > 0.7:
                compensation = playbook.get("compensation", "small_credit") or "small_credit"
            elif intensity > 0.5:
                compensation = "small_credit"

            # De-escalation needed for moderate+ intensity
            de_escalation = intensity > 0.4

            # Escalation for high/critical risk
            escalation = risk in ("high", "critical") or playbook.get("escalation", False)

            # Follow-up for serious+ complaints
            follow_up = intensity > 0.5 or escalation

            # Resolution confidence based on automation level
            confidence = 0.9  # Base confidence for automated resolution
            if escalation:
                confidence *= 0.7  # Lower confidence when escalation needed
            if customer_tier in ("growth", "enterprise"):
                confidence *= 0.95  # Slightly lower for high-value customers
            if intensity > 0.85:
                confidence *= 0.8  # Very upset = less confident auto-resolution

            return {
                "resolution_strategy": strategy,
                "de_escalation_applied": de_escalation,
                "compensation_type": compensation,
                "follow_up_scheduled": follow_up,
                "escalation_triggered": escalation,
                "resolution_confidence": round(min(1.0, confidence), 3),
            }
        except Exception:
            logger.exception("complaint_resolution_failed")
            return {
                "resolution_strategy": "acknowledge_and_resolve",
                "de_escalation_applied": False,
                "compensation_type": "none",
                "follow_up_scheduled": False,
                "escalation_triggered": False,
                "resolution_confidence": 0.0,
            }

    def _default_profile(self) -> Dict[str, Any]:
        """Return a default neutral emotion profile."""
        return {
            "primary_emotion": "neutral",
            "secondary_emotions": [],
            "intensity": 0.3,
            "risk_level": "low",
            "emotional_needs": ["acknowledgment", "information"],
            "escalation_trajectory": "stable",
            "de_escalation_priority": 0.0,
            "matched_keywords": {},
            "empathy_score_input": 0.5,
        }
