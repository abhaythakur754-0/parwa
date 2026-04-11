"""
Variant AI Capability Matrix Service (SG-01).

Single source of truth for mapping 170+ AI features to
variant tiers (mini_parwa, parwa, parwa_high) with
instance-level override support.

BC-001: All queries filtered by company_id.
BC-007: Feature gating per variant tier.
BC-008: Graceful degradation.
BC-013: Single source of truth (FEATURE_REGISTRY).
"""

import json
from datetime import datetime, timezone

from database.base import SessionLocal
from database.models.variant_engine import VariantAICapability
from app.exceptions import ParwaBaseError

# ══════════════════════════════════════════════════════════════════
# FEATURE REGISTRY — Single Source of Truth (BC-013)
# ══════════════════════════════════════════════════════════════════
# Each feature maps to minimum variant tier required:
#   mini_parwa  = 1
#   parwa       = 2
#   parwa_high  = 3
# A variant can access all features at or below its level.

VARIANT_LEVELS = {
    "mini_parwa": 1,
    "parwa": 2,
    "parwa_high": 3,
}

# Feature definitions: {feature_id: {
#   "name": str, "category": str, "min_level": int,
#   "technique_tier": str|None, "config": dict
# }}
FEATURE_REGISTRY: dict[str, dict] = {}

# ── Routing Features (Day 2-3) ─────────────────────────────────
_routing = [
    ("F-054", "Smart Router (3-tier LLM)",
     "routing", 1, None, {}),
    ("SG-03", "Variant-Specific Model Access",
     "routing", 1, None, {}),
    ("F-055", "Query Pre-Processing",
     "routing", 1, None, {}),
    ("F-056", "Context Window Manager",
     "routing", 2, None, {}),
    ("F-057", "Multi-Turn Memory Manager",
     "routing", 2, None, {}),
    ("F-058", "Conversation Thread Manager",
     "routing", 1, None, {}),
    ("SG-06", "Cross-Variant Routing Rules",
     "routing", 2, None, {}),
    ("SG-11", "Cross-Variant Ticket Routing Logic",
     "routing", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _routing:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Classification Features ────────────────────────────────────
_classification = [
    ("F-060", "Intent Classification", "classification", 1, None, {}),
    ("F-061", "Sentiment Analysis", "classification", 1, None, {}),
    ("F-062", "Urgency Detection", "classification", 1, None, {}),
    ("F-063", "Language Detection", "classification", 1, None, {}),
    ("F-064", "Spam Detection", "classification", 1, None, {}),
    ("F-065", "Topic Classification", "classification", 2, None, {}),
    ("F-066", "Customer Tier Classification",
     "classification", 2, None, {}),
    ("F-067", "Complexity Scoring", "classification", 2, None, {}),
    ("F-068", "Multi-Intent Detection", "classification", 3, None, {}),
    ("F-069", "Emotion Analysis", "classification", 3, None, {}),
    ("F-070", " sarcasm Detection", "classification", 3, None, {}),
    ("F-071", "Domain Classification", "classification", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _classification:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── RAG Features ───────────────────────────────────────────────
_rag = [
    ("F-080", "Knowledge Base Retrieval", "rag", 1, None, {}),
    ("F-081", "Document Chunking", "rag", 1, None, {}),
    ("F-082", "Embedding Generation", "rag", 1, None, {}),
    ("F-083", "Semantic Search", "rag", 1, None, {}),
    ("F-084", "Hybrid Search (BM25+Vector)",
     "rag", 2, None, {}),
    ("F-085", "Re-Ranking", "rag", 2, None, {}),
    ("F-086", "Context Compression", "rag", 2, None, {}),
    ("F-087", "Source Citation", "rag", 2, None, {}),
    ("F-088", "Multi-Source Fusion", "rag", 3, None, {}),
    ("F-089", "Knowledge Graph Retrieval", "rag", 3, None, {}),
    ("F-090", "Temporal-Aware Retrieval", "rag", 3, None, {}),
    ("F-091", "Cross-Lingual Retrieval", "rag", 3, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _rag:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Confidence Scoring ─────────────────────────────────────────
_confidence = [
    ("F-059", "Confidence Scoring Engine",
     "monitoring", 1, None, {}),
    ("SG-04", "Variant-Specific Confidence Thresholds",
     "monitoring", 1,
     None, {"mini_parwa": 95, "parwa": 85, "parwa_high": 75}),
]
for fid, name, cat, lvl, tt, cfg in _confidence:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Response Generation ────────────────────────────────────────
_response = [
    ("F-100", "Response Generation", "response", 1, None, {}),
    ("F-101", "Response Personalization", "response", 2, None, {}),
    ("F-102", "Response Templating", "response", 1, None, {}),
    ("F-103", "Multi-Language Response", "response", 2, None, {}),
    ("F-104", "Tone Adjustment", "response", 2, None, {}),
    ("F-105", "Brand Voice Enforcement", "response", 2, None, {}),
    ("F-106", "Response A/B Testing", "response", 3, None, {}),
    ("F-107", "Human-Handoff Trigger", "response", 1, None, {}),
    ("F-108", "Escalation Response", "response", 2, None, {}),
    ("F-109", "Follow-Up Generation", "response", 3, None, {}),
    ("F-110", "Suggested Reply Queue", "response", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _response:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Technique Features (Tier 1 — all variants) ────────────────
_tier1 = [
    ("F-140", "Chain-of-Thought (CoT)", "technique", 1, "tier_1", {}),
    ("F-141", "ReAct", "technique", 1, "tier_1", {}),
    ("F-142", "Few-Shot Prompting", "technique", 1, "tier_1", {}),
]
for fid, name, cat, lvl, tt, cfg in _tier1:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Technique Features (Tier 2 — parwa+) ──────────────────────
_tier2 = [
    ("F-143", "Generative Self-Training (GST)",
     "technique", 2, "tier_2", {}),
    ("F-144", "Chain-of-Review-and-Plan (CRP)",
     "technique", 2, "tier_2", {}),
    ("F-145", "Tree-of-Thought (ToT)",
     "technique", 2, "tier_2", {}),
    ("F-146", "Step-Back Prompting",
     "technique", 2, "tier_2", {}),
    ("F-147", "Least-to-Most Prompting",
     "technique", 2, "tier_2", {}),
    ("F-148", "Self-Consistency",
     "technique", 2, "tier_2", {}),
    ("F-149", "Reflexion",
     "technique", 2, "tier_2", {}),
]
for fid, name, cat, lvl, tt, cfg in _tier2:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Technique Features (Tier 3 — parwa_high only) ─────────────
_tier3 = [
    ("F-150", "CLARA (Contrastive Learning)",
     "technique", 3, "tier_3", {}),
    ("F-151", "Graph-of-Thought (GoT)",
     "technique", 3, "tier_3", {}),
    ("F-152", "Uncertainty-over-Threshold (UoT)",
     "technique", 3, "tier_3", {}),
    ("F-153", "Tournament-of-Thoughts (ToT-v2)",
     "technique", 3, "tier_3", {}),
    ("F-154", "Reverse Thinking",
     "technique", 3, "tier_3", {}),
    ("F-155", "Meta-Prompting",
     "technique", 3, "tier_3", {}),
]
for fid, name, cat, lvl, tt, cfg in _tier3:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Guardrail Features ─────────────────────────────────────────
_guardrails = [
    ("F-160", "Prompt Injection Detection",
     "guardrail", 1, None, {}),
    ("F-161", "PII Redaction", "guardrail", 1, None, {}),
    ("F-162", "Content Policy Filter", "guardrail", 1, None, {}),
    ("F-163", "Toxicity Detection", "guardrail", 1, None, {}),
    ("F-164", "Hallucination Detection",
     "guardrail", 2, None, {}),
    ("F-165", "Bias Detection", "guardrail", 2, None, {}),
    ("F-166", "Fact-Checking", "guardrail", 3, None, {}),
    ("F-167", "Output Guardrails", "guardrail", 1, None, {}),
    ("F-168", "Input Sanitization", "guardrail", 1, None, {}),
    ("F-169", "Rate Limit Guard", "guardrail", 2, None, {}),
    ("F-170", "Budget Guard (Token)",
     "guardrail", 1, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _guardrails:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Monitoring / Ops Features ──────────────────────────────────
_monitoring = [
    ("F-180", "Performance Dashboard", "monitoring", 1, None, {}),
    ("F-181", "Token Usage Tracking", "monitoring", 1, None, {}),
    ("F-182", "Latency Monitoring", "monitoring", 1, None, {}),
    ("F-183", "Error Rate Monitoring", "monitoring", 1, None, {}),
    ("F-184", "Cost Analytics", "monitoring", 2, None, {}),
    ("F-185", "Model Performance Comparison",
     "monitoring", 3, None, {}),
    ("F-186", "A/B Test Analytics", "monitoring", 3, None, {}),
    ("F-187", "Alerting System", "monitoring", 2, None, {}),
    ("F-188", "Audit Trail", "monitoring", 1, None, {}),
    ("F-189", "Pipeline State Recovery",
     "monitoring", 2, None, {}),
    ("F-190", "Real-Time Metrics Streaming",
     "monitoring", 3, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _monitoring:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Orchestration Features ─────────────────────────────────────
_orchestration = [
    ("SG-37", "Unlimited Variant Instance Architecture",
     "orchestration", 1, None, {}),
    ("SG-38", "Variant Orchestration Layer",
     "orchestration", 2, None, {}),
    ("SG-21", "Task Decomposition",
     "orchestration", 2, None, {}),
    ("SG-22", "Agent Assignment Strategy",
     "orchestration", 2, None, {}),
    ("SG-05", "Feature Entitlement Middleware",
     "orchestration", 1, None, {}),
    ("F-200", "LangGraph Workflow Engine",
     "orchestration", 1, None, {}),
    ("F-201", "Celery Task Distribution",
     "orchestration", 1, None, {}),
    ("F-202", "Redis State Management",
     "orchestration", 1, None, {}),
    ("F-203", "Workload Balancer",
     "orchestration", 2, None, {}),
    ("F-204", "Auto-Scaling Orchestration",
     "orchestration", 3, None, {}),
    ("F-205", "Pipeline Checkpointing",
     "orchestration", 2, None, {}),
    ("F-206", "Cross-Instance Context Sharing",
     "orchestration", 3, None, {}),
    ("F-207", "Fallback Chain Manager",
     "orchestration", 2, None, {}),
    ("F-208", "Dead Letter Queue Handler",
     "orchestration", 2, None, {}),
    ("F-209", "Workflow Versioning",
     "orchestration", 3, None, {}),
    ("F-210", "Multi-Tenant Queue Isolation",
     "orchestration", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _orchestration:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Signal Extraction Features ─────────────────────────────────
_signals = [
    ("F-220", "Intent Signal Extraction",
     "routing", 1, None, {}),
    ("F-221", "Sentiment Signal Extraction",
     "routing", 1, None, {}),
    ("F-222", "Complexity Signal", "routing", 1, None, {}),
    ("F-223", "Monetary Value Signal",
     "routing", 2, None, {}),
    ("F-224", "Customer Tier Signal",
     "routing", 2, None, {}),
    ("F-225", "Turn Count Signal", "routing", 1, None, {}),
    ("F-226", "Previous Response Status Signal",
     "routing", 1, None, {}),
    ("F-227", "Reasoning Loop Detection",
     "routing", 2, None, {}),
    ("F-228", "Resolution Path Count",
     "routing", 2, None, {}),
    ("F-229", "Query Breadth Signal", "routing", 2, None, {}),
    ("SG-13", "Signal Extraction Layer (detailed)",
     "routing", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _signals:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── GSD / State Machine Features ──────────────────────────────
_gsd = [
    ("F-053", "GSD State Engine", "orchestration", 2, None, {}),
    ("F-240", "Multi-Step Conversation Handler",
     "orchestration", 2, None, {}),
    ("F-241", "State Persistence", "orchestration", 2, None, {}),
    ("F-242", "State Recovery", "orchestration", 3, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _gsd:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Additional Situation Gap Features ──────────────────────────
_gaps = [
    ("SG-01", "Variant AI Capability Matrix",
     "orchestration", 1, None, {}),
    ("SG-02", "Variant Config Inheritance",
     "orchestration", 1, None, {}),
    ("SG-07", "Same-Type Instance Isolation",
     "orchestration", 2, None, {}),
    ("SG-08", "Instance Health Monitoring",
     "monitoring", 2, None, {}),
    ("SG-09", "Graceful Instance Failover",
     "orchestration", 3, None, {}),
    ("SG-10", "Instance Auto-Recovery",
     "orchestration", 3, None, {}),
    ("SG-12", "Variant Upgrade Path",
     "orchestration", 1, None, {}),
    ("SG-14", "Multi-Instance Billing Split",
     "monitoring", 2, None, {}),
    ("SG-15", "Per-Instance API Key",
     "guardrail", 2, None, {}),
    ("SG-16", "Cross-Instance Ticket Transfer",
     "orchestration", 2, None, {}),
    ("SG-17", "Shared Knowledge Base",
     "rag", 1, None, {}),
    ("SG-18", "Instance-Specific Training",
     "technique", 2, None, {}),
    ("SG-19", "Batch Operations across Instances",
     "orchestration", 3, None, {}),
    ("SG-20", "Instance Grouping",
     "orchestration", 2, None, {}),
    ("SG-23", "Human-in-the-Loop Config",
     "orchestration", 1, None, {}),
    ("SG-24", "Conversation Handoff Protocol",
     "orchestration", 2, None, {}),
    ("SG-25", "Multi-Channel Sync",
     "routing", 2, None, {}),
    ("SG-26", "Context Window Optimization",
     "routing", 2, None, {}),
    ("SG-27", "Fallback Response Cache",
     "response", 2, None, {}),
    ("SG-28", "Rate Limit per Instance",
     "guardrail", 2, None, {}),
    ("SG-29", "Token Budget per Instance",
     "guardrail", 1, None, {}),
    ("SG-30", "Model Fallback Chain",
     "routing", 1, None, {}),
    ("SG-31", "Instance-Specific Prompts",
     "response", 2, None, {}),
    ("SG-32", "Custom Guardrail Rules",
     "guardrail", 2, None, {}),
    ("SG-33", "Escalation to Human",
     "response", 1, None, {}),
    ("SG-34", "Auto-Close Rules",
     "response", 2, None, {}),
    ("SG-35", "Priority Queue per Instance",
     "orchestration", 2, None, {}),
    ("SG-36", "Workload Rebalancing",
     "orchestration", 3, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _gaps:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Channel Features ───────────────────────────────────────────
_channels = [
    ("F-250", "Email Channel AI", "routing", 1, None, {}),
    ("F-251", "Chat Channel AI", "routing", 1, None, {}),
    ("F-252", "SMS Channel AI", "routing", 2, None, {}),
    ("F-253", "Voice Channel AI", "routing", 3, None, {}),
    ("F-254", "Social Media Channel AI",
     "routing", 2, None, {}),
    ("F-255", "WhatsApp Channel AI", "routing", 2, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _channels:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }

# ── Additional Features to reach 170+ ─────────────────────────
_extra = [
    ("F-260", "Auto-Summarization", "response", 2, None, {}),
    ("F-261", "Knowledge Base Auto-Update",
     "rag", 3, None, {}),
    ("F-262", "Feedback Loop Learning",
     "technique", 3, None, {}),
    ("F-263", "Customer Satisfaction Prediction",
     "classification", 3, None, {}),
    ("F-264", "Churn Risk Detection",
     "classification", 3, None, {}),
    ("F-265", "Response Quality Scoring",
     "monitoring", 2, None, {}),
    ("F-266", "SLA Compliance Monitor",
     "monitoring", 2, None, {}),
    ("F-267", "Agent Performance Analytics",
     "monitoring", 2, None, {}),
    ("F-268", "Ticket Volume Forecasting",
     "monitoring", 3, None, {}),
    ("F-269", "Knowledge Gap Detection",
     "rag", 3, None, {}),
    ("F-270", "Automated FAQ Generation",
     "response", 3, None, {}),
    ("F-271", "Conversation Analytics",
     "monitoring", 2, None, {}),
    ("F-272", "Customer Journey Mapping",
     "classification", 3, None, {}),
    ("F-273", "Proactive Engagement",
     "response", 3, None, {}),
    ("F-274", "Batch Response Processing",
     "response", 2, None, {}),
    ("F-275", "Template Suggestion Engine",
     "response", 2, None, {}),
    ("F-276", "Duplicate Detection (AI)",
     "classification", 1, None, {}),
    ("F-277", "Similar Ticket Matching",
     "classification", 2, None, {}),
    ("F-278", "Response Time Optimization",
     "monitoring", 2, None, {}),
    ("F-279", "Multi-Tenant AI Isolation",
     "guardrail", 1, None, {}),
    ("F-280", "Custom Model Configuration",
     "routing", 3, None, {}),
    ("F-281", "Prompt Versioning",
     "response", 3, None, {}),
    ("F-282", "Experiment Tracking",
     "monitoring", 3, None, {}),
    ("F-283", "Model Drift Detection",
     "monitoring", 3, None, {}),
    ("F-284", "Data Lineage Tracking",
     "monitoring", 3, None, {}),
    ("F-285", "Compliance Audit AI",
     "guardrail", 3, None, {}),
    ("F-286", "Secure Response Generation",
     "guardrail", 2, None, {}),
    ("F-287", "Anomaly Detection",
     "monitoring", 2, None, {}),
    ("F-288", "Capacity Planning AI",
     "monitoring", 3, None, {}),
    ("F-289", "Intelligent Routing Cache",
     "routing", 2, None, {}),
    ("F-290", "Context Deduplication",
     "rag", 2, None, {}),
    ("F-291", "Embedding Cache Management",
     "rag", 2, None, {}),
    ("F-292", "Query Rewrite Engine",
     "rag", 2, None, {}),
    ("F-293", "Response Personalization ML",
     "response", 3, None, {}),
    ("F-294", "Multi-Modal Input Support",
     "routing", 3, None, {}),
    ("F-295", "Image Understanding",
     "classification", 3, None, {}),
    ("F-296", "Document Understanding",
     "rag", 3, None, {}),
]
for fid, name, cat, lvl, tt, cfg in _extra:
    FEATURE_REGISTRY[fid] = {
        "name": name, "category": cat,
        "min_level": lvl, "technique_tier": tt,
        "config": cfg,
    }


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _validate_company_id(company_id: str) -> None:
    """Validate company_id is not empty (BC-001)."""
    if not company_id or not company_id.strip():
        raise ParwaBaseError(
            message="company_id is required and cannot be empty",
            error_code="INVALID_COMPANY_ID",
            status_code=400,
        )


def _validate_variant_type(variant_type: str) -> None:
    """Validate variant_type is a known type."""
    if variant_type not in VARIANT_LEVELS:
        raise ParwaBaseError(
            error_code="INVALID_VARIANT_TYPE",
            message=(
                f"Invalid variant_type '{variant_type}'. "
                f"Must be one of: "
                f"{', '.join(VARIANT_LEVELS.keys())}"
            ),
            status_code=400,
        )


def initialize_variant_matrix(
    db: SessionLocal,
    company_id: str,
) -> int:
    """
    Populate variant_ai_capabilities for a new tenant.

    Creates entries for ALL features across ALL 3 variant types.
    Features above a variant's level are marked is_enabled=False.

    Returns the number of capability rows created.

    Idempotent: skips if capabilities already exist for this
    company_id + variant_type + feature_id.
    """
    _validate_company_id(company_id)

    level = VARIANT_LEVELS
    created = 0

    for feature_id, feat in FEATURE_REGISTRY.items():
        for variant_type, var_level in level.items():
            is_enabled = feat["min_level"] <= var_level
            cfg = json.dumps(feat["config"])

            # Idempotent: check if already exists
            existing = db.query(VariantAICapability).filter_by(
                company_id=company_id,
                variant_type=variant_type,
                instance_id=None,
                feature_id=feature_id,
            ).first()

            if existing is not None:
                continue

            cap = VariantAICapability(
                company_id=company_id,
                variant_type=variant_type,
                instance_id=None,
                feature_id=feature_id,
                feature_name=feat["name"],
                feature_category=feat["category"],
                technique_tier=feat.get("technique_tier"),
                is_enabled=is_enabled,
                config_json=cfg,
            )
            db.add(cap)
            created += 1

    if created > 0:
        db.commit()

    return created


def get_capability(
    db: SessionLocal,
    company_id: str,
    feature_id: str,
    variant_type: str | None = None,
    instance_id: str | None = None,
) -> VariantAICapability | None:
    """
    Look up a specific capability.

    If instance_id is given, check instance-specific override
    first, then fall back to variant_type default.
    """
    _validate_company_id(company_id)

    query = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        feature_id=feature_id,
    )

    # Instance-specific override takes precedence
    if instance_id is not None:
        inst_cap = query.filter_by(
            instance_id=instance_id,
        ).first()
        if inst_cap is not None:
            return inst_cap

    # Fall back to variant default (instance_id=NULL)
    if variant_type is not None:
        var_cap = query.filter_by(
            variant_type=variant_type,
            instance_id=None,
        ).first()
        return var_cap

    # No variant_type or instance match
    return None


def check_feature_enabled(
    db: SessionLocal,
    company_id: str,
    feature_id: str,
    variant_type: str,
    instance_id: str | None = None,
) -> bool:
    """
    Returns whether a feature is enabled for this
    variant/instance combination.
    """
    cap = get_capability(
        db, company_id, feature_id, variant_type, instance_id,
    )
    if cap is None:
        return False
    return cap.is_enabled


def list_capabilities(
    db: SessionLocal,
    company_id: str,
    variant_type: str | None = None,
    feature_category: str | None = None,
    instance_id: str | None = None,
    enabled_only: bool = False,
) -> list[VariantAICapability]:
    """List capabilities with optional filtering."""
    _validate_company_id(company_id)

    query = db.query(VariantAICapability).filter_by(
        company_id=company_id,
    )

    if variant_type is not None:
        query = query.filter_by(variant_type=variant_type)
    if instance_id is not None:
        query = query.filter_by(instance_id=instance_id)
    else:
        query = query.filter(
            VariantAICapability.instance_id.is_(None),
        )
    if feature_category is not None:
        query = query.filter_by(
            feature_category=feature_category,
        )
    if enabled_only:
        query = query.filter_by(is_enabled=True)

    return query.order_by(
        VariantAICapability.feature_id,
    ).all()


def update_capability_config(
    db: SessionLocal,
    company_id: str,
    feature_id: str,
    variant_type: str,
    config_json: dict,
    instance_id: str | None = None,
) -> VariantAICapability:
    """Update per-feature config overrides."""
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    query = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        feature_id=feature_id,
        variant_type=variant_type,
    )

    if instance_id is not None:
        cap = query.filter_by(instance_id=instance_id).first()
    else:
        cap = query.filter(
            VariantAICapability.instance_id.is_(None),
        ).first()

    if cap is None:
        raise ParwaBaseError(
            error_code="CAPABILITY_NOT_FOUND",
            message=(
                f"Capability '{feature_id}' not found for "
                f"variant '{variant_type}'"
            ),
            status_code=404,
        )

    cap.config_json = json.dumps(config_json)
    cap.updated_at = datetime.now(timezone.utc)  # GAP 4 fix
    db.commit()
    db.refresh(cap)
    return cap


def get_enabled_features(
    db: SessionLocal,
    company_id: str,
    variant_type: str,
    instance_id: str | None = None,
) -> list[str]:
    """Returns list of enabled feature_ids."""
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    query = db.query(
        VariantAICapability.feature_id,
    ).filter_by(
        company_id=company_id,
        variant_type=variant_type,
        is_enabled=True,
    )

    if instance_id is not None:
        query = query.filter_by(instance_id=instance_id)
    else:
        query = query.filter(
            VariantAICapability.instance_id.is_(None),
        )

    rows = query.all()
    return [row[0] for row in rows]


def get_variant_feature_count(
    db: SessionLocal,
    company_id: str,
    variant_type: str,
) -> dict:
    """
    Returns count of enabled/disabled features
    per variant type.
    """
    _validate_company_id(company_id)
    _validate_variant_type(variant_type)

    caps = db.query(VariantAICapability).filter_by(
        company_id=company_id,
        variant_type=variant_type,
        instance_id=None,
    ).all()

    enabled = sum(1 for c in caps if c.is_enabled)
    disabled = sum(1 for c in caps if not c.is_enabled)

    return {
        "variant_type": variant_type,
        "total_features": len(caps),
        "enabled_features": enabled,
        "disabled_features": disabled,
    }


def batch_update_capabilities(
    db: SessionLocal,
    company_id: str,
    updates: list[dict],
) -> dict:
    """
    Batch enable/disable features.

    Each update dict:
      {
        "feature_id": str,
        "variant_type": str,
        "is_enabled": bool,
        "instance_id": str | None
      }

    Returns {"updated": int, "skipped": int, "errors": int}.
    """
    _validate_company_id(company_id)

    result = {"updated": 0, "skipped": 0, "errors": 0}

    for upd in updates:
        fid = upd.get("feature_id")
        vt = upd.get("variant_type")
        ie = upd.get("instance_id")
        en = upd.get("is_enabled")

        if not fid or not vt or en is None:
            result["errors"] += 1
            continue

        try:
            _validate_variant_type(vt)
        except ParwaBaseError:
            result["errors"] += 1
            continue

        try:
            query = db.query(VariantAICapability).filter_by(
                company_id=company_id,
                feature_id=fid,
                variant_type=vt,
            )

            if ie is not None:
                cap = query.filter_by(instance_id=ie).first()
            else:
                cap = query.filter(
                    VariantAICapability.instance_id.is_(None),
                ).first()

            if cap is None:
                result["skipped"] += 1
                continue

            cap.is_enabled = en
            cap.updated_at = datetime.now(timezone.utc)  # GAP 4 fix
            result["updated"] += 1
        except Exception:
            # Individual item failure should not break
            # the entire batch (BC-008 graceful degradation)
            result["errors"] += 1
            continue

    if result["updated"] > 0:
        db.commit()

    return result


def get_all_variant_summaries(
    db: SessionLocal,
    company_id: str,
) -> list[dict]:
    """Get feature count summaries for all variant types."""
    _validate_company_id(company_id)
    summaries = []
    for vt in VARIANT_LEVELS:
        summaries.append(
            get_variant_feature_count(db, company_id, vt),
        )
    return summaries
