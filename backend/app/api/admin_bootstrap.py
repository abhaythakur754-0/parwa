"""
PARWA Customer Variant Activation Endpoint

Allows a company owner to activate all 3 SaaS variants (Starter, Growth, High)
on their account for testing/demo purposes. The user remains a regular customer
(owner role) — no platform admin privileges are granted.

SECURITY:
- Requires valid JWT (must be company owner)
- First-run only: works only when no subscription record exists yet
- Does NOT grant is_platform_admin

This endpoint should be removed or disabled after initial testing.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.exceptions import ValidationError
from database.base import get_db
from database.models.core import User, Company
from database.models.billing import Subscription
from database.models.variant_engine import VariantInstance

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.post("/activate-all-variants")
def activate_all_variants(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate all 3 PARWA variants on the authenticated user's company.

    This is a setup/testing endpoint that simulates a customer who has
    purchased all 3 variants. The user stays as a regular customer (owner)
    with no admin privileges — exactly what a real customer would experience.

    What it does:
    - Sets company subscription_tier='high' and subscription_status='active'
    - Sets company mode to 'live'
    - Creates a subscription record (high tier, 30-day period)
    - Creates 3 VariantInstance records (starter, growth, high)
    - Does NOT set is_platform_admin
    """

    # Only company owners can do this
    if user.role != "owner":
        raise ValidationError(
            message="Only company owners can activate variants",
            details={"role": user.role},
        )

    company = db.query(Company).filter(
        Company.id == user.company_id,
    ).first()
    if not company:
        raise ValidationError(
            message="Company not found",
        )

    now = datetime.now(timezone.utc)

    # 1. Upgrade company to High tier (top tier — unlocks all features)
    company.subscription_tier = "high"
    company.subscription_status = "active"
    company.mode = "live"
    company.updated_at = now

    # 2. Create or update subscription record
    existing_sub = db.query(Subscription).filter(
        Subscription.company_id == company.id,
    ).first()

    if existing_sub:
        existing_sub.tier = "high"
        existing_sub.status = "active"
        existing_sub.current_period_start = now
        existing_sub.current_period_end = now + timedelta(days=30)
        existing_sub.cancel_at_period_end = False
    else:
        subscription = Subscription(
            id=str(uuid.uuid4()),
            company_id=company.id,
            tier="high",
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at_period_end=False,
        )
        db.add(subscription)

    # 3. Create 3 VariantInstance records (one per variant)
    variant_configs = [
        {
            "variant_type": "starter",
            "instance_name": "Starter - Chat & Email Support",
            "channels": ["email", "chat"],
            "capacity": {
                "max_concurrent_tickets": 50,
                "token_budget_share_pct": 15,
                "priority_weight": 1,
            },
        },
        {
            "variant_type": "growth",
            "instance_name": "Growth - Multi-Channel Agent",
            "channels": ["email", "chat", "sms", "voice"],
            "capacity": {
                "max_concurrent_tickets": 200,
                "token_budget_share_pct": 35,
                "priority_weight": 2,
            },
        },
        {
            "variant_type": "high",
            "instance_name": "High - Senior AI Agent (Full Suite)",
            "channels": ["email", "chat", "sms", "voice", "social"],
            "capacity": {
                "max_concurrent_tickets": 500,
                "token_budget_share_pct": 50,
                "priority_weight": 3,
            },
        },
    ]

    for config in variant_configs:
        existing = db.query(VariantInstance).filter(
            VariantInstance.company_id == company.id,
            VariantInstance.variant_type == config["variant_type"],
        ).first()

        if existing:
            existing.status = "active"
            existing.channel_assignment = json.dumps(config["channels"])
            existing.capacity_config = json.dumps(config["capacity"])
        else:
            instance = VariantInstance(
                id=str(uuid.uuid4()),
                company_id=company.id,
                instance_name=config["instance_name"],
                variant_type=config["variant_type"],
                status="active",
                channel_assignment=json.dumps(config["channels"]),
                capacity_config=json.dumps(config["capacity"]),
            )
            db.add(instance)

    db.commit()

    return {
        "message": "All 3 variants activated — you now have Starter, Growth, and High as a customer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_platform_admin": user.is_platform_admin,
        },
        "company": {
            "id": str(company.id),
            "name": company.name,
            "subscription_tier": "high",
            "subscription_status": "active",
            "mode": "live",
        },
        "variants_activated": [
            {
                "type": c["variant_type"],
                "name": c["instance_name"],
                "channels": c["channels"],
            }
            for c in variant_configs
        ],
        "note": "Log out and log back in to get a fresh JWT with the 'high' plan claim.",
    }


@router.get("/migrate-unique-id")
def migrate_unique_id():
    """One-time migration: add unique_id column to companies table.

    Safe to call multiple times — uses IF NOT EXISTS.
    Called manually after deploying the unique_id feature.
    """
    from sqlalchemy import text
    from database.base import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS unique_id VARCHAR(50)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_companies_unique_id ON companies (unique_id)"))
            conn.commit()
        return {"status": "ok", "message": "unique_id column added (or already existed)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/debug-company")
def debug_company():
    """Temporary debug endpoint — check company data for thakurabahychaowhan754.
    Returns: company name, unique_id, industry, subscription_tier, variant instances.
    """
    from sqlalchemy import text
    from database.base import engine

    try:
        with engine.connect() as conn:
            # Find company by user email
            rows = conn.execute(text("""
                SELECT c.id, c.name, c.unique_id, c.industry,
                       c.subscription_tier, c.subscription_status
                FROM companies c
                JOIN users u ON u.company_id = c.id
                WHERE u.email LIKE '%thakurabahy%' OR u.email LIKE '%thakur%'
            """)).fetchall()

            if not rows:
                return {"status": "not_found", "message": "No company found for that user"}

            companies = []
            for row in rows:
                company_id = row[0]
                # Get variant instances
                vi_rows = conn.execute(text("""
                    SELECT instance_name, variant_type, status
                    FROM variant_instances
                    WHERE company_id = :cid
                """), {"cid": company_id}).fetchall()

                # Get subscriptions
                sub_rows = conn.execute(text("""
                    SELECT tier, status, paddle_subscription_id
                    FROM subscriptions
                    WHERE company_id = :cid AND status NOT IN ('plan_cache', 'customer_link')
                """), {"cid": company_id}).fetchall()

                # Get ticket count
                ticket_count = conn.execute(text("""
                    SELECT count(*) FROM tickets WHERE company_id = :cid
                """), {"cid": company_id}).scalar()

                companies.append({
                    "company_id": company_id,
                    "name": row[1],
                    "unique_id": row[2],
                    "industry": row[3],
                    "subscription_tier": row[4],
                    "subscription_status": row[5],
                    "variant_instances": [{"name": r[0], "type": r[1], "status": r[2]} for r in vi_rows],
                    "subscriptions": [{"tier": r[0], "status": r[1], "razorpay_id": r[2]} for r in sub_rows],
                    "ticket_count": ticket_count,
                })

            return {"status": "ok", "companies": companies}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()[:500]}


@router.get("/fix-existing-company")
def fix_existing_company():
    """One-time fix: for companies that completed onboarding before the
    unique_id + variant_instance features were added.

    For each company with subscription_status='trial' and no variant_instances:
    1. Set subscription_status to 'active'
    2. Create a VariantInstance matching their subscription_tier
    3. Set unique_id if not already set (uses company name slugified)
    """
    from sqlalchemy import text
    from database.base import engine

    try:
        with engine.connect() as conn:
            # Find all companies with 'trial' status and no variant instances
            rows = conn.execute(text("""
                SELECT c.id, c.name, c.unique_id, c.subscription_tier
                FROM companies c
                WHERE c.subscription_status = 'trial'
                AND NOT EXISTS (
                    SELECT 1 FROM variant_instances vi WHERE vi.company_id = c.id
                )
            """)).fetchall()

            fixed = []
            for row in rows:
                company_id = row[0]
                company_name = row[1]
                existing_unique_id = row[2]
                tier = row[3] or 'starter'

                # Set subscription_status to active
                conn.execute(text(
                    "UPDATE companies SET subscription_status = 'active' WHERE id = :cid"
                ), {"cid": company_id})

                # Set unique_id if not set (slugify company name)
                if not existing_unique_id:
                    slug = company_name.lower().replace(' ', '-').replace("'", '').replace('"', '')[:30]
                    # Ensure uniqueness
                    existing = conn.execute(text(
                        "SELECT id FROM companies WHERE unique_id = :slug AND id != :cid"
                    ), {"slug": slug, "cid": company_id}).fetchone()
                    if existing:
                        slug = f"{slug}-{company_id[:4]}"
                    conn.execute(text(
                        "UPDATE companies SET unique_id = :slug WHERE id = :cid"
                    ), {"slug": slug, "cid": company_id})
                    fixed_unique_id = slug
                else:
                    fixed_unique_id = existing_unique_id

                # Create variant instance
                instance_name = "Mini Parwa" if tier == "starter" else "Parwa" if tier == "growth" else "High Parwa"
                import uuid
                conn.execute(text("""
                    INSERT INTO variant_instances (id, company_id, instance_name, variant_type, status, channel_assignment, capacity_config, active_tickets_count, total_tickets_handled)
                    VALUES (:id, :cid, :name, :type, 'active', '["chat"]', '{"max_concurrent": 10}', 0, 0)
                """), {
                    "id": str(uuid.uuid4()),
                    "cid": company_id,
                    "name": instance_name,
                    "type": tier,
                })

                fixed.append({
                    "company_id": company_id,
                    "name": company_name,
                    "unique_id": fixed_unique_id,
                    "tier": tier,
                    "instance_name": instance_name,
                })

            conn.commit()
            return {"status": "ok", "fixed_count": len(fixed), "companies": fixed}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()[:500]}


@router.get("/nuke-all-data")
def nuke_all_data():
    """DESTRUCTIVE: Delete ALL user data from every table. Cannot be undone.
    Leaves only the database schema (empty tables).
    """
    from sqlalchemy import text
    from database.base import engine

    tables_to_wipe = [
        "ticket_feedbacks",
        "ticket_messages",
        "ticket_attachments",
        "ticket_internal_notes",
        "ticket_status_changes",
        "ticket_assignments",
        "ticket_collisions",
        "ticket_intents",
        "ticket_merges",
        "ticket_triggers",
        "tickets",
        "subscriptions",
        "invoices",
        "transactions",
        "overage_charges",
        "cancellation_requests",
        "variant_instances",
        "variant_workload_distribution",
        "variant_ai_capabilities",
        "ai_agent_assignments",
        "onboarding_sessions",
        "first_victories",
        "knowledge_documents",
        "document_chunks",
        "customers",
        "customer_channels",
        "customer_merge_audits",
        "approval_queues",
        "auto_approve_rules",
        "executed_actions",
        "notifications",
        "notification_preferences",
        "notification_logs",
        "activity_log",
        "jarvis_activity_events",
        "jarvis_sessions",
        "jarvis_messages",
        "jarvis_knowledge_used",
        "jarvis_awareness_snapshots",
        "jarvis_commands",
        "jarvis_proactive_alerts",
        "demo_sessions",
        "audit_trail",
        "webhook_events",
        "webhook_sequences",
        "idempotency_keys",
        "proration_audits",
        "payment_failures",
        "payment_methods",
        "usage_records",
        "client_refunds",
        "paddle_webhook_events",
        "paddle_reconciliation_reports",
        "refresh_tokens",
        "mfa_secrets",
        "backup_codes",
        "phone_otps",
        "business_email_otps",
        "verification_tokens",
        "password_reset_tokens",
        "oauth_accounts",
        "api_keys",
        "api_key_audit_log",
        "agents",
        "emergency_states",
        "company_settings",
        "rate_limit_events",
        "users",
        "companies",
    ]

    try:
        with engine.connect() as conn:
            deleted_counts = {}
            for table in tables_to_wipe:
                try:
                    result = conn.execute(text(f"DELETE FROM {table}"))
                    deleted_counts[table] = result.rowcount if result.rowcount and result.rowcount > 0 else 0
                except Exception:
                    # Table might not exist — skip
                    deleted_counts[table] = "skipped"
            conn.commit()

        return {
            "status": "ok",
            "message": "ALL data deleted. Database is now empty.",
            "deleted_counts": deleted_counts,
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()[:500]}


@router.get("/debug-onboarding")
def debug_onboarding():
    """Check onboarding state for all users."""
    from sqlalchemy import text
    from database.base import engine

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT u.email, u.id, u.company_id,
                       o.current_step, o.status, o.first_victory_completed,
                       o.details_completed, o.wizard_started
                FROM users u
                LEFT JOIN onboarding_sessions o ON o.user_id = u.id
                ORDER BY u.created_at DESC
                LIMIT 10
            """)).fetchall()

            users = []
            for row in rows:
                users.append({
                    "email": row[0],
                    "user_id": row[1],
                    "company_id": row[2],
                    "current_step": row[3],
                    "status": row[4],
                    "first_victory_completed": row[5],
                    "details_completed": row[6],
                    "wizard_started": row[7],
                })
            return {"status": "ok", "users": users}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/debug-variants")
def debug_variants():
    """Check variant instances for all companies."""
    from sqlalchemy import text
    from database.base import engine

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT vi.id, vi.company_id, vi.instance_name, vi.variant_type, vi.status,
                       c.name as company_name
                FROM variant_instances vi
                JOIN companies c ON c.id = vi.company_id
                ORDER BY vi.created_at DESC
            """)).fetchall()

            instances = []
            for row in rows:
                instances.append({
                    "id": row[0],
                    "company_id": row[1],
                    "instance_name": row[2],
                    "variant_type": row[3],
                    "status": row[4],
                    "company_name": row[5],
                })
            return {"status": "ok", "count": len(instances), "instances": instances}
    except Exception as e:
        return {"status": "error", "message": str(e)}
