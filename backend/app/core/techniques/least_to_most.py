"""
F-148: Least-to-Most Decomposition — Tier 3 Premium AI Reasoning Technique

Activates when query_complexity > 0.7, task has 5+ identifiable sub-steps,
multi-department coordination required, or enterprise-scale request with
multiple components. Uses deterministic/heuristic-based decomposition
(no LLM calls) to solve complex queries by:

  1. Decomposition          — break complex query into simplest sub-queries
  2. Dependency Ordering    — order sub-queries by dependency graph
  3. Sequential Solving     — solve each sub-query, feeding results forward
  4. Result Combination     — combine all results into comprehensive answer
  5. Completeness Check     — verify all original query components addressed

Performance target: ~800-1,300 tokens per activation, sub-200ms processing.

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("least_to_most")


# ── Enums ────────────────────────────────────────────────────────────


class SubQueryStatus(str, Enum):
    """Lifecycle status of a sub-query within the decomposition pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SOLVED = "solved"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class TaskDomain(str, Enum):
    """Domains of complex enterprise tasks for template matching."""
    ONBOARDING = "onboarding"
    MIGRATION = "migration"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    REPORTING = "reporting"
    GENERAL = "general"


# ── Task Domain Pattern Matching ─────────────────────────────────────


_DOMAIN_PATTERNS: List[Tuple[re.Pattern, TaskDomain]] = [
    # Onboarding patterns
    (
        re.compile(
            r"\b(onboard|new.?employee|new.?hire|new.?user|new.?member|"
            r"join|welcom|first.?day|orientation|setup.?account|"
            r"provision|access.?grant)\b",
            re.I,
        ),
        TaskDomain.ONBOARDING,
    ),
    # Migration patterns
    (
        re.compile(
            r"\b(migrat|transfer|move.?data|switch.?to|transition|"
            r"import.?data|export.?data|convert|data.?transfer|"
            r"port|relocate)\b",
            re.I,
        ),
        TaskDomain.MIGRATION,
    ),
    # Configuration patterns
    (
        re.compile(
            r"\b(config|setting|setup|customize|preference|"
            r"workflow.?config|permission|role.?setup|policy.?config|"
            r"workspace.?setup|environment|parameter|option)\b",
            re.I,
        ),
        TaskDomain.CONFIGURATION,
    ),
    # Integration patterns
    (
        re.compile(
            r"\b(integrat|connect|sync|api.?setup|webhook|"
            r"third.?party|plugin|extension|slack|email.?sync|"
            r"sso|single.?sign|oauth|zapier|connector)\b",
            re.I,
        ),
        TaskDomain.INTEGRATION,
    ),
    # Reporting patterns
    (
        re.compile(
            r"\b(report|dashboard|analytics|metric|kpi|"
            r"chart|graph|visuali|track|monitor|insight|"
            r"summary|export.?report|schedule.?report|aggregate)\b",
            re.I,
        ),
        TaskDomain.REPORTING,
    ),
]

_DEFAULT_DOMAIN = TaskDomain.GENERAL


# ── Decomposition Templates ──────────────────────────────────────────
#
# Each template defines:
#   name             — human-readable template label
#   trigger_keywords — keywords that select this template
#   sub_queries      — ordered list of sub-query definitions
#       id             — unique identifier within template (sq1, sq2, …)
#       text           — the sub-query question
#       dependencies   — list of sq IDs this sub-query depends on
#       is_parallel    — whether this can run alongside peers
#       answer         — deterministic heuristic answer
#   dependency_chain — visual representation of the execution flow
#   final_synthesis  — template for combining all results


_DECOMPOSITION_TEMPLATES: Dict[TaskDomain, List[Dict[str, Any]]] = {
    # ──── ONBOARDING ────────────────────────────────────────────────
    TaskDomain.ONBOARDING: [
        # Template 1: Multi-department employee onboarding
        {
            "name": "multi_dept_employee_onboarding",
            "trigger_keywords": [
                "onboard", "new employee", "new hire", "department",
                "access", "email", "slack", "provision",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "How many employees need to be onboarded and across which departments?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "The headcount and department distribution should be "
                        "confirmed with HR. A standard roster listing each "
                        "employee's name, target department, start date, and "
                        "role is the foundation for all subsequent steps."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "Which employees are managers or team leads requiring elevated permissions?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Manager identification requires cross-referencing the "
                        "roster with the organizational chart. Managers typically "
                        "receive admin-level or team-admin access, while individual "
                        "contributors receive standard user access."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What platform access levels are required per department?",
                    "dependencies": ["sq2"],
                    "is_parallel": False,
                    "answer": (
                        "Access requirements vary by department. Engineering "
                        "typically needs repository and CI/CD access. Sales needs "
                        "CRM and analytics. Marketing needs content management "
                        "tools. All departments need core platform access and "
                        "communication tools."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to set up email integration for all new employees?",
                    "dependencies": ["sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Email integration is configured through the admin "
                        "console under Settings → Integrations → Email. Batch "
                        "provisioning via CSV upload is recommended for groups "
                        "of 10+. Each user receives a welcome email with setup "
                        "instructions upon account creation."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to set up Slack/workspace integration for all new employees?",
                    "dependencies": ["sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Slack integration is configured under Settings → "
                        "Integrations → Messaging. Users can be bulk-invited "
                        "via email list. Department-specific channels should be "
                        "pre-created and users auto-assigned based on their "
                        "department field."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What is the recommended onboarding sequence and timeline?",
                    "dependencies": ["sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Recommended sequence: (1) Day 0 — create accounts, "
                        "(2) Day 1 — send welcome emails with access credentials, "
                        "(3) Day 1-2 — assign department channels and tool access, "
                        "(4) Day 3 — verify all integrations active, "
                        "(5) Week 1 — collect feedback and resolve issues."
                    ),
                },
                {
                    "id": "sq7",
                    "text": "What compliance and security training is required?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "All new employees must complete security awareness "
                        "training within their first week. Managers additionally "
                        "require data governance and access management training. "
                        "Certificates of completion should be tracked in HRIS."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → sq3 → [parallel: sq4, sq5, sq7] → sq6"
            ),
            "final_synthesis": (
                "To onboard {count} employees across {departments} departments: "
                "First, confirm the roster and identify managers (sq1 → sq2). "
                "Then, determine access levels per department (sq3). "
                "Next, configure email and Slack integrations in parallel "
                "(sq4 ∥ sq5), alongside compliance training assignments (sq7). "
                "Finally, follow the recommended onboarding timeline (sq6) "
                "to ensure a smooth rollout."
            ),
        },
        # Template 2: Customer/client onboarding
        {
            "name": "customer_client_onboarding",
            "trigger_keywords": [
                "customer", "client", "onboard", "trial", "pilot",
                "kickoff", "implementation",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the customer's company profile and team size?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Collect the customer's company name, industry, total "
                        "seat count, primary contact, and technical contact. "
                        "This determines the plan tier, SLA requirements, and "
                        "configuration complexity."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "Which product plan and features does the customer need?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "The plan tier is determined by seat count and feature "
                        "requirements. Enterprise plans include SSO, audit logs, "
                        "and dedicated support. Pro plans include advanced "
                        "analytics and API access. Free plans include core "
                        "features only."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What data needs to be imported or migrated for the customer?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Data import scope includes user lists, existing "
                        "configurations, historical data (if applicable), and "
                        "any integrations with the customer's existing tools. "
                        "A data mapping document should be created and reviewed."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What integrations does the customer require?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Common customer integrations include SSO (SAML/OIDC), "
                        "HRIS sync, CRM integration, and notification webhooks. "
                        "Each integration requires separate configuration and "
                        "testing before go-live."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What training and documentation does the customer need?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Training needs are determined by plan tier and team "
                        "size. Standard: self-serve docs and knowledge base. "
                        "Pro: live onboarding session + docs. Enterprise: "
                        "dedicated CSM, custom training, and ongoing Q&A sessions."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What is the go-live checklist and success criteria?",
                    "dependencies": ["sq3", "sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Go-live checklist: (1) All user accounts provisioned, "
                        "(2) Data imported and verified, (3) Integrations tested "
                        "and active, (4) Training completed, (5) Support channel "
                        "established. Success criteria: 90%+ user activation "
                        "within 14 days, zero critical issues in first week."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3] → [parallel: sq4, sq5] → sq6"
            ),
            "final_synthesis": (
                "Customer onboarding plan: Start by gathering the company "
                "profile (sq1). Then assess plan requirements (sq2) and data "
                "migration scope (sq3) in parallel. Configure required "
                "integrations (sq4) and prepare training materials (sq5). "
                "Execute the go-live checklist (sq6) with defined success "
                "criteria to ensure a smooth launch."
            ),
        },
        # Template 3: Bulk user provisioning
        {
            "name": "bulk_user_provisioning",
            "trigger_keywords": [
                "bulk", "batch", "provision", "create accounts",
                "add users", "user list", "csv", "import users",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the source of user data and format?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "User data should be provided in CSV format with "
                        "columns: email, full_name, department, role. "
                        "Alternative formats (JSON, Excel) require conversion. "
                        "The data source is typically HRIS export or a manual "
                        "spreadsheet maintained by HR."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "How to validate and clean the user data before import?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Validation checks: (1) Required fields present, "
                        "(2) Valid email format, (3) No duplicate emails, "
                        "(4) Recognized department names, (5) Valid role values. "
                        "Records failing validation should be flagged in a "
                        "separate error report for manual review."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What roles and permission groups need to be assigned?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Role assignment follows the principle of least "
                        "privilege. Standard roles: Viewer, Editor, Admin. "
                        "Custom roles can be created per department. The "
                        "mapping between user role field and system roles "
                        "should be defined before import."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to execute the bulk import operation?",
                    "dependencies": ["sq2", "sq3"],
                    "is_parallel": False,
                    "answer": (
                        "Bulk import is executed via Admin → Users → Import. "
                        "Upload the validated CSV, map columns to system fields, "
                        "review the preview, and confirm. The system processes "
                        "records in batches of 100 with progress tracking. "
                        "A detailed import report is generated upon completion."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to verify the import and handle errors?",
                    "dependencies": ["sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Post-import verification: (1) Compare imported count "
                        "vs. expected count, (2) Spot-check random user records, "
                        "(3) Verify role assignments, (4) Test login for sample "
                        "users. Failed records are listed in the import report "
                        "with specific error reasons for each."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What post-provisioning steps are needed?",
                    "dependencies": ["sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Post-provisioning: (1) Send welcome emails to all "
                        "imported users, (2) Assign to department workspaces, "
                        "(3) Enroll in required training, (4) Notify managers "
                        "of their team's access. Bulk actions can be used for "
                        "steps 1-3 via the admin console."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3] → sq4 → sq5 → sq6"
            ),
            "final_synthesis": (
                "Bulk provisioning workflow: Prepare and format the user data "
                "(sq1). Validate data quality (sq2) and define role mappings "
                "(sq3) in parallel. Execute the bulk import (sq4), verify "
                "results and resolve errors (sq5), then complete "
                "post-provisioning tasks (sq6) to fully activate all users."
            ),
        },
    ],
    # ──── MIGRATION ─────────────────────────────────────────────────
    TaskDomain.MIGRATION: [
        # Template 1: Data migration
        {
            "name": "data_migration",
            "trigger_keywords": [
                "migrate data", "move data", "import data", "export data",
                "data transfer", "database migration", "bulk data",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the scope and volume of data to be migrated?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Data migration scope includes: total record count, "
                        "data types (users, transactions, configurations), "
                        "estimated data volume (GB/TB), date range coverage, "
                        "and any data that should be excluded or archived."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What is the source system and data format?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Source system details include: system name and version, "
                        "database type (MySQL, PostgreSQL, MongoDB), data "
                        "export format (CSV, JSON, SQL dump), and available "
                        "API endpoints for extraction."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What is the target schema and mapping rules?",
                    "dependencies": ["sq2"],
                    "is_parallel": False,
                    "answer": (
                        "Target schema mapping requires a field-by-field "
                        "comparison between source and target. Special attention "
                        "to: primary key translation, foreign key relationships, "
                        "enum value mapping, nullable field handling, and "
                        "default value assignment for missing fields."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to handle data validation and transformation?",
                    "dependencies": ["sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Data validation rules: type checking, constraint "
                        "validation, referential integrity, and business rule "
                        "compliance. Transformations include format conversion, "
                        "encoding normalization, and deduplication. Validation "
                        "is run on a sample (5%) before full migration."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What is the migration strategy (big bang vs phased)?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Strategy selection depends on data volume and downtime "
                        "tolerance. Big bang: all data migrated in one window "
                        "(suitable for < 10GB). Phased: data migrated in "
                        "logical batches over multiple windows (suitable for "
                        "larger datasets). Phased migration includes delta "
                        "sync for data created during migration."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What is the rollback plan if migration fails?",
                    "dependencies": ["sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Rollback plan: (1) Full backup of target before "
                        "migration, (2) Source system remains read-only during "
                        "migration window, (3) Automated rollback script tested "
                        "in staging, (4) Maximum rollback time: 2 hours, "
                        "(5) Communication plan to notify affected users."
                    ),
                },
                {
                    "id": "sq7",
                    "text": "How to verify migration completeness and correctness?",
                    "dependencies": ["sq4", "sq6"],
                    "is_parallel": False,
                    "answer": (
                        "Verification steps: (1) Record count comparison "
                        "(source vs. target), (2) Checksum/hash comparison for "
                        "data integrity, (3) Spot-check random records for field "
                        "accuracy, (4) Run integration tests, (5) Performance "
                        "benchmark comparison with pre-migration baseline."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → sq3 → [parallel: sq4, sq5] → sq6 → sq7"
            ),
            "final_synthesis": (
                "Data migration plan: Assess scope and volume (sq1), identify "
                "source system and format (sq2), create schema mapping (sq3). "
                "Prepare validation rules (sq4) and choose migration strategy "
                "(sq5) in parallel. Establish rollback plan (sq6), then "
                "execute migration and verify completeness (sq7)."
            ),
        },
        # Template 2: Platform/system migration
        {
            "name": "platform_system_migration",
            "trigger_keywords": [
                "switch", "move to", "transition", "replatform",
                "change system", "upgrade platform", "migrate platform",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the current platform and what are the pain points driving migration?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Document the current platform: name, version, "
                        "integrations, custom configurations, and user count. "
                        "Identify specific pain points: performance issues, "
                        "missing features, scalability limits, cost concerns, "
                        "or vendor dependency."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What is the target platform and required features?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Target platform selection criteria: feature parity with "
                        "current system, scalability requirements, integration "
                        "ecosystem, cost model, vendor stability, and compliance "
                        "certifications. A feature comparison matrix should "
                        "be created."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What integrations need to be re-established on the new platform?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Integration audit: list all current integrations, "
                        "categorize as critical/important/optional. Check "
                        "target platform's native support vs. requiring custom "
                        "development. Prioritize critical integrations for "
                        "go-live readiness."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What data migration is required for the platform switch?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Data migration for platform switch includes: user "
                        "accounts, configuration data, historical records, "
                        "custom templates, and workflow definitions. Export "
                        "tools and import APIs should be verified in a staging "
                        "environment first."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What user training and change management is needed?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Change management plan: (1) Communication timeline "
                        "starting 4 weeks before switch, (2) Training sessions "
                        "by user role, (3) Quick-reference guides for common "
                        "tasks, (4) Super-user program for department champions, "
                        "(5) Support escalation path during transition."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What is the cutover plan and timeline?",
                    "dependencies": ["sq3", "sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Cutover plan: (1) Staging validation 2 weeks prior, "
                        "(2) Final data sync during maintenance window, "
                        "(3) DNS/config switch, (4) Smoke testing of critical "
                        "flows, (5) Old platform in read-only mode for 30 days, "
                        "(6) Full decommission after 60-day stabilization period."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4, sq5] → sq6"
            ),
            "final_synthesis": (
                "Platform migration plan: Document current state and pain "
                "points (sq1), select target platform with feature comparison "
                "(sq2). In parallel, audit integrations (sq3), plan data "
                "migration (sq4), and prepare change management (sq5). "
                "Execute the cutover plan (sq6) with defined validation and "
                "stabilization periods."
            ),
        },
        # Template 3: User/account migration
        {
            "name": "user_account_migration",
            "trigger_keywords": [
                "merge accounts", "transfer users", "consolidate users",
                "move accounts", "user migration", "account transfer",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the source and target for user account migration?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Identify source system(s) and target system. Determine "
                        "if this is a one-way migration, bidirectional sync, or "
                        "merge operation. Document the total number of accounts "
                        "and any accounts that exist in both systems (duplicates)."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "How to handle duplicate accounts across systems?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Duplicate resolution strategy: (1) Match by email "
                        "address as primary key, (2) For matches, merge data "
                        "preferring target system settings, (3) Flag unmatched "
                        "source accounts for manual review, (4) Provide a "
                        "deduplication report before execution."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What user data and permissions need to be migrated?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Migratable data: profile information, role and "
                        "permission assignments, team/group memberships, "
                        "notification preferences, API tokens (regenerated), "
                        "and activity history (if supported). SSO mappings "
                        "must be updated if identity provider differs."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to preserve user sessions and avoid disruption?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Session continuity: (1) Schedule migration during "
                        "low-usage window, (2) Set session TTL to force "
                        "re-authentication post-migration, (3) Send advance "
                        "notification to all affected users, (4) Provide a "
                        "grace period where both systems accept logins."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to verify the migration was successful?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Verification: (1) Total user count matches expected, "
                        "(2) Sample login tests for migrated accounts, "
                        "(3) Permission verification for each role, "
                        "(4) Integration functionality check, (5) Monitor "
                        "support tickets for migration-related issues for 7 days."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4] → sq5"
            ),
            "final_synthesis": (
                "User migration plan: Identify source/target systems and "
                "account scope (sq1). Resolve duplicate accounts (sq2). "
                "Migrate user data and permissions (sq3) while preserving "
                "session continuity (sq4) in parallel. Verify success with "
                "automated and manual checks (sq5)."
            ),
        },
    ],
    # ──── CONFIGURATION ─────────────────────────────────────────────
    TaskDomain.CONFIGURATION: [
        # Template 1: Multi-team workspace configuration
        {
            "name": "multi_team_workspace_setup",
            "trigger_keywords": [
                "workspace", "team setup", "multi-team", "organization",
                "create workspace", "team structure", "department setup",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the organizational structure and team hierarchy?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Organizational structure should map to workspace "
                        "hierarchy. Document: company → divisions → departments "
                        "→ teams. Each level may correspond to a workspace, "
                        "sub-workspace, or channel depending on platform "
                        "capabilities."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What roles and permission levels are needed?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Standard role hierarchy: Organization Admin (full "
                        "control), Workspace Admin (workspace-scoped), Team "
                        "Lead (team management), Member (standard access), "
                        "Guest (read-only). Custom roles can be created for "
                        "specialized functions (e.g., Auditor, API User)."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "How to configure cross-team collaboration settings?",
                    "dependencies": ["sq1", "sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Cross-team settings: (1) Shared channels for "
                        "inter-department projects, (2) Guest access policies "
                        "for external collaborators, (3) Resource sharing rules "
                        "(documents, dashboards), (4) Approval workflows for "
                        "cross-team requests."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What notification and communication preferences should be set?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Notification configuration: (1) Default notification "
                        "level per workspace (all/mentions/replies only), "
                        "(2) Email digest frequency, (3) Do-not-disturb "
                        "schedules, (4) Escalation alert routing. Teams can "
                        "override defaults at the workspace level."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to configure default templates and workflows for each team?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Template configuration: (1) Create standardized "
                        "project templates per department, (2) Define default "
                        "workflow stages (backlog → in progress → review → "
                        "done), (3) Set up automation rules for common actions, "
                        "(4) Configure default views and filters."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What security and compliance settings must be configured?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Security configuration: (1) Password policy and MFA "
                        "requirements, (2) IP allowlist for organization "
                        "admin access, (3) Data retention policies, "
                        "(4) Audit log configuration, (5) Compliance reporting "
                        "schedule (SOC 2, GDPR, etc.)."
                    ),
                },
                {
                    "id": "sq7",
                    "text": "How to validate the complete workspace configuration?",
                    "dependencies": ["sq3", "sq4", "sq5", "sq6"],
                    "is_parallel": False,
                    "answer": (
                        "Validation checklist: (1) All teams created with "
                        "correct members, (2) Permission inheritance verified, "
                        "(3) Cross-team channels accessible, (4) Notifications "
                        "routed correctly, (5) Templates available, "
                        "(6) Security policies enforced. Run a pilot with "
                        "2-3 teams before full rollout."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2] → [parallel: sq3, sq4, sq5, sq6] → sq7"
            ),
            "final_synthesis": (
                "Workspace configuration plan: Define organizational hierarchy "
                "(sq1) and establish role/permission model (sq2). Configure "
                "cross-team collaboration (sq3), notifications (sq4), templates "
                "(sq5), and security settings (sq6) in parallel. Validate the "
                "complete setup with a pilot rollout (sq7)."
            ),
        },
        # Template 2: Security and access control configuration
        {
            "name": "security_access_control_config",
            "trigger_keywords": [
                "security", "access control", "permission", "sso",
                "mfa", "authentication", "authorization", "policy",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What authentication methods should be configured?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Authentication configuration: (1) Email/password as "
                        "baseline, (2) Multi-factor authentication (TOTP, SMS), "
                        "(3) SSO via SAML 2.0 or OIDC for enterprise, "
                        "(4) Social login (Google, Microsoft) for convenience. "
                        "MFA should be mandatory for admin roles."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What is the role-based access control (RBAC) model?",
                    "dependencies": [],
                    "is_parallel": True,
                    "answer": (
                        "RBAC model defines permissions per role: Admin (all "
                        "permissions), Manager (team management + content), "
                        "Editor (create + edit own content), Viewer (read-only). "
                        "Each role maps to a set of granular permissions that "
                        "can be further customized."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What IP and network-level restrictions are needed?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Network restrictions: (1) IP allowlist for admin "
                        "console access, (2) VPN requirement for sensitive "
                        "operations, (3) Geo-blocking for non-business regions, "
                        "(4) Rate limiting per IP. These are configured in the "
                        "security settings with CIDR notation."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What audit and compliance logging is required?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Audit logging: (1) User login/logout events, "
                        "(2) Permission changes, (3) Data access patterns, "
                        "(4) Configuration modifications, (5) Export events. "
                        "Logs should be retained per compliance requirements "
                        "(typically 90 days to 1 year)."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to configure session management and token policies?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Session policies: (1) Session timeout (30 min idle, "
                        "8 hour absolute), (2) Concurrent session limits, "
                        "(3) Token refresh rotation, (4) Automatic logout on "
                        "password change, (5) Device fingerprinting for "
                        "sensitive operations."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What incident response procedures should be documented?",
                    "dependencies": ["sq3", "sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Incident response: (1) Defined severity levels and "
                        "escalation paths, (2) Automated alerting for suspicious "
                        "activity (brute force, privilege escalation), "
                        "(3) Account lockdown procedure, (4) Forensic data "
                        "preservation, (5) Post-incident review template."
                    ),
                },
            ],
            "dependency_chain": (
                "[parallel: sq1, sq2] → [parallel: sq3, sq4] → sq5 → sq6"
            ),
            "final_synthesis": (
                "Security configuration plan: Set up authentication methods "
                "(sq1) and RBAC model (sq2) in parallel. Configure network "
                "restrictions (sq3) and audit logging (sq4). Establish "
                "session management policies (sq5) and document incident "
                "response procedures (sq6)."
            ),
        },
        # Template 3: Notification and alert configuration
        {
            "name": "notification_alert_configuration",
            "trigger_keywords": [
                "notification", "alert", "notify", "warning", "trigger",
                "pagerduty", "slack alert", "email alert", "monitor",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What events should trigger notifications?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Notification triggers by category: (1) System: "
                        "downtime, error spikes, deployment events, "
                        "(2) Business: new signup, payment failure, churn risk, "
                        "(3) Security: failed logins, permission changes, "
                        "(4) Workflow: task assigned, approval required, "
                        "SLA breach. Each trigger needs severity assignment."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What notification channels should be configured?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Channel selection by urgency: Critical → PagerDuty/"
                        "phone call + Slack + email. High → Slack + email. "
                        "Medium → Slack channel. Low → email digest. Each "
                        "channel requires separate integration setup."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What are the routing and escalation rules?",
                    "dependencies": ["sq1", "sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Routing rules: (1) Route by service/component owner, "
                        "(2) On-call rotation for after-hours, (3) Escalation "
                        "chain: L1 (5 min) → L2 (15 min) → L3 (30 min), "
                        "(4) Auto-acknowledge for known issues. Rules are "
                        "configured as condition → action pairs."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to prevent alert fatigue and noise?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Alert fatigue prevention: (1) Aggregation of related "
                        "alerts, (2) Deduplication of identical alerts, "
                        "(3) Suppression windows for planned maintenance, "
                        "(4) Severity threshold tuning, (5) Regular review "
                        "and pruning of unused alert rules."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to test and validate the notification configuration?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Testing approach: (1) Send test notifications for "
                        "each channel and severity level, (2) Simulate alert "
                        "scenarios in staging, (3) Verify escalation timing, "
                        "(4) Confirm on-call rotation works correctly, "
                        "(5) Review notification delivery metrics for the "
                        "first week after deployment."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4] → sq5"
            ),
            "final_synthesis": (
                "Notification configuration plan: Define trigger events "
                "(sq1) and configure delivery channels (sq2). Set up routing "
                "and escalation rules (sq3) while implementing alert fatigue "
                "prevention (sq4). Validate the entire configuration with "
                "testing (sq5) before going live."
            ),
        },
    ],
    # ──── INTEGRATION ───────────────────────────────────────────────
    TaskDomain.INTEGRATION: [
        # Template 1: Third-party tool integration
        {
            "name": "third_party_tool_integration",
            "trigger_keywords": [
                "third party", "connect tool", "integration", "plugin",
                "slack", "jira", "salesforce", "hubspot", "zapier",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "Which third-party tools need to be integrated?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Tool inventory: list all third-party tools requested, "
                        "categorized by function (communication, CRM, project "
                        "management, analytics, etc.). Prioritize by business "
                        "impact and usage frequency. Check platform marketplace "
                        "for native integration availability."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What authentication and authorization is required for each tool?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Auth requirements per tool: (1) API key vs. OAuth 2.0 "
                        "vs. SAML, (2) Required scopes and permissions, "
                        "(3) Token refresh mechanism, (4) Credential storage "
                        "(secure vault recommended). Each tool's documentation "
                        "specifies the supported auth flow."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What data flows in each direction for each integration?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Data flow mapping: (1) Inbound data — what the "
                        "third-party sends to our platform (events, records), "
                        "(2) Outbound data — what we send to the third-party "
                        "(notifications, updates), (3) Data transformation "
                        "rules, (4) Sync frequency (real-time, batch, webhook)."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to handle error cases and retry logic?",
                    "dependencies": ["sq2", "sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Error handling: (1) Retry with exponential backoff "
                        "(3 retries, max 5 min delay), (2) Dead letter queue "
                        "for permanently failed messages, (3) Alert on "
                        "sustained failure (> 5 min), (4) Circuit breaker "
                        "pattern for downstream outages, (5) Manual replay "
                        "capability for queued items."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What is the configuration and setup process for each tool?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Setup process: (1) Register application in third-party "
                        "developer console, (2) Configure callback URLs and "
                        "webhook endpoints, (3) Map fields between systems, "
                        "(4) Test in sandbox/staging environment, "
                        "(5) Enable in production with monitoring."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to monitor integration health and performance?",
                    "dependencies": ["sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Monitoring setup: (1) Track sync latency and success "
                        "rate per integration, (2) Alert on error rate > 1%, "
                        "(3) Monitor API rate limit usage, (4) Log all "
                        "integration events for debugging, (5) Weekly health "
                        "report summarizing integration status across all tools."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq5] → sq4 → sq6"
            ),
            "final_synthesis": (
                "Third-party integration plan: Inventory required tools (sq1), "
                "configure authentication (sq2). Map data flows (sq3) and set "
                "up each tool (sq5) in parallel. Implement error handling and "
                "retry logic (sq4), then establish monitoring (sq6) for "
                "ongoing health visibility."
            ),
        },
        # Template 2: API integration setup
        {
            "name": "api_integration_setup",
            "trigger_keywords": [
                "api", "endpoint", "rest", "graphql", "webhook",
                "api key", "api setup", "developer",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the API specification and available endpoints?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "API discovery: review the provider's API documentation "
                        "for available endpoints, request/response schemas, "
                        "authentication method, rate limits, and versioning "
                        "policy. Determine if REST, GraphQL, or gRPC is used."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What are the rate limits and quota constraints?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Rate limit assessment: (1) Requests per second/minute/"
                        "hour, (2) Payload size limits, (3) Daily/monthly "
                        "quotas, (4) Rate limit headers to monitor. If limits "
                        "are insufficient, request a quota increase or implement "
                        "request batching."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "How to implement authentication and secure credential storage?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Security implementation: (1) Use OAuth 2.0 client "
                        "credentials flow for server-to-server, (2) Store tokens "
                        "in encrypted secret manager (not in code), "
                        "(3) Implement automatic token rotation, "
                        "(4) Use TLS for all API calls."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What data models need to be mapped between systems?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Data mapping: create a field mapping document "
                        "comparing source and target data models. Handle: "
                        "naming convention differences, type conversions, "
                        "enum translations, nested object flattening, and "
                        "pagination for list endpoints."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to implement webhook receivers for event-driven updates?",
                    "dependencies": ["sq3"],
                    "is_parallel": False,
                    "answer": (
                        "Webhook setup: (1) Create endpoint with signature "
                        "verification, (2) Implement idempotent processing "
                        "(dedup by event ID), (3) Return 200 immediately and "
                        "process asynchronously, (4) Provide retry endpoint, "
                        "(5) Log all webhook events for audit."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to test the API integration end-to-end?",
                    "dependencies": ["sq2", "sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Testing strategy: (1) Unit tests for data "
                        "transformation logic, (2) Integration tests against "
                        "sandbox environment, (3) Load test to verify behavior "
                        "under rate limits, (4) Failure scenario testing "
                        "(timeout, 5xx, malformed response), (5) End-to-end "
                        "test with real data flow."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3, sq4] → sq5 → sq6"
            ),
            "final_synthesis": (
                "API integration plan: Review API specification (sq1), assess "
                "rate limits (sq2). Implement security (sq3) and data mapping "
                "(sq4) in parallel. Set up webhook receivers (sq5), then "
                "execute comprehensive testing (sq6) before production "
                "deployment."
            ),
        },
        # Template 3: Workflow automation integration
        {
            "name": "workflow_automation_integration",
            "trigger_keywords": [
                "automation", "workflow", "trigger", "action", "rule",
                "if then", "automate", "process",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What business processes need automation?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Process inventory: document current manual workflows, "
                        "identify repetitive tasks, measure time spent per task. "
                        "Prioritize automation candidates by: frequency, time "
                        "savings, error reduction potential, and complexity."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What triggers and conditions define each automation?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Trigger definition: (1) Event-based triggers (new "
                        "record, status change, form submission), "
                        "(2) Schedule-based triggers (daily, weekly), "
                        "(3) Condition filters (field value, user role, "
                        "time of day). Each trigger should be specific to "
                        "avoid unintended activations."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What actions should each automation perform?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Action types: (1) Create/update records, "
                        "(2) Send notifications (email, Slack, SMS), "
                        "(3) Assign tasks or change ownership, "
                        "(4) Call external APIs, (5) Update fields based on "
                        "formula. Complex automations chain multiple actions "
                        "with conditional branching."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What error handling and rollback is needed?",
                    "dependencies": ["sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Error handling: (1) Define failure behavior per "
                        "action (skip, retry, notify admin), (2) Implement "
                        "compensating actions for rollback, (3) Log all "
                        "automation execution with status, (4) Set up alerts "
                        "for repeated failures, (5) Manual override capability."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How to test and monitor the automated workflows?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Testing: (1) Unit test each action independently, "
                        "(2) Integration test complete workflow, "
                        "(3) Edge case testing (empty data, concurrent runs), "
                        "(4) Performance test under expected load. "
                        "Monitoring: track execution count, success rate, "
                        "average duration, and error frequency."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4] → sq5"
            ),
            "final_synthesis": (
                "Workflow automation plan: Identify processes to automate "
                "(sq1), define triggers and conditions (sq2). Implement "
                "actions (sq3) and error handling (sq4) in parallel. Test "
                "and deploy with monitoring (sq5) to ensure reliable "
                "operation."
            ),
        },
    ],
    # ──── REPORTING ─────────────────────────────────────────────────
    TaskDomain.REPORTING: [
        # Template 1: Custom report creation
        {
            "name": "custom_report_creation",
            "trigger_keywords": [
                "custom report", "create report", "build report",
                "report template", "report design", "new report",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the report purpose and target audience?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Define: (1) Business question the report answers, "
                        "(2) Primary audience (executives, managers, analysts), "
                        "(3) Required granularity (daily/weekly/monthly), "
                        "(4) Decision this report informs. This shapes all "
                        "subsequent design choices."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What data sources and metrics are needed?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Data requirements: (1) Source systems (database, API, "
                        "spreadsheet), (2) Specific metrics and KPIs, "
                        "(3) Dimensions for grouping/filtering, "
                        "(4) Time range and comparison periods. Create a "
                        "data dictionary mapping each metric to its source."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What visualizations and layout should be used?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Visualization selection: (1) Trends over time → line "
                        "chart, (2) Comparison → bar chart, (3) Composition → "
                        "pie/stacked bar, (4) Distribution → histogram, "
                        "(5) Correlation → scatter plot. Layout: executive "
                        "summary at top, supporting details below."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What filters and parameters should be configurable?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Configurable parameters: (1) Date range selector, "
                        "(2) Department/team filter, (3) Metric toggle, "
                        "(4) Comparison period selector, (5) Threshold/target "
                        "line. Default values should show the most common "
                        "view while allowing drill-down."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "How should the report be scheduled and distributed?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Distribution plan: (1) Schedule frequency (daily "
                        "automated, weekly manual review), (2) Delivery "
                        "channels (email PDF, dashboard link, Slack), "
                        "(3) Recipient list with access controls, "
                        "(4) Version history and annotation support."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to validate report accuracy and completeness?",
                    "dependencies": ["sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Validation: (1) Cross-check totals against source "
                        "system, (2) Verify filter logic with sample scenarios, "
                        "(3) Test date boundary conditions, (4) Review with "
                        "stakeholders for accuracy, (5) Establish a QA "
                        "checklist for ongoing report maintenance."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4] → sq5 → sq6"
            ),
            "final_synthesis": (
                "Report creation plan: Define purpose and audience (sq1), "
                "identify data sources and metrics (sq2). Design visualizations "
                "(sq3) and configurable filters (sq4) in parallel. Set up "
                "scheduling and distribution (sq5), then validate accuracy "
                "(sq6) before sharing with stakeholders."
            ),
        },
        # Template 2: Dashboard setup
        {
            "name": "dashboard_setup",
            "trigger_keywords": [
                "dashboard", "overview", "metrics view", "kpi dashboard",
                "real-time", "control panel", "command center",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "Who are the dashboard users and what decisions does it support?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "User persona analysis: (1) Executive — high-level "
                        "KPIs and trend indicators, (2) Manager — team "
                        "performance and resource allocation, (3) Analyst — "
                        "detailed metrics with drill-down capability. Each "
                        "persona may need separate dashboard views."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What key metrics and KPIs should be displayed?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "KPI selection: align metrics with business objectives. "
                        "Use the SMART framework (Specific, Measurable, "
                        "Achievable, Relevant, Time-bound). Include: leading "
                        "indicators (predictive) and lagging indicators "
                        "(outcome). Limit to 8-12 primary metrics per view."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What data refresh rate and latency requirements exist?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Refresh requirements: (1) Real-time (< 1 min) for "
                        "operational dashboards, (2) Hourly for tactical views, "
                        "(3) Daily for strategic reports. Balance freshness "
                        "with system load. Use incremental updates for large "
                        "datasets to reduce latency."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to design the dashboard layout for usability?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Layout principles: (1) Most important metrics at top "
                        "left (F-pattern reading), (2) Group related metrics, "
                        "(3) Use consistent color coding, (4) Provide context "
                        "(comparisons, targets), (5) Mobile-responsive design, "
                        "(6) Progressive disclosure for detailed views."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What drill-down and interaction capabilities are needed?",
                    "dependencies": ["sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Interaction design: (1) Click-through to detailed "
                        "views, (2) Tooltip explanations for metrics, "
                        "(3) Date range selector, (4) Dimension filters, "
                        "(5) Export to CSV/PDF, (6) Shareable links with "
                        "preset filters. Each interaction should have clear "
                        "visual affordance."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to set up access controls for the dashboard?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Access control: (1) Role-based view access "
                        "(executive sees all, team lead sees own team), "
                        "(2) Row-level security for sensitive data, "
                        "(3) Guest access with limited metrics, "
                        "(4) Embedding permissions for iframe sharing, "
                        "(5) Audit log for dashboard access events."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4, sq6] → sq5"
            ),
            "final_synthesis": (
                "Dashboard setup plan: Identify users and decisions (sq1), "
                "select KPIs (sq2). Configure refresh rate (sq3), design "
                "layout (sq4), and set access controls (sq6) in parallel. "
                "Implement drill-down interactions (sq5) for a complete "
                "dashboard experience."
            ),
        },
        # Template 3: Analytics pipeline setup
        {
            "name": "analytics_pipeline_setup",
            "trigger_keywords": [
                "analytics", "data pipeline", "etl", "data warehouse",
                "data flow", "event tracking", "funnel", "cohort",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What analytics questions need to be answered?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Requirements gathering: document the specific "
                        "questions the analytics pipeline must answer. "
                        "Categories: user behavior, conversion funnel, "
                        "retention/churn, revenue attribution, product usage. "
                        "Prioritize by business value."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What events and data points need to be tracked?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Event taxonomy: (1) Page view events, "
                        "(2) User action events (click, submit, purchase), "
                        "(3) System events (error, latency), "
                        "(4) Session events (start, end, timeout). Each event "
                        "needs: name, properties, timestamp, user ID."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What is the data pipeline architecture?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Pipeline architecture: (1) Event collection layer "
                        "(SDK, webhook), (2) Event streaming/buffering (Kafka, "
                        "SQS), (3) Transformation/ETL (dbt, custom), "
                        "(4) Storage (data warehouse), (5) Query/visualization "
                        "layer. Design for scalability and fault tolerance."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "How to ensure data quality and consistency?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Data quality controls: (1) Schema validation on "
                        "event ingestion, (2) Deduplication by event ID, "
                        "(3) Anomaly detection for volume spikes, "
                        "(4) Reconciliation with source of truth, "
                        "(5) Data quality dashboards with completeness and "
                        "accuracy metrics."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What privacy and compliance requirements apply?",
                    "dependencies": ["sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Privacy compliance: (1) PII detection and masking "
                        "in event properties, (2) User consent management, "
                        "(3) Right-to-deletion implementation, "
                        "(4) Data retention policies, (5) GDPR/CCPA audit "
                        "trail. Implement privacy at the collection layer "
                        "to prevent PII from entering the pipeline."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to validate end-to-end analytics accuracy?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Validation approach: (1) Instrumented test events "
                        "through the full pipeline, (2) Compare aggregated "
                        "metrics against known ground truth, (3) A/B test "
                        "comparison with legacy tracking, (4) Time-series "
                        "sanity checks (no unexpected drops/spikes), "
                        "(5) Regular data audits (weekly/monthly)."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → sq2 → [parallel: sq3, sq4, sq5] → sq6"
            ),
            "final_synthesis": (
                "Analytics pipeline plan: Define analytics questions (sq1) "
                "and event taxonomy (sq2). Design pipeline architecture (sq3), "
                "data quality controls (sq4), and privacy measures (sq5) in "
                "parallel. Validate end-to-end accuracy (sq6) before "
                "production deployment."
            ),
        },
    ],
    # ──── GENERAL ───────────────────────────────────────────────────
    TaskDomain.GENERAL: [
        # Template 1: Multi-department coordination
        {
            "name": "multi_department_coordination",
            "trigger_keywords": [
                "multiple departments", "cross-functional", "coordinate",
                "collaborate", "team", "department", "stakeholder",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "Which departments are involved and what are their roles?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Stakeholder mapping: identify all involved departments, "
                        "their responsibilities, and decision authority. Create "
                        "a RACI matrix (Responsible, Accountable, Consulted, "
                        "Informed) to clarify ownership at each stage."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What is the shared goal and success criteria?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Alignment: define a clear, measurable objective that "
                        "all departments agree on. Success criteria should be "
                        "quantifiable and time-bound. Document any conflicting "
                        "departmental priorities and negotiate trade-offs "
                        "upfront."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What resources does each department need to contribute?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Resource inventory: (1) Personnel (FTE allocation, "
                        "skills required), (2) Budget per department, "
                        "(3) Tools and systems, (4) Timeline availability. "
                        "Identify resource conflicts early and establish "
                        "escalation for bottlenecks."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What is the communication plan and meeting cadence?",
                    "dependencies": ["sq1", "sq2"],
                    "is_parallel": True,
                    "answer": (
                        "Communication plan: (1) Weekly cross-department "
                        "standup, (2) Bi-weekly stakeholder review, "
                        "(3) Shared Slack channel for async updates, "
                        "(4) Documented decision log, (5) Escalation path "
                        "for blockers. Keep meetings focused on decisions, "
                        "not status updates."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What is the project timeline with departmental milestones?",
                    "dependencies": ["sq2", "sq3"],
                    "is_parallel": False,
                    "answer": (
                        "Timeline: create a Gantt-style view with critical path "
                        "analysis. Assign department-specific milestones with "
                        "clear handoff criteria. Include buffer time (15-20%) "
                        "for inter-departmental dependencies. Define the "
                        "minimum viable first delivery."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "How to track progress and handle inter-department blockers?",
                    "dependencies": ["sq4", "sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Tracking: (1) Shared project board visible to all "
                        "departments, (2) Automated status reports, "
                        "(3) Blocker escalation within 24 hours, "
                        "(4) Cross-department retrospective at each milestone, "
                        "(5) Defined RACI for issue resolution. Transparency "
                        "prevents siloed work."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3] → [parallel: sq4] → [parallel: sq5] → sq6"
            ),
            "final_synthesis": (
                "Coordination plan: Map stakeholders and RACI (sq1), define "
                "shared goals (sq2). Inventory resources (sq3) and establish "
                "communication cadence (sq4). Build the timeline (sq5) and "
                "set up tracking with blocker resolution (sq6) for successful "
                "cross-departmental delivery."
            ),
        },
        # Template 2: Enterprise-scale complex request
        {
            "name": "enterprise_scale_request",
            "trigger_keywords": [
                "enterprise", "scale", "large", "organization-wide",
                "global", "rollout", "deploy", "implement",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the scope and scale of the request?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Scope definition: (1) Geographic coverage (regions, "
                        "countries), (2) User population affected, "
                        "(3) Systems and processes impacted, "
                        "(4) Estimated effort (person-months), "
                        "(5) Budget range. Classify as small/medium/large/"
                        "enterprise to determine governance requirements."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What are the technical requirements and constraints?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Technical assessment: (1) Infrastructure requirements, "
                        "(2) Integration touchpoints, (3) Performance "
                        "requirements (latency, throughput), "
                        "(4) Data handling and storage, "
                        "(5) Compatibility with existing systems. Document "
                        "technical constraints that limit solution options."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What is the rollout strategy (phased vs big bang)?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Rollout strategy: for enterprise-scale, phased "
                        "rollout is strongly recommended. Phases: "
                        "(1) Pilot (1-2 teams, 2 weeks), "
                        "(2) Regional (1 region, 4 weeks), "
                        "(3) Broad (all regions, 4-8 weeks), "
                        "(4) Full (organization-wide). Each phase includes "
                        "feedback collection and iteration."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What training and change management is required?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Change management: (1) Executive sponsorship and "
                        "communication plan, (2) Champion network across "
                        "departments, (3) Training by role (admin, power "
                        "user, end user), (4) Self-serve documentation and "
                        "FAQ, (5) Support escalation during rollout period."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What is the governance and approval process?",
                    "dependencies": ["sq2"],
                    "is_parallel": False,
                    "answer": (
                        "Governance: (1) Steering committee with executive "
                        "sponsors, (2) Stage-gate approval at each phase, "
                        "(3) Risk register and mitigation plans, "
                        "(4) Budget control and variance reporting, "
                        "(5) Compliance and legal review for regulated "
                        "industries."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What success metrics and post-implementation review is planned?",
                    "dependencies": ["sq3", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Success metrics: (1) Adoption rate (% active users), "
                        "(2) Performance vs. baseline, (3) User satisfaction "
                        "(survey NPS), (4) Business outcome metrics, "
                        "(5) Support ticket volume. Post-implementation "
                        "review at 30, 60, and 90 days."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3, sq4] → sq5 → sq6"
            ),
            "final_synthesis": (
                "Enterprise rollout plan: Define scope and scale (sq1). "
                "Assess technical requirements (sq2), choose rollout strategy "
                "(sq3), and prepare change management (sq4) in parallel. "
                "Establish governance (sq5) and define success metrics with "
                "post-implementation review schedule (sq6)."
            ),
        },
        # Template 3: Complex multi-step troubleshooting
        {
            "name": "complex_troubleshooting",
            "trigger_keywords": [
                "troubleshoot", "debug", "fix", "issue", "problem",
                "broken", "not working", "error", "complex issue",
            ],
            "sub_queries": [
                {
                    "id": "sq1",
                    "text": "What is the exact symptom and when did it start?",
                    "dependencies": [],
                    "is_parallel": False,
                    "answer": (
                        "Symptom documentation: (1) Exact error messages or "
                        "unexpected behavior, (2) When the issue was first "
                        "observed, (3) Whether it is consistent or "
                        "intermittent, (4) Percentage of users/requests "
                        "affected. Precise symptom definition prevents "
                        "misdiagnosis."
                    ),
                },
                {
                    "id": "sq2",
                    "text": "What changed recently that could have caused this?",
                    "dependencies": ["sq1"],
                    "is_parallel": False,
                    "answer": (
                        "Change analysis: (1) Recent deployments/releases, "
                        "(2) Configuration changes, (3) Infrastructure "
                        "modifications, (4) Third-party service updates, "
                        "(5) Data volume changes. Correlate change timeline "
                        "with issue onset. If no changes found, investigate "
                        "external factors."
                    ),
                },
                {
                    "id": "sq3",
                    "text": "What components and services are involved?",
                    "dependencies": ["sq1"],
                    "is_parallel": True,
                    "answer": (
                        "Component mapping: trace the request path through "
                        "all involved services. Identify: (1) Frontend "
                        "client, (2) API gateway, (3) Application services, "
                        "(4) Database/cache, (5) External integrations. "
                        "Narrow the component scope to isolate the failure."
                    ),
                },
                {
                    "id": "sq4",
                    "text": "What do the logs and metrics show?",
                    "dependencies": ["sq3"],
                    "is_parallel": True,
                    "answer": (
                        "Log analysis: (1) Search for error patterns around "
                        "the issue timeframe, (2) Check latency spikes, "
                        "error rate increases, and resource utilization, "
                        "(3) Correlate across services using trace IDs, "
                        "(4) Look for OOM, connection pool exhaustion, or "
                        "timeout patterns."
                    ),
                },
                {
                    "id": "sq5",
                    "text": "What is the root cause hypothesis and how to verify it?",
                    "dependencies": ["sq2", "sq4"],
                    "is_parallel": False,
                    "answer": (
                        "Root cause analysis: (1) Formulate hypothesis based "
                        "on evidence from sq2 and sq4, (2) Identify "
                        "reproduction steps, (3) Verify in staging if "
                        "possible, (4) Rule out alternative hypotheses. "
                        "Use the 5 Whys technique to trace to fundamental "
                        "cause."
                    ),
                },
                {
                    "id": "sq6",
                    "text": "What is the fix and how to prevent recurrence?",
                    "dependencies": ["sq5"],
                    "is_parallel": False,
                    "answer": (
                        "Resolution: (1) Implement immediate fix, "
                        "(2) Add monitoring/alerting for early detection, "
                        "(3) Update runbook with new troubleshooting steps, "
                        "(4) Schedule preventive measures (e.g., circuit "
                        "breaker, retry logic, additional logging), "
                        "(5) Conduct blameless post-mortem with team."
                    ),
                },
            ],
            "dependency_chain": (
                "sq1 → [parallel: sq2, sq3] → sq4 → sq5 → sq6"
            ),
            "final_synthesis": (
                "Troubleshooting plan: Document symptoms precisely (sq1), "
                "analyze recent changes (sq2) and map components (sq3) in "
                "parallel. Examine logs and metrics (sq4), form and verify "
                "root cause hypothesis (sq5), then implement fix with "
                "preventive measures (sq6)."
            ),
        },
    ],
}


# ── Data Structures ──────────────────────────────────────────────────


@dataclass
class SubQuery:
    """A single sub-query within the decomposition pipeline.

    Attributes:
        id: Unique identifier (e.g. 'sq1').
        text: The sub-query question text.
        status: Current lifecycle status.
        dependencies: List of sub-query IDs this depends on.
        result: Solved result text.
        order: Position in execution sequence.
        is_parallel: Whether this can execute alongside peers.
    """

    id: str = ""
    text: str = ""
    status: SubQueryStatus = SubQueryStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    result: str = ""
    order: int = 0
    is_parallel: bool = False


@dataclass
class DependencyGraph:
    """Directed acyclic graph of sub-query dependencies.

    Attributes:
        sub_queries: All sub-queries in the graph.
        execution_order: Ordered list of parallel groups (lists of sq IDs).
        has_cycles: Whether a dependency cycle was detected.
    """

    sub_queries: List[SubQuery] = field(default_factory=list)
    execution_order: List[List[str]] = field(default_factory=list)
    has_cycles: bool = False


@dataclass(frozen=True)
class LeastToMostConfig:
    """Immutable configuration for Least-to-Most Decomposition (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        max_sub_queries: Maximum number of sub-queries to generate.
        min_sub_queries: Minimum number of sub-queries to generate.
        enable_dependency_check: Whether to run cycle detection.
    """

    company_id: str = ""
    max_sub_queries: int = 8
    min_sub_queries: int = 3
    enable_dependency_check: bool = True


@dataclass
class LeastToMostResult:
    """Output of the Least-to-Most pipeline.

    Attributes:
        sub_queries: All generated sub-queries with their status.
        dependency_graph: Serialized dependency graph information.
        solved_results: List of {id, result} dicts for solved sub-queries.
        final_answer: Combined comprehensive answer.
        completeness_check: Results of the completeness verification.
        steps_applied: Names of pipeline steps executed.
        confidence_boost: Estimated confidence increase from this process.
    """

    sub_queries: List[SubQuery] = field(default_factory=list)
    dependency_graph: Dict[str, Any] = field(default_factory=dict)
    solved_results: List[Dict[str, str]] = field(default_factory=list)
    final_answer: str = ""
    completeness_check: Dict[str, Any] = field(default_factory=dict)
    steps_applied: List[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "sub_queries": [
                {
                    "id": sq.id,
                    "text": sq.text,
                    "status": sq.status.value,
                    "dependencies": sq.dependencies,
                    "result": sq.result,
                    "order": sq.order,
                    "is_parallel": sq.is_parallel,
                }
                for sq in self.sub_queries
            ],
            "dependency_graph": self.dependency_graph,
            "solved_results": self.solved_results,
            "final_answer": self.final_answer,
            "completeness_check": self.completeness_check,
            "steps_applied": self.steps_applied,
            "confidence_boost": round(self.confidence_boost, 4),
        }


# ── Least-to-Most Processor ─────────────────────────────────────────


class LeastToMostProcessor:
    """
    Deterministic Least-to-Most processor (F-148).

    Uses pattern matching and heuristic rules to decompose complex
    queries into sub-queries, order them by dependency, solve
    sequentially, and combine results — all without any LLM calls.

    Pipeline:
      1. Decomposition          — pattern-match domain, select template
      2. Dependency Ordering    — topological sort, cycle detection
      3. Sequential Solving     — solve in order, feed results forward
      4. Result Combination     — synthesize all results into answer
      5. Completeness Check     — verify all sub-queries addressed
    """

    def __init__(
        self, config: Optional[LeastToMostConfig] = None,
    ):
        self.config = config or LeastToMostConfig()

    # ── Step 1: Decomposition ──────────────────────────────────────

    async def decompose_query(self, query: str) -> List[SubQuery]:
        """
        Break a complex query into sub-queries using template matching.

        Identifies the task domain from the query text, selects the
        best-matching decomposition template, and instantiates sub-query
        objects with dependency information.

        Args:
            query: The user's complex query text.

        Returns:
            List of SubQuery objects representing the decomposition.
        """
        if not query or not query.strip():
            return []

        domain = self._detect_domain(query)
        template = self._select_template(domain, query)

        if template is None:
            # Fallback: generate generic sub-queries
            return self._generate_generic_sub_queries(query)

        sub_queries: List[SubQuery] = []
        for idx, sq_def in enumerate(template["sub_queries"]):
            sq = SubQuery(
                id=sq_def["id"],
                text=sq_def["text"],
                status=SubQueryStatus.PENDING,
                dependencies=list(sq_def.get("dependencies", [])),
                result=sq_def.get("answer", ""),
                order=idx + 1,
                is_parallel=sq_def.get("is_parallel", False),
            )
            sub_queries.append(sq)

        # Enforce config limits
        if len(sub_queries) > self.config.max_sub_queries:
            sub_queries = sub_queries[: self.config.max_sub_queries]

        return sub_queries

    # ── Step 2: Dependency Ordering ───────────────────────────────

    async def order_dependencies(
        self, sub_queries: List[SubQuery],
    ) -> DependencyGraph:
        """
        Build a dependency graph and compute topological execution order.

        Uses Kahn's algorithm for topological sorting. Detects cycles
        and identifies parallel execution groups (sub-queries whose
        dependencies are fully resolved at the same time).

        Args:
            sub_queries: List of SubQuery objects from decomposition.

        Returns:
            DependencyGraph with execution_order and cycle detection.
        """
        if not sub_queries:
            return DependencyGraph()

        # Build adjacency structures
        sq_map: Dict[str, SubQuery] = {sq.id: sq for sq in sub_queries}
        in_degree: Dict[str, int] = {sq.id: 0 for sq in sub_queries}
        dependents: Dict[str, List[str]] = {sq.id: [] for sq in sub_queries}

        for sq in sub_queries:
            valid_deps: List[str] = []
            for dep_id in sq.dependencies:
                if dep_id in sq_map:
                    in_degree[sq.id] += 1
                    dependents[dep_id].append(sq.id)
                    valid_deps.append(dep_id)
            sq.dependencies = valid_deps  # prune invalid deps

        # Kahn's algorithm with parallel group tracking
        execution_order: List[List[str]] = []
        queue: deque[str] = deque()

        # Seed with nodes that have no dependencies
        for sq_id, degree in in_degree.items():
            if degree == 0:
                queue.append(sq_id)

        has_cycles = False
        processed_count = 0

        while queue:
            # All nodes currently in the queue form one parallel group
            current_group: List[str] = []
            group_size = len(queue)

            for _ in range(group_size):
                current_node = queue.popleft()
                current_group.append(current_node)
                processed_count += 1

                for dependent_id in dependents[current_node]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            if current_group:
                execution_order.append(sorted(current_group))

        # Cycle detection: if not all nodes processed, there is a cycle
        if processed_count < len(sub_queries):
            has_cycles = True
            # Find cycle members for reporting
            unprocessed = [
                sq_id for sq_id, degree in in_degree.items() if degree > 0
            ]
            logger.warning(
                "least_to_most_cycle_detected",
                cycle_nodes=str(unprocessed),
                company_id=self.config.company_id,
            )
            # Mark blocked sub-queries
            for sq_id in unprocessed:
                if sq_id in sq_map:
                    sq_map[sq_id].status = SubQueryStatus.BLOCKED

        # Assign execution order to sub-queries
        for group_idx, group in enumerate(execution_order):
            for sq_id in group:
                if sq_id in sq_map:
                    sq_map[sq_id].order = group_idx + 1
                    # Mark as parallel if group has more than one member
                    sq_map[sq_id].is_parallel = len(group) > 1

        return DependencyGraph(
            sub_queries=list(sq_map.values()),
            execution_order=execution_order,
            has_cycles=has_cycles,
        )

    # ── Step 3: Sequential Solving ─────────────────────────────────

    async def solve_sequentially(
        self, graph: DependencyGraph,
    ) -> List[Dict[str, str]]:
        """
        Solve sub-queries in dependency order.

        Processes each parallel group sequentially. Within a group,
        all sub-queries are solved independently. Solved results from
        earlier groups are available as context for later groups.

        Args:
            graph: DependencyGraph with ordered execution groups.

        Returns:
            List of dicts with 'id' and 'result' for each solved sub-query.
        """
        if not graph or not graph.execution_order:
            return []

        sq_map: Dict[str, SubQuery] = {
            sq.id: sq for sq in graph.sub_queries
        }
        results: List[Dict[str, str]] = []
        solved_context: Dict[str, str] = {}

        for group_idx, group in enumerate(graph.execution_order):
            for sq_id in group:
                sq = sq_map.get(sq_id)
                if sq is None or sq.status == SubQueryStatus.BLOCKED:
                    continue

                sq.status = SubQueryStatus.IN_PROGRESS

                # Solve: use pre-computed answer from template
                # In a real system, this would involve LLM calls or
                # tool execution. Here we use deterministic answers.
                result = self._solve_sub_query(sq, solved_context)

                sq.result = result
                sq.status = SubQueryStatus.SOLVED
                solved_context[sq_id] = result

                results.append({"id": sq_id, "result": result})

            logger.debug(
                "least_to_most_group_solved",
                group_index=group_idx,
                group_size=len(group),
                company_id=self.config.company_id,
            )

        return results

    # ── Step 4: Result Combination ─────────────────────────────────

    async def combine_results(
        self,
        results: List[Dict[str, str]],
        query: str,
    ) -> str:
        """
        Combine all sub-query results into a comprehensive answer.

        Builds a structured response that addresses all aspects of
        the original query by weaving together the individual
        sub-query solutions in logical order.

        Args:
            results: List of {id, result} dicts from sequential solving.
            query: The original complex query for context.

        Returns:
            A comprehensive combined answer string.
        """
        if not results:
            return ""

        # Build numbered result sections
        sections: List[str] = []
        for idx, r in enumerate(results, start=1):
            if r.get("result"):
                sections.append(f"{idx}. {r['result']}")

        if not sections:
            return "Decomposition completed but no results were generated."

        combined = (
            "Based on the decomposition of your request into "
            f"{len(results)} sub-queries, here is the comprehensive plan:\n\n"
            + "\n\n".join(sections)
        )

        return combined

    # ── Step 5: Completeness Check ─────────────────────────────────

    async def check_completeness(
        self,
        sub_queries: List[SubQuery],
        results: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Verify that all original query components have been addressed.

        Checks each sub-query for a solved status and non-empty result.
        Produces a completeness report with pass/fail per sub-query
        and an overall score.

        Args:
            sub_queries: All sub-queries from the decomposition.
            results: All solved results from sequential solving.

        Returns:
            Dict with completeness metrics and per-sub-query status.
        """
        if not sub_queries:
            return {
                "is_complete": False,
                "total": 0,
                "solved": 0,
                "blocked": 0,
                "skipped": 0,
                "missing": 0,
                "score": 0.0,
                "details": [],
            }

        result_map: Dict[str, str] = {
            r["id"]: r["result"] for r in results if r.get("id")
        }

        details: List[Dict[str, Any]] = []
        solved_count = 0
        blocked_count = 0
        skipped_count = 0
        missing_count = 0

        for sq in sub_queries:
            has_result = (
                sq.status == SubQueryStatus.SOLVED
                and bool(result_map.get(sq.id, "").strip())
            )

            detail = {
                "id": sq.id,
                "text": sq.text,
                "status": sq.status.value,
                "has_result": has_result,
            }

            if sq.status == SubQueryStatus.SOLVED and has_result:
                solved_count += 1
                detail["check"] = "pass"
            elif sq.status == SubQueryStatus.BLOCKED:
                blocked_count += 1
                detail["check"] = "blocked"
            elif sq.status == SubQueryStatus.SKIPPED:
                skipped_count += 1
                detail["check"] = "skipped"
            else:
                missing_count += 1
                detail["check"] = "fail"

            details.append(detail)

        total = len(sub_queries)
        score = (solved_count / total) if total > 0 else 0.0

        # Determine if there are unresolvable gaps due to cycles
        has_gaps = missing_count > 0 or blocked_count > 0

        return {
            "is_complete": score >= 1.0,
            "total": total,
            "solved": solved_count,
            "blocked": blocked_count,
            "skipped": skipped_count,
            "missing": missing_count,
            "score": round(score, 4),
            "has_gaps": has_gaps,
            "details": details,
        }

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(self, query: str) -> LeastToMostResult:
        """
        Run the full 5-step Least-to-Most decomposition pipeline.

        Args:
            query: The complex query to decompose and solve.

        Returns:
            LeastToMostResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0
        sub_queries: List[SubQuery] = []
        graph = DependencyGraph()
        results: List[Dict[str, str]] = []
        completeness: Dict[str, Any] = {}

        if not query or not query.strip():
            return LeastToMostResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 1: Decomposition
            sub_queries = await self.decompose_query(query)
            if sub_queries:
                steps_applied.append("decomposition")
                logger.info(
                    "least_to_most_decomposition_complete",
                    sub_query_count=len(sub_queries),
                    company_id=self.config.company_id,
                )
            else:
                steps_applied.append("decomposition_fallback")
                logger.warning(
                    "least_to_most_decomposition_empty",
                    company_id=self.config.company_id,
                )
            confidence_boost += 0.1

            # Step 2: Dependency Ordering
            if sub_queries and self.config.enable_dependency_check:
                graph = await self.order_dependencies(sub_queries)
                steps_applied.append("dependency_ordering")
                if graph.has_cycles:
                    steps_applied.append("cycle_detected")
                    logger.warning(
                        "least_to_most_cycle_in_graph",
                        company_id=self.config.company_id,
                    )
                else:
                    logger.info(
                        "least_to_most_dependency_order",
                        parallel_groups=len(graph.execution_order),
                        company_id=self.config.company_id,
                    )
            confidence_boost += 0.05

            # Step 3: Sequential Solving
            if graph.execution_order:
                results = await self.solve_sequentially(graph)
                if results:
                    steps_applied.append("sequential_solving")
                    logger.info(
                        "least_to_most_solving_complete",
                        solved_count=len(results),
                        company_id=self.config.company_id,
                    )
            confidence_boost += 0.1

            # Step 4: Result Combination
            final_answer = await self.combine_results(results, query)
            if final_answer:
                steps_applied.append("result_combination")
            confidence_boost += 0.05

            # Step 5: Completeness Check
            completeness = await self.check_completeness(
                sub_queries, results,
            )
            steps_applied.append("completeness_check")
            if completeness.get("is_complete"):
                confidence_boost += 0.1
            elif completeness.get("score", 0) >= 0.7:
                confidence_boost += 0.05

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "least_to_most_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return LeastToMostResult(
                sub_queries=sub_queries,
                dependency_graph={
                    "execution_order": [g for g in graph.execution_order],
                    "has_cycles": graph.has_cycles,
                },
                solved_results=results,
                final_answer=final_answer if "final_answer" in dir() else "",
                completeness_check=completeness,
                steps_applied=steps_applied + ["error_fallback"]
                if "steps_applied" in dir() else ["error_fallback"],
                confidence_boost=0.0,
            )

        return LeastToMostResult(
            sub_queries=sub_queries,
            dependency_graph={
                "execution_order": [list(g) for g in graph.execution_order],
                "has_cycles": graph.has_cycles,
                "total_sub_queries": len(sub_queries),
                "parallel_group_count": len(graph.execution_order),
            },
            solved_results=results,
            final_answer=final_answer,
            completeness_check=completeness,
            steps_applied=steps_applied,
            confidence_boost=confidence_boost,
        )

    # ── Domain Detection ───────────────────────────────────────────

    @staticmethod
    def _detect_domain(query: str) -> TaskDomain:
        """
        Detect the task domain from the query text using pattern matching.

        Scores each domain by the number of pattern matches and returns
        the highest-scoring domain. Falls back to GENERAL.

        Args:
            query: The user's query text.

        Returns:
            Matched TaskDomain.
        """
        query_lower = query.lower()

        best_domain = _DEFAULT_DOMAIN
        best_score = 0

        domain_scores: Dict[TaskDomain, int] = {}
        for pattern, domain in _DOMAIN_PATTERNS:
            matches = pattern.findall(query_lower)
            if matches:
                domain_scores[domain] = domain_scores.get(domain, 0) + len(matches)

        for domain, score in domain_scores.items():
            if score > best_score:
                best_score = score
                best_domain = domain

        return best_domain

    # ── Template Selection ─────────────────────────────────────────

    def _select_template(
        self,
        domain: TaskDomain,
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best decomposition template for the given domain and query.

        Scores templates by keyword overlap with the query text and
        returns the highest-scoring template.

        Args:
            domain: Detected task domain.
            query: The user's query text.

        Returns:
            Best-matching template dict, or None if no templates exist.
        """
        templates = _DECOMPOSITION_TEMPLATES.get(domain, [])
        if not templates:
            return None

        query_lower = query.lower()
        query_words: Set[str] = set(re.findall(r"\b\w{3,}\b", query_lower))

        best_template: Optional[Dict[str, Any]] = None
        best_score = 0

        for template in templates:
            keywords = template.get("trigger_keywords", [])
            keyword_set: Set[str] = set()
            for kw in keywords:
                keyword_set.update(kw.lower().split())

            # Score: number of keyword words found in query
            overlap = len(query_words & keyword_set)
            if overlap > best_score:
                best_score = overlap
                best_template = template

        # If no keyword match found, use the first template as default
        if best_template is None and templates:
            best_template = templates[0]

        return best_template

    # ── Generic Fallback ───────────────────────────────────────────

    @staticmethod
    def _generate_generic_sub_queries(query: str) -> List[SubQuery]:
        """
        Generate generic sub-queries when no template matches.

        Creates a minimal decomposition based on sentence-level
        analysis of the query.

        Args:
            query: The user's query text.

        Returns:
            List of generic SubQuery objects.
        """
        # Extract question-like segments
        sentences = re.split(r"[.!?;]\s+", query)
        sub_queries: List[SubQuery] = []

        # Core generic sub-queries
        generic_items = [
            {
                "id": "sq1",
                "text": "What is the core objective of this request?",
                "dependencies": [],
                "is_parallel": False,
                "answer": (
                    "The core objective should be extracted from the primary "
                    "statement or question in the request. This defines the "
                    "overall goal that the plan must achieve."
                ),
            },
            {
                "id": "sq2",
                "text": "What are the key components or requirements?",
                "dependencies": ["sq1"],
                "is_parallel": False,
                "answer": (
                    "Key components are the distinct elements mentioned in the "
                    "request. Each component represents a deliverable or "
                    "action item that contributes to the overall objective."
                ),
            },
            {
                "id": "sq3",
                "text": "What is the recommended approach or sequence?",
                "dependencies": ["sq2"],
                "is_parallel": False,
                "answer": (
                    "The recommended approach orders the components logically, "
                    "respecting any dependencies between them. Simpler tasks "
                    "should be completed first to build toward more complex ones."
                ),
            },
            {
                "id": "sq4",
                "text": "What potential issues or risks should be anticipated?",
                "dependencies": ["sq3"],
                "is_parallel": True,
                "answer": (
                    "Common risks include resource constraints, dependency "
                    "delays, scope creep, and communication gaps. Identifying "
                    "these early allows for proactive mitigation planning."
                ),
            },
            {
                "id": "sq5",
                "text": "How to verify successful completion?",
                "dependencies": ["sq3"],
                "is_parallel": True,
                "answer": (
                    "Success verification involves checking each component "
                    "against its requirements, collecting stakeholder feedback, "
                    "and confirming that the core objective has been met."
                ),
            },
        ]

        for idx, item in enumerate(generic_items):
            sub_queries.append(
                SubQuery(
                    id=item["id"],
                    text=item["text"],
                    status=SubQueryStatus.PENDING,
                    dependencies=list(item.get("dependencies", [])),
                    result=item.get("answer", ""),
                    order=idx + 1,
                    is_parallel=item.get("is_parallel", False),
                )
            )

        return sub_queries

    # ── Sub-query Solving ──────────────────────────────────────────

    @staticmethod
    def _solve_sub_query(
        sq: SubQuery,
        solved_context: Dict[str, str],
    ) -> str:
        """
        Solve a single sub-query deterministically.

        Uses the pre-computed answer from the template as the base.
        If earlier sub-queries have been solved, appends a context
        reference to create dependency-aware answers.

        Args:
            sq: The sub-query to solve.
            solved_context: Map of previously solved sub-query results.

        Returns:
            The solved result string.
        """
        # Use the pre-computed template answer
        result = sq.result

        if not result:
            result = (
                f"Analysis for '{sq.text}': This component has been "
                f"identified as part of the decomposition. A detailed "
                f"response requires additional context about your specific "
                f"setup and requirements."
            )

        # Enhance with dependency context if available
        if sq.dependencies and solved_context:
            context_refs: List[str] = []
            for dep_id in sq.dependencies:
                if dep_id in solved_context:
                    dep_result = solved_context[dep_id]
                    # Extract first sentence as context summary
                    first_sentence = dep_result.split(".")[0].strip()
                    context_refs.append(first_sentence)

            if context_refs:
                result += (
                    "\n\nBuilding on previous findings: "
                    + "; ".join(context_refs) + "."
                )

        return result


# ── Least-to-Most Node (LangGraph compatible) ─────────────────────


class LeastToMostNode(BaseTechniqueNode):
    """
    F-148: Least-to-Most Decomposition — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation triggers:
      - query_complexity > 0.7, OR
      - Task has 5+ identifiable sub-steps, OR
      - Multi-department coordination required, OR
      - Enterprise-scale request with multiple components
    """

    def __init__(
        self, config: Optional[LeastToMostConfig] = None,
    ):
        self._config = config or LeastToMostConfig()
        self._processor = LeastToMostProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.LEAST_TO_MOST

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Least-to-Most should activate.

        Triggers when query complexity is high (> 0.7), indicating
        a complex query that benefits from decomposition.
        """
        return state.signals.query_complexity > 0.7

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Least-to-Most decomposition pipeline.

        Implements the 5-step process:
          1. Decomposition — break into sub-queries
          2. Dependency Ordering — topological sort
          3. Sequential Solving — solve in order
          4. Result Combination — synthesize answer
          5. Completeness Check — verify coverage

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            result = await self._processor.process(state.query)

            # Build confidence-adjusted signals
            new_confidence = min(
                state.signals.confidence_score + result.confidence_boost,
                1.0,
            )

            # Record result in state
            self.record_result(state, result.to_dict())

            # Update confidence score in signals
            state.signals.confidence_score = new_confidence

            # If we have a comprehensive answer, append to response parts
            if result.final_answer:
                state.response_parts.append(result.final_answer)

            # Log completeness status
            completeness = result.completeness_check
            if completeness.get("has_gaps"):
                logger.info(
                    "least_to_most_completeness_gaps",
                    score=completeness.get("score", 0),
                    missing=completeness.get("missing", 0),
                    blocked=completeness.get("blocked", 0),
                    company_id=self._config.company_id,
                )
            else:
                logger.info(
                    "least_to_most_complete",
                    score=completeness.get("score", 0),
                    sub_queries=completeness.get("total", 0),
                    company_id=self._config.company_id,
                )

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "least_to_most_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state
