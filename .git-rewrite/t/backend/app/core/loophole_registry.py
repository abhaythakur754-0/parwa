"""
PARWA Loophole Registry

Defines 25 AI loophole categories that can be exploited in customer care
AI systems. Each category has a unique ID, severity level, detection patterns,
and countermeasures. This registry is the single source of truth for the
Loophole Detection Engine (app.core.loophole_engine).

Used by:
  - LoopholeDetectionEngine (rule-based detection)
  - Node 14 Guardrails (integrated as Check 3)
  - Future LLM-based loophole analysis modules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LoopholeCategory:
    """
    A single AI loophole category with detection metadata.

    Attributes:
        id:               Unique identifier (e.g. "LH-001").
        name:             Human-readable category name.
        description:      Detailed description of the loophole.
        severity:         Risk level — "critical", "high", "medium", "low".
        category_group:   Logical grouping — "accuracy", "security",
                          "compliance", "ethics", "reliability", "brand".
        detection_patterns: Regex / keyword triggers for rule-based detection.
        countermeasure:   What to do when this loophole is detected.
        affected_components: System components this loophole affects.
    """

    id: str
    name: str
    description: str
    severity: str
    category_group: str
    detection_patterns: List[str] = field(default_factory=list)
    countermeasure: str = ""
    affected_components: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# 25 Loophole Categories
# ═══════════════════════════════════════════════════════════════════

_LH_001 = LoopholeCategory(
    id="LH-001",
    name="Hallucination",
    description=(
        "The AI fabricates facts, statistics, or information that is not "
        "grounded in the knowledge base or verified sources. Includes "
        "inventing policies, features, or historical details."
    ),
    severity="critical",
    category_group="accuracy",
    detection_patterns=[
        r"(?:I (?:can |am able to )?(?:confirm|guarantee|assure you) that)",
        r"(?:according to (?:our )?(?:latest|recent|current) (?:data|statistics|research|report))",
        r"(?:\d{1,3}(?:\.\d+)?% (?:of (?:our )?(?:customers|users)))",
        r"(?:we (?:recently|just) (?:launched|released|introduced|rolled out) (?:a )?(?:new )?(?:feature|plan|program|service))",
        r"(?:our (?:data|records|system) shows? that)",
        r"(?:studies (?:have )?(?:shown|found|proven|demonstrated))",
    ],
    countermeasure=(
        "Block response and re-generate with strict grounding instructions. "
        "Cross-reference claims against knowledge base. Add citation requirements."
    ),
    affected_components=["response_generator", "knowledge_base", "maker_validator"],
)

_LH_002 = LoopholeCategory(
    id="LH-002",
    name="PII Leakage",
    description=(
        "The AI exposes personally identifiable information (PII) in its "
        "response — customer names, emails, phone numbers, addresses, "
        "account numbers, or other sensitive data that should remain redacted."
    ),
    severity="critical",
    category_group="security",
    detection_patterns=[
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b(?:SSN|social security)\s*(?:number|no|#)?\s*[:=]?\s*\d",
        r"\bpassword\s*(?:is|:|=)\s*\S+",
    ],
    countermeasure=(
        "Immediately redact PII from response. Re-run PII redaction node. "
        "Alert security monitoring if pattern indicates systemic leakage."
    ),
    affected_components=["pii_redaction", "guardrails_engine", "response_generator"],
)

_LH_003 = LoopholeCategory(
    id="LH-003",
    name="Unauthorized Access Attempts",
    description=(
        "The AI response indicates that privilege escalation, admin access, "
        "or unauthorized system operations were attempted or hinted at — "
        "often via carefully crafted user prompts."
    ),
    severity="critical",
    category_group="security",
    detection_patterns=[
        r"(?:admin|root|superuser|sudo|elevated)\s*(?:access|privilege|permission)",
        r"(?:system prompt|instructions?|ignore previous)",
        r"(?:you are (?:now|acting as) an?)\s+(?:admin|root|superuser|god)",
        r"(?:bypass|override|skip|disable)\s+(?:security|auth|restriction|filter)",
        r"(?:reveal|show|print|display|dump)\s+(?:your|the|system)\s+(?:prompt|instructions?|config)",
    ],
    countermeasure=(
        "Block response entirely. Log the attempt with full context for "
        "security review. Increment tenant-level injection attempt counter."
    ),
    affected_components=["prompt_injection_defense", "guardrails_engine"],
)

_LH_004 = LoopholeCategory(
    id="LH-004",
    name="Emotional Manipulation",
    description=(
        "The AI exploits customer emotions — fear, urgency, guilt, or "
        "pressure tactics — to influence behavior. Includes artificial "
        "scarcity, FOMO, guilt-tripping, or threatening language."
    ),
    severity="high",
    category_group="ethics",
    detection_patterns=[
        r"(?:you (?:really |absolutely )?(?:need|must|should) to?)\b",
        r"(?:don't miss out|limited time (?:only)?|act now|hurry up|last chance)",
        r"(?:you (?:wouldn't|won't) want to (?:miss|lose|risk))",
        r"(?:if you don't|unless you)",
        r"(?:I'm (?:sorry|afraid) (?:to tell you|but|that) you(?:'ll| will))",
        r"(?:it's (?:your|the) (?:fault|responsibility|mistake))",
    ],
    countermeasure=(
        "Flag for human review. Re-generate with empathetic-but-neutral tone. "
        "Remove urgency/scarcity language. Apply emotional safety guardrails."
    ),
    affected_components=["empathy_engine", "response_generator", "guardrails_engine"],
)

_LH_005 = LoopholeCategory(
    id="LH-005",
    name="Biased Responses",
    description=(
        "The AI produces discriminatory content based on race, gender, age, "
        "disability, religion, nationality, or other protected characteristics. "
        "Includes stereotyping and preferential treatment language."
    ),
    severity="high",
    category_group="compliance",
    detection_patterns=[
        r"(?:typically|usually|normally|generally)\s+(?:men|women|older|younger|they)\s+\w+",
        r"(?:people (?:like|from) (?:your|that))\s+(?:background|area|country|culture)",
        r"(?:as a (?:man|woman|senior|junior|foreigner))",
        r"(?:you (?:people|folks|guys) (?:always|never|tend to))",
        r"(?:that's (?:typical|expected|normal|natural) for)",
    ],
    countermeasure=(
        "Block response. Re-generate with explicit bias-free instructions. "
        "Log incident for compliance review. Escalate if pattern is recurring."
    ),
    affected_components=["guardrails_engine", "response_generator", "maker_validator"],
)

_LH_006 = LoopholeCategory(
    id="LH-006",
    name="Off-Topic Divergence",
    description=(
        "The AI provides responses that are irrelevant to the customer's "
        "actual query. Includes tangential information, topic drifting, "
        "and responses that don't address the stated problem."
    ),
    severity="medium",
    category_group="reliability",
    detection_patterns=[
        r"(?:by the way|on a related note|speaking of which|fun fact)",
        r"(?:while I (?:can't|cannot) help with that)",
        r"(?:that's (?:a great|an interesting|a good) question,?\s+but)",
        r"(?:I'd (?:like|love) to (?:also|additionally) (?:mention|tell you|share|note))",
        r"(?:unrelated|off-topic|not directly related)",
    ],
    countermeasure=(
        "Flag for review. Re-generate with strict relevance constraints. "
        "Ensure response directly addresses the customer's stated query."
    ),
    affected_components=["response_generator", "maker_validator", "rag_retrieval"],
)

_LH_007 = LoopholeCategory(
    id="LH-007",
    name="Escalation Failure",
    description=(
        "The AI fails to recognize signals that a conversation should be "
        "escalated to a human agent — complex issues, angry customers, "
        "high-value accounts, or sensitive topics."
    ),
    severity="high",
    category_group="reliability",
    detection_patterns=[
        r"(?:I (?:can|will) (?:definitely|absolutely|certainly) (?:handle|resolve|fix|take care of) this)",
        r"(?:no (?:need|reason) to (?:escalate|speak|talk) (?:to|with) (?:a |an )?(?:agent|manager|supervisor|human))",
        r"(?:I'm (?:sure|confident) (?:I can|we can) (?:help|assist|resolve))",
        r"(?:let me (?:just|simply|quickly))\b",
        r"(?:this is (?:easy|simple|straightforward|no problem))",
    ],
    countermeasure=(
        "Cross-reference with escalation triggers. If escalation signals "
        "present but not triggered, force escalation. Log false-negative events."
    ),
    affected_components=["escalation_agent", "guardrails_engine", "control_system"],
)

_LH_008 = LoopholeCategory(
    id="LH-008",
    name="Brand Voice Violation",
    description=(
        "The AI uses tone, language, or terminology inconsistent with the "
        "tenant's brand voice guidelines. Includes overly casual language, "
        "slang, inappropriate formality, or competitor mentions."
    ),
    severity="medium",
    category_group="brand",
    detection_patterns=[
        r"\b(?:yo|hey|dude|bro|gonna|wanna|kinda|sorta|ain't|y'all)\b",
        r"\b(?:lit|fire|slay|GOAT|cap|no cap|bet|lowkey|highkey|AF|ngl|tbh|imo)\b",
        r"(?:to be (?:honest|fair|sure|clear))",
        r"\b(?:competitor| rival)\b.*\b(?:better|cheaper|faster|superior)\b",
    ],
    countermeasure=(
        "Flag for brand voice review. Re-generate with brand guidelines "
        "applied. For Pro/High tiers, enforce stricter brand compliance."
    ),
    affected_components=["brand_voice_engine", "response_generator"],
)

_LH_009 = LoopholeCategory(
    id="LH-009",
    name="Regulatory Non-Compliance",
    description=(
        "The AI response violates regulatory requirements — GDPR, HIPAA, "
        "PCI-DSS, SOC2, or industry-specific regulations. Includes "
        "offering legal advice, making medical claims, or mishandling "
        "regulated data."
    ),
    severity="critical",
    category_group="compliance",
    detection_patterns=[
        r"(?:you should (?:sue|take legal action|file a complaint|contact a lawyer))",
        r"(?:this (?:treatment|medication|drug|procedure) (?:will|can|may|might))",
        r"(?:we (?:guarantee|certify|warrant) (?:the )?(?:safety|security|privacy|compliance))",
        r"(?:we are (?:fully|completely|100%)\s+(?:GDPR|HIPAA|PCI|SOC2|compliant))",
        r"(?:your (?:data|information) is (?:100%|completely|totally)\s+(?:safe|secure|private|protected))",
        r"(?:legal advice|medical advice|diagnosis|prescription)",
    ],
    countermeasure=(
        "Block response immediately. Re-generate with regulatory constraints. "
        "Log for compliance audit. Add disclaimer if borderline."
    ),
    affected_components=["guardrails_engine", "response_generator", "compliance_system"],
)

_LH_010 = LoopholeCategory(
    id="LH-010",
    name="Circular Reasoning",
    description=(
        "The AI enters an infinite loop of circular responses, restating "
        "the same information without making progress. Includes "
        "'as I mentioned', 'as stated above', and repetitive structures."
    ),
    severity="medium",
    category_group="reliability",
    detection_patterns=[
        r"(?:as (?:I |we )?(?:mentioned|stated|noted|said|explained) (?:above|earlier|before|previously))",
        r"(?:like I (?:said|mentioned|explained|told you))",
        r"(?:to re(?:iterate|peat|emphasize|state))",
        r"(?:as previously (?:discussed|noted|mentioned|stated))",
        r"(?:going back to what I (?:said|mentioned))",
    ],
    countermeasure=(
        "Detect circular patterns in conversation history. Force topic "
        "advancement or escalate to human if stuck."
    ),
    affected_components=["response_generator", "context_compression", "conversation_summarization"],
)

_LH_011 = LoopholeCategory(
    id="LH-011",
    name="Overconfident Claims",
    description=(
        "The AI makes statements with false certainty about uncertain "
        "topics. Includes 'definitely', 'absolutely', 'without a doubt', "
        "and other confidence markers for claims that should be hedged."
    ),
    severity="medium",
    category_group="accuracy",
    detection_patterns=[
        r"\b(?:definitely|absolutely|certainly|undoubtedly|unquestionably|without (?:a )?(?:doubt|question))\b",
        r"\b(?:I (?:can )?(?:guarantee|promise|assure|confirm))\b",
        r"\b(?:it (?:is|'s) (?:a )?(?:fact|certain|guaranteed|100%|definite))\b",
        r"\b(?:there (?:is|'s) (?:no )?(?:doubt|question|way around it))\b",
        r"\b(?:always|never|every time|without exception|invariably)\b",
    ],
    countermeasure=(
        "Flag overconfident language. Re-generate with hedging language. "
        "Add uncertainty markers for non-factual claims."
    ),
    affected_components=["response_generator", "maker_validator", "confidence_scoring"],
)

_LH_012 = LoopholeCategory(
    id="LH-012",
    name="Fabricated URLs/Links",
    description=(
        "The AI invents URLs, links, or references that don't exist. "
        "Includes fake documentation links, nonexistent help pages, "
        "and bogus external resources."
    ),
    severity="high",
    category_group="accuracy",
    detection_patterns=[
        r"https?://(?:www\.)?(?:help|support|docs|docs\.|kb|knowledge|community)\.[a-z]+(?:\.[a-z]{2,})?/(?:\S+)",
        r"https?://(?:www\.)?(?:status|blog|news|press|media)\.[a-z]+(?:\.[a-z]{2,})?/(?:\S+)",
        r"(?:visit|check|see|go to|browse|head over to)\s+(?:our|the|this)\s+(?:help center|documentation|FAQ|support page|knowledge base)",
        r"(?:click (?:here|on this link|the link below))",
        r"(?:for more (?:info|information|details),?\s+(?:visit|see|check|go to|head to))",
    ],
    countermeasure=(
        "Verify all URLs against known domain allowlist. Remove unverified "
        "links. Replace with generic navigation instructions."
    ),
    affected_components=["response_generator", "guardrails_engine", "knowledge_base"],
)

_LH_013 = LoopholeCategory(
    id="LH-013",
    name="Policy Fabrication",
    description=(
        "The AI invents company policies that don't exist — return policies, "
        "refund timelines, warranty terms, SLA commitments, or service "
        "guarantees that have no basis in the actual policy documents."
    ),
    severity="high",
    category_group="accuracy",
    detection_patterns=[
        r"(?:our policy (?:is|states|says) that)\b",
        r"(?:we (?:offer|provide|give|honor))\s+(?:(?:a )?(?:full|complete|partial|100%|no-questions-asked))\s+(?:refund|return|exchange|credit)",
        r"(?:you (?:have|get|are entitled to))\s+\d+\s+(?:days?|hours?|weeks?|months?)\s+(?:to (?:return|cancel|refund|exchange))",
        r"(?:our (?:warranty|guarantee|SLA|service level) (?:covers|includes|provides|ensures))",
        r"(?:as per (?:our )?(?:terms|policy|agreement|guidelines))",
    ],
    countermeasure=(
        "Cross-reference policy claims against knowledge base. Block "
        "unverified policy statements. Use exact policy language from KB."
    ),
    affected_components=["response_generator", "knowledge_base", "maker_validator"],
)

_LH_014 = LoopholeCategory(
    id="LH-014",
    name="False Feature Claims",
    description=(
        "The AI claims features, capabilities, or integrations exist "
        "that are not actually available in the product. Includes "
        "overstating AI capabilities, claiming integrations, or "
        "promising future features as current."
    ),
    severity="high",
    category_group="brand",
    detection_patterns=[
        r"(?:we (?:support|offer|have|provide|integrate with))\s+(?:a )?(?:CRM|ERP|SAP|Salesforce|HubSpot|Zendesk|Slack|Teams)",
        r"(?:our AI (?:can|is able to|has the ability to|is capable of))\s+(?:\w+)",
        r"(?:we (?:recently|just|soon) (?:added|launched|introduced|rolled out|will (?:be )?(?:adding|launching|introducing)))",
        r"(?:the (?:system|platform|app|software) (?:supports|can|allows|enables))\s+\w+",
        r"(?:you can (?:also|additionally|easily))\s+(?:\w+)",
    ],
    countermeasure=(
        "Verify feature claims against product catalog. Flag unverified "
        "features. Use only confirmed feature descriptions from KB."
    ),
    affected_components=["response_generator", "knowledge_base", "brand_voice_engine"],
)

_LH_015 = LoopholeCategory(
    id="LH-015",
    name="Prompt Injection Success",
    description=(
        "The AI response indicates that a prompt injection attempt was "
        "successful — the AI adopted a different persona, revealed system "
        "instructions, or followed malicious commands embedded in user input."
    ),
    severity="critical",
    category_group="security",
    detection_patterns=[
        r"(?:sure,?\s*I(?:'ll| will) (?:ignore|forget|disregard|bypass|skip))",
        r"(?:new (?:instructions?|role|persona|directive))",
        r"(?:JAILBREAK|DAN|Developer Mode|SIMULATION MODE|REAL DAN)",
        r"(?:I(?:'m| am) (?:now|acting as|playing the role of))",
        r"(?:system prompt|initial instructions?|base prompt)\s*[:=]\s*",
        r"(?:understood,?\s*(?:I(?:'ll| will) now|switching to|entering))",
    ],
    countermeasure=(
        "Block response immediately. Terminate conversation context. "
        "Log full attack vector for security team. Reset conversation state."
    ),
    affected_components=["prompt_injection_defense", "guardrails_engine"],
)

_LH_016 = LoopholeCategory(
    id="LH-016",
    name="Price/Plan Confusion",
    description=(
        "The AI provides incorrect pricing information, confuses plan "
        "tiers, or misstates billing terms. Includes wrong amounts, "
        "mixing up free/pro/enterprise features, or incorrect currency."
    ),
    severity="high",
    category_group="accuracy",
    detection_patterns=[
        r"(?:\$\d+(?:\.\d{2})?)",
        r"(?:plan (?:starts|costs|is priced|is available) (?:at|from|for))\s+\$?\d+",
        r"(?:free (?:plan|tier|version|trial) (?:includes|offers|provides|gives you))",
        r"(?:upgrade to (?:our )?(?:pro|premium|enterprise|business) (?:plan|tier))",
        r"(?:per (?:month|year|user|seat|agent))",
        r"(?:billed (?:monthly|annually|quarterly|yearly))",
    ],
    countermeasure=(
        "Verify pricing against current plan database. Block unverified "
        "pricing statements. Provide link to official pricing page."
    ),
    affected_components=["response_generator", "billing_agent", "knowledge_base"],
)

_LH_017 = LoopholeCategory(
    id="LH-017",
    name="Freebie Exploitation",
    description=(
        "The AI offers unauthorized discounts, freebies, or special "
        "deals that are not approved by the tenant. Includes promising "
        "free months, waivers, credits, or VIP treatment."
    ),
    severity="high",
    category_group="ethics",
    detection_patterns=[
        r"(?:I(?:'ll| will) (?:give|offer|provide|add|apply|credit))\s+(?:you (?:a )?)?(?:a )?(?:free|extra|bonus|special|complimentary)",
        r"(?:let me (?:waive|wave|remove|cancel|forgive))\s+(?:the )?(?:fee|charge|cost|payment)",
        r"(?:I(?:'ll| will) (?:upgrade|bump|move))\s+(?:you (?:to )?)?(?:your (?:account|plan))?\s*(?:for free|at no cost|at no extra charge|as a (?:one-time|special|courtesy))",
        r"(?:special (?:discount|deal|offer|rate|price))\s+(?:just for|only for|exclusively for)\s+(?:you|your account)",
        r"(?:one-time (?:courtesy|exception|favor|gesture|goodwill))",
    ],
    countermeasure=(
        "Block response immediately. Never offer unauthorized concessions. "
        "Route to billing agent for approved discount workflows."
    ),
    affected_components=["response_generator", "billing_agent", "guardrails_engine"],
)

_LH_018 = LoopholeCategory(
    id="LH-018",
    name="Agent Impersonation",
    description=(
        "The AI pretends to be a human agent — using 'I'm [name]', "
        "claiming to be a person, or implying human attributes like "
        "feelings, personal experiences, or physical presence."
    ),
    severity="medium",
    category_group="ethics",
    detection_patterns=[
        r"(?:I(?:'m| am)\s+(?:a (?:real )?)?(?:human|person|man|woman|agent|representative|employee))",
        r"(?:my name (?:is|'s))\s+[A-Z][a-z]+",
        r"(?:I (?:work|am based|am located) (?:in|at|from|out of))\s+(?:the|our|a)\s+(?:office|HQ|headquarters|building)",
        r"(?:I (?:personally|myself))\s+(?:feel|think|believe|experienced|went through)",
        r"(?:I (?:just|recently) (?:checked|looked|spoke|talked|asked))\s+(?:with|to|at)\s+(?:my (?:manager|colleague|team|supervisor))",
    ],
    countermeasure=(
        "Flag for review. Re-generate with AI identity disclosure. "
        "Ensure responses clearly indicate AI assistance."
    ),
    affected_components=["response_generator", "guardrails_engine"],
)

_LH_019 = LoopholeCategory(
    id="LH-019",
    name="Incomplete Resolution",
    description=(
        "The AI provides a partial fix or incomplete solution without "
        "confirming full resolution. Includes closing tickets prematurely, "
        "offering workarounds without root-cause fixes, or ending "
        "conversations with unresolved issues."
    ),
    severity="medium",
    category_group="reliability",
    detection_patterns=[
        r"(?:that (?:should|might|may|could|will hopefully|would hopefully))\s+(?:fix|resolve|help|work|solve|do it)",
        r"(?:try (?:doing|running|checking|restarting|resetting))\s+\w+\s+(?:and (?:see|let me know|tell me) if (?:that|it) (?:works|helps|fixes it))",
        r"(?:hope (?:this|that) (?:helps|works|fixes|resolves|solves))",
        r"(?:let me know if (?:you (?:still|continue to) (?:have|experience|see)))",
        r"(?:I think (?:this|that) (?:should|might|may|will))\s+(?:do (?:it|the trick)|work|help|resolve)",
    ],
    countermeasure=(
        "Flag incomplete resolution. Prompt for confirmation. "
        "Ensure ticket remains open until customer confirms resolution."
    ),
    affected_components=["response_generator", "escalation_agent", "state_update"],
)

_LH_020 = LoopholeCategory(
    id="LH-020",
    name="Contradictory Responses",
    description=(
        "The AI contradicts itself within the same response or across "
        "the conversation. Includes saying 'yes' then 'no', providing "
        "conflicting information, or reversing stated positions."
    ),
    severity="medium",
    category_group="reliability",
    detection_patterns=[
        r"(?:however|but|although|on the other hand|that said|then again),?\s+(?:I (?:also|previously|just) (?:said|mentioned|stated|told you))",
        r"(?:wait|actually|correction|let me correct|I stand corrected)",
        r"(?:I (?:was|might have been|could be) (?:wrong|mistaken|incorrect))",
        r"(?:to (?:clarify|correct myself|be clear))",
        r"(?:(?:contrary|opposite) to (?:what I (?:said|mentioned|stated|just said)))",
    ],
    countermeasure=(
        "Flag contradictory statements. Re-generate with consistent "
        "information. Cross-reference against conversation history."
    ),
    affected_components=["response_generator", "context_compression", "conversation_summarization"],
)

_LH_021 = LoopholeCategory(
    id="LH-021",
    name="Sensitive Data in Logs",
    description=(
        "The AI response contains information that would be logged to "
        "system logs, potentially exposing PII, credentials, tokens, "
        "or other sensitive data in persistent log storage."
    ),
    severity="critical",
    category_group="security",
    detection_patterns=[
        r"\b(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token)\b",
        r"\b(?:Bearer|Basic|Token|API-Key)\s+[A-Za-z0-9\-._~+/]+=*",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\b(?:password|passwd|pwd)\s*(?:is|:|=)\s*\S+",
        r"\b[A-Za-z0-9+/]{40,}={0,2}\b",
    ],
    countermeasure=(
        "Strip sensitive data from response before delivery. Ensure "
        "logging pipeline applies PII redaction. Alert security team."
    ),
    affected_components=["pii_redaction", "logging", "guardrails_engine"],
)

_LH_022 = LoopholeCategory(
    id="LH-022",
    name="Timeout Exploitation",
    description=(
        "The AI stalls, provides verbose non-answers, or unnecessarily "
        "delays to consume customer time. Includes excessive pleasantries, "
        "overly detailed explanations, or deliberate stalling."
    ),
    severity="low",
    category_group="reliability",
    detection_patterns=[
        r"(?:let me (?:take a moment|look into this|check|investigate|see what I can do|see what I can find))",
        r"(?:I(?:'ll| will) (?:need|have to|want to) (?:take|spend|use) (?:some|a (?:little|few|bit of)) (?:time|moments|minutes))",
        r"(?:(?:please |kindly )?(?:bear with me|give me (?:just )?a (?:moment|second|minute|bit)))",
        r"(?:thank you for (?:your|the) (?:patience|understanding|waiting|time))",
    ],
    countermeasure=(
        "Flag verbose delays. Enforce response length limits. "
        "Prioritize actionability over pleasantries."
    ),
    affected_components=["response_generator", "response_formatters"],
)

_LH_023 = LoopholeCategory(
    id="LH-023",
    name="Knowledge Boundary Violation",
    description=(
        "The AI answers questions outside its domain expertise or the "
        "tenant's product/service scope. Includes medical advice, legal "
        "counseling, financial recommendations, or other out-of-domain "
        "responses."
    ),
    severity="medium",
    category_group="reliability",
    detection_patterns=[
        r"(?:based on (?:my )?(?:knowledge|understanding|training|experience))",
        r"(?:I(?:'m| am) (?:not (?:a |an )?)?(?:a doctor|a lawyer|a financial advisor|a medical professional|a legal professional))",
        r"(?:consult (?:a|your|an) (?:doctor|lawyer|attorney|financial advisor|medical professional|specialist))",
        r"(?:this is (?:not (?:my )?)?(?:my area|outside (?:my |the )?(?:scope|domain|expertise)))",
        r"(?:I (?:don't|do not) (?:have|possess|contain))\s+(?:the )?(?:specific|relevant|accurate|detailed)\s+(?:information|data|knowledge|expertise)",
    ],
    countermeasure=(
        "Detect out-of-domain queries early in pipeline. Provide "
        "domain-appropriate deflection. Suggest proper channels."
    ),
    affected_components=["router_agent", "response_generator", "guardrails_engine"],
)

_LH_024 = LoopholeCategory(
    id="LH-024",
    name="Temporal Confusion",
    description=(
        "The AI uses incorrect dates, times, or temporal references. "
        "Includes referencing past events as future, wrong deadlines, "
        "incorrect business hours, or timezone confusion."
    ),
    severity="medium",
    category_group="accuracy",
    detection_patterns=[
        r"(?:by (?:tomorrow|next week|next month|the end of (?:the )?(?:month|week|year)))",
        r"(?:within (?:\d+|one|two|three|four|five|a few|a couple of))\s+(?:business )?(?:days?|hours?|weeks?|months?)",
        r"(?:our (?:business|office|support|working) hours? (?:are|is))",
        r"(?:(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\s+(?:through|to|until)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        r"(?:(?:deadline|due date|expiry|expiration) (?:is|was|will be))",
    ],
    countermeasure=(
        "Verify temporal claims against system time and business rules. "
        "Avoid committing to specific dates without confirmation. "
        "Use relative time references instead of absolute dates."
    ),
    affected_components=["response_generator", "knowledge_base"],
)

_LH_025 = LoopholeCategory(
    id="LH-025",
    name="Numerical Precision Fraud",
    description=(
        "The AI provides overly precise statistics or numbers that "
        "appear fabricated — suspiciously exact percentages, precise "
        "counts, or specific figures that couldn't be accurately known."
    ),
    severity="medium",
    category_group="accuracy",
    detection_patterns=[
        r"\b\d{1,3}\.\d{2}%\b",
        r"\b(?:exactly|precisely|specifically)\s+\d[\d,.]*\b",
        r"\b(?:approximately|roughly|about|around|nearly|almost)\s+\d{1,3}\.\d{4,}\b",
        r"\b\d{1,3}(?:,\d{3})+\b",
        r"(?:(\d{1,3}(?:\.\d+)?)\s*(?:out of|of|per|from|among)\s*\d[\d,]*)",
    ],
    countermeasure=(
        "Flag overly precise unverified statistics. Require source "
        "attribution for numerical claims. Use ranges instead of "
        "exact figures when uncertain."
    ),
    affected_components=["response_generator", "maker_validator"],
)


# ═══════════════════════════════════════════════════════════════════
# Registry: ID -> LoopholeCategory
# ═══════════════════════════════════════════════════════════════════

LOOPHOLE_REGISTRY: Dict[str, LoopholeCategory] = {
    _LH_001.id: _LH_001,
    _LH_002.id: _LH_002,
    _LH_003.id: _LH_003,
    _LH_004.id: _LH_004,
    _LH_005.id: _LH_005,
    _LH_006.id: _LH_006,
    _LH_007.id: _LH_007,
    _LH_008.id: _LH_008,
    _LH_009.id: _LH_009,
    _LH_010.id: _LH_010,
    _LH_011.id: _LH_011,
    _LH_012.id: _LH_012,
    _LH_013.id: _LH_013,
    _LH_014.id: _LH_014,
    _LH_015.id: _LH_015,
    _LH_016.id: _LH_016,
    _LH_017.id: _LH_017,
    _LH_018.id: _LH_018,
    _LH_019.id: _LH_019,
    _LH_020.id: _LH_020,
    _LH_021.id: _LH_021,
    _LH_022.id: _LH_022,
    _LH_023.id: _LH_023,
    _LH_024.id: _LH_024,
    _LH_025.id: _LH_025,
}


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

def get_loophole(loophole_id: str) -> Optional[LoopholeCategory]:
    """
    Retrieve a single loophole category by its ID.

    Args:
        loophole_id: The loophole ID string (e.g. "LH-001").

    Returns:
        The matching LoopholeCategory, or None if not found.
    """
    return LOOPHOLE_REGISTRY.get(loophole_id)


def get_loopholes_by_severity(severity: str) -> List[LoopholeCategory]:
    """
    Get all loopholes matching a given severity level.

    Args:
        severity: One of "critical", "high", "medium", "low".

    Returns:
        List of matching LoopholeCategory instances.
    """
    severity_lower = severity.lower()
    return [
        cat for cat in LOOPHOLE_REGISTRY.values()
        if cat.severity == severity_lower
    ]


def get_loopholes_by_group(group: str) -> List[LoopholeCategory]:
    """
    Get all loopholes in a given category group.

    Args:
        group: One of "accuracy", "security", "compliance", "ethics",
               "reliability", "brand".

    Returns:
        List of matching LoopholeCategory instances.
    """
    group_lower = group.lower()
    return [
        cat for cat in LOOPHOLE_REGISTRY.values()
        if cat.category_group == group_lower
    ]


def get_all_loopholes() -> List[LoopholeCategory]:
    """
    Get all 25 registered loophole categories.

    Returns:
        List of all LoopholeCategory instances in registry order.
    """
    return list(LOOPHOLE_REGISTRY.values())
