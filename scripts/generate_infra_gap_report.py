"""
PARWA Infrastructure Gap Analysis Report Generator
Generates a comprehensive PDF report of infrastructure gaps.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import SimpleDocTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# -- Font Registration --
pdfmetrics.registerFont(
    TTFont('Times New Roman',
           '/usr/share/fonts/truetype/english/Times-New-Roman.ttf'))
pdfmetrics.registerFont(
    TTFont('Calibri', '/usr/share/fonts/truetype/english/calibri-regular.ttf'))
registerFontFamily('Times New Roman', normal='Times New Roman',
                   bold='Times New Roman')
registerFontFamily('Calibri', normal='Calibri', bold='Calibri')

# -- Colors --
DARK_BLUE = colors.HexColor('#1F4E79')
ROW_ODD = colors.HexColor('#F5F5F5')
WHITE = colors.white
BLACK = colors.black
RED_TEXT = colors.HexColor('#C0392B')
AMBER_TEXT = colors.HexColor('#856404')

# -- Output --
OUTPUT_DIR = "/home/z/my-project/parwa/download"
os.makedirs(OUTPUT_DIR, exist_ok=True)
PDF_PATH = os.path.join(OUTPUT_DIR, "PARWA_Infrastructure_Gap_Analysis.pdf")

# -- Styles --
cover_title_style = ParagraphStyle(
    name='CoverTitle', fontName='Times New Roman', fontSize=36,
    leading=44, alignment=TA_CENTER, spaceAfter=24, textColor=DARK_BLUE)

cover_subtitle_style = ParagraphStyle(
    name='CoverSubtitle', fontName='Times New Roman', fontSize=18,
    leading=26, alignment=TA_CENTER, spaceAfter=12, textColor=BLACK)

cover_info_style = ParagraphStyle(
    name='CoverInfo', fontName='Times New Roman', fontSize=13,
    leading=20, alignment=TA_CENTER, spaceAfter=8,
    textColor=colors.HexColor('#555555'))

h1_style = ParagraphStyle(
    name='H1', fontName='Times New Roman', fontSize=20,
    leading=26, spaceBefore=18, spaceAfter=10, textColor=DARK_BLUE)

h2_style = ParagraphStyle(
    name='H2', fontName='Times New Roman', fontSize=15,
    leading=20, spaceBefore=14, spaceAfter=8, textColor=DARK_BLUE)

h3_style = ParagraphStyle(
    name='H3', fontName='Times New Roman', fontSize=12,
    leading=16, spaceBefore=10, spaceAfter=6, textColor=BLACK)

body_style = ParagraphStyle(
    name='Body', fontName='Times New Roman', fontSize=10.5,
    leading=16, alignment=TA_JUSTIFY, spaceAfter=6)

th_style = ParagraphStyle(
    name='TH', fontName='Times New Roman', fontSize=9.5,
    leading=13, alignment=TA_CENTER, textColor=WHITE)

td_style = ParagraphStyle(
    name='TD', fontName='Times New Roman', fontSize=9,
    leading=12, alignment=TA_LEFT, textColor=BLACK)

td_center = ParagraphStyle(
    name='TDC', fontName='Times New Roman', fontSize=9,
    leading=12, alignment=TA_CENTER, textColor=BLACK)

td_just = ParagraphStyle(
    name='TDJ', fontName='Times New Roman', fontSize=9,
    leading=12, alignment=TA_JUSTIFY, textColor=BLACK)

caption_style = ParagraphStyle(
    name='Caption', fontName='Times New Roman', fontSize=9,
    leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#666666'),
    spaceBefore=3, spaceAfter=6)


def make_table(data, col_widths, caption_text=None):
    """Create a styled table with standard PARWA color scheme."""
    n_rows = len(data)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, n_rows):
        bg = WHITE if i % 2 == 1 else ROW_ODD
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle(style_cmds))
    elements = [Spacer(1, 18), t]
    if caption_text:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(caption_text, caption_style))
    elements.append(Spacer(1, 12))
    return elements


class TocDocTemplate(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        SimpleDocTemplate.__init__(self, *args, **kwargs)

    def afterFlowable(self, flowable):
        if hasattr(flowable, 'bookmark_name'):
            level = getattr(flowable, 'bookmark_level', 0)
            text = getattr(flowable, 'bookmark_text', '')
            self.notify('TOCEntry', (level, text, self.page))


def add_heading(text, style, level=0):
    p = Paragraph(text, style)
    p.bookmark_name = text
    p.bookmark_level = level
    p.bookmark_text = text
    return p


def build_report():
    doc = TocDocTemplate(
        PDF_PATH, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.5*cm, bottomMargin=2*cm,
        title="PARWA_Infrastructure_Gap_Analysis",
        author="Z.ai", creator="Z.ai",
        subject="PARWA Infrastructure Gap Analysis - Foundation Review")

    story = []

    # -- COVER PAGE --
    story.append(Spacer(1, 100))
    story.append(Paragraph('<b>PARWA</b>', cover_title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        '<b>Infrastructure Gap Analysis Report</b>', cover_subtitle_style))
    story.append(Spacer(1, 36))
    story.append(Paragraph(
        'Foundation Review: Weeks 1-3 Infrastructure Phase',
        cover_info_style))
    story.append(Paragraph(
        'Identifying missing and partially completed infrastructure',
        cover_info_style))
    story.append(Paragraph(
        'that future roadmap weeks depend on', cover_info_style))
    story.append(Spacer(1, 60))
    story.append(Paragraph(
        'Build Status: 1131 Tests | 0 Flake8 Errors', cover_info_style))
    story.append(Paragraph(
        'Days Completed: 1-14 (Week 1-2 + Day 14 Celery)', cover_info_style))
    story.append(Spacer(1, 40))
    story.append(Paragraph('Generated: April 2, 2026', cover_info_style))
    story.append(Paragraph('Z.ai', cover_info_style))
    story.append(PageBreak())

    # -- TABLE OF CONTENTS --
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(name='TOC1', fontSize=12, leftIndent=20,
                       fontName='Times New Roman', spaceBefore=6),
        ParagraphStyle(name='TOC2', fontSize=10, leftIndent=40,
                       fontName='Times New Roman', spaceBefore=3),
    ]
    story.append(Paragraph('<b>Table of Contents</b>', h1_style))
    story.append(Spacer(1, 12))
    story.append(toc)
    story.append(PageBreak())

    # ============ 1. EXECUTIVE SUMMARY ============
    story.append(add_heading(
        '<b>1. Executive Summary</b>', h1_style, 0))
    story.append(Paragraph(
        'This report identifies all infrastructure gaps in the PARWA platform '
        'after completing Week 2 (Days 1-13) and the initial Celery setup '
        '(Day 14). The analysis specifically focuses on infrastructure pieces '
        'that are either partially completed or entirely missing, and that '
        'future roadmap weeks (Weeks 4 through 21) critically depend on. '
        'Features that will be covered in future weeks are excluded from this '
        'analysis unless their underlying infrastructure foundation is missing.',
        body_style))
    story.append(Paragraph(
        'The PARWA build has completed 14 development days across Week 1 and '
        'Week 2, producing 1131 passing tests with zero flake8 errors. All '
        '10 authentication features (F-010 through F-019) are built and '
        'loophole-audited. The initial Celery infrastructure (app config, 7 '
        'queues, task base class) was added in Day 14. However, several '
        'critical infrastructure components remain incomplete, which will '
        'block or complicate the implementation of future phases.',
        body_style))
    story.append(Paragraph(
        'The analysis identified <b>5 partially completed infrastructure '
        'items</b> that need completion before they can reliably support '
        'downstream features, and <b>8 entirely missing infrastructure items</b> '
        'that must be built to unblock future roadmap weeks. These gaps span '
        'the Celery task system, webhook processing, health monitoring, file '
        'storage, and audit logging subsystems.',
        body_style))

    summary_data = [
        [Paragraph('<b>Category</b>', th_style),
         Paragraph('<b>Total</b>', th_style),
         Paragraph('<b>Critical</b>', th_style),
         Paragraph('<b>High</b>', th_style),
         Paragraph('<b>Medium</b>', th_style)],
        [Paragraph('Partially Complete', td_style),
         Paragraph('5', td_center),
         Paragraph('2', td_center),
         Paragraph('2', td_center),
         Paragraph('1', td_center)],
        [Paragraph('Entirely Missing', td_style),
         Paragraph('8', td_center),
         Paragraph('3', td_center),
         Paragraph('3', td_center),
         Paragraph('2', td_center)],
        [Paragraph('<b>Total Gaps</b>', td_style),
         Paragraph('<b>13</b>', td_center),
         Paragraph('<b>5</b>', td_center),
         Paragraph('<b>5</b>', td_center),
         Paragraph('<b>3</b>', td_center)],
    ]
    story.extend(make_table(
        summary_data, [3.5*cm, 2*cm, 2*cm, 2*cm, 2*cm],
        'Table 1: Gap Summary by Category and Severity'))

    # ============ 2. COMPLETED INFRASTRUCTURE ============
    story.append(add_heading(
        '<b>2. Completed Infrastructure Overview</b>', h1_style, 0))
    story.append(Paragraph(
        'Before diving into gaps, it is important to document what infrastructure '
        'has been successfully built across the 14 development days. This provides '
        'context for understanding exactly what is missing.',
        body_style))

    story.append(add_heading(
        '<b>2.1 Week 1 (Days 1-6) - Foundation Layer</b>', h2_style, 1))
    w1_data = [
        [Paragraph('<b>Component</b>', th_style),
         Paragraph('<b>Status</b>', th_style),
         Paragraph('<b>Details</b>', th_style)],
        [Paragraph('Config + Logger', td_style),
         Paragraph('Done', td_center),
         Paragraph('pydantic-settings, structlog JSON logging, 45 config '
                   'fields', td_just)],
        [Paragraph('Database Models', td_style),
         Paragraph('Done', td_center),
         Paragraph('57+ tables across 9 model files, BC-001 company_id on '
                   'all tenant tables, BC-002 DECIMAL for money', td_just)],
        [Paragraph('Alembic Migrations', td_style),
         Paragraph('Config Only', td_center),
         Paragraph('Framework configured, env.py override from DATABASE_URL, '
                   'but NO actual migration stubs generated yet', td_just)],
        [Paragraph('Tenant Middleware', td_style),
         Paragraph('Done', td_center),
         Paragraph('BC-001 multi-tenant isolation, PUBLIC_PREFIXES for '
                   'auth/admin paths', td_just)],
        [Paragraph('Error Handling', td_style),
         Paragraph('Done', td_center),
         Paragraph('BC-012 structured JSON errors, correlation ID, Starlette '
                   'HTTPException handler, no stack traces', td_just)],
        [Paragraph('Shared Utilities', td_style),
         Paragraph('Done', td_center),
         Paragraph('UTC datetime, validators, pagination (max 100), bcrypt '
                   'cost 12, AES-256-GCM encryption', td_just)],
        [Paragraph('Rate Limiting', td_style),
         Paragraph('Done', td_center),
         Paragraph('Sliding window, progressive lockout (5 levels), '
                   'circuit breaker (3-state), SHA-256 keys', td_just)],
        [Paragraph('API Key Framework', td_style),
         Paragraph('Done', td_center),
         Paragraph('pk_ prefix, SHA-256 hashing, 4 scopes, constant-time '
                   'lookup, scope enforcement', td_just)],
        [Paragraph('Redis Layer', td_style),
         Paragraph('Done', td_center),
         Paragraph('Connection pool (max 20), parwa:{company_id}:* '
                   'namespace, fail-open on all operations', td_just)],
        [Paragraph('Socket.io Server', td_style),
         Paragraph('Done', td_center),
         Paragraph('tenant_{company_id} rooms, event buffer (24h TTL), '
                   'JWT auth from query params, ping/interval', td_just)],
        [Paragraph('Health Endpoints', td_style),
         Paragraph('Partial', td_center),
         Paragraph('/health checks Redis+DB only. NO Celery health, NO '
                   'external API health (Twilio/Brevo/Paddle/LLM)', td_just)],
        [Paragraph('Security Headers', td_style),
         Paragraph('Done', td_center),
         Paragraph('HSTS (prod), X-Content-Type-Options, X-Frame-Options, '
                   'CORS middleware', td_just)],
    ]
    story.extend(make_table(
        w1_data, [3*cm, 1.5*cm, 12*cm],
        'Table 2: Week 1 Infrastructure Status'))

    story.append(add_heading(
        '<b>2.2 Week 2 (Days 7-13) - Authentication System</b>', h2_style, 1))
    story.append(Paragraph(
        'All 10 authentication features (F-010 through F-019) from the Week 2 '
        'roadmap have been built, loophole-audited, and fixed. Additionally, '
        'Phone OTP (C5), Socket.io JWT auth (S02), Redis TIME sync (G01), '
        'scope wiring (G02/G03), and Admin Panel API + Company Settings were '
        'completed. The admin panel added 18 new routes (8 client + 10 admin) '
        'with JWT auth, role hierarchy enforcement, and company settings CRUD.',
        body_style))

    story.append(add_heading(
        '<b>2.3 Day 14 - Celery Initial Setup (Partial)</b>', h2_style, 1))
    story.append(Paragraph(
        'Day 14 introduced the Celery infrastructure skeleton: the Celery '
        'application configuration with Redis broker and result backend, 7 '
        'specialized queue definitions (default, ai_heavy, ai_light, email, '
        'webhook, analytics, training), task routing rules for automatic '
        'queue assignment, a ParwaTask base class with structured lifecycle '
        'logging (BC-012), a ParwaBaseTask concrete class with automatic '
        'retry and exponential backoff (2s to 5min, max 3 retries with '
        'jitter), and a with_company_id decorator enforcing BC-001. However, '
        'no actual task modules, DLQ configuration, Beat scheduler, or '
        'worker entry point exist yet.',
        body_style))

    # ============ 3. PARTIALLY COMPLETED ============
    story.append(add_heading(
        '<b>3. Partially Completed Infrastructure</b>', h1_style, 0))
    story.append(Paragraph(
        'These infrastructure items have been started but are incomplete. '
        'They must be finished before they can reliably support the downstream '
        'features that depend on them.',
        body_style))

    # 3.1 Celery
    story.append(add_heading(
        '<b>3.1 Celery Infrastructure (CRITICAL)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> CEL-001 | <b>Severity:</b> CRITICAL | <b>Blocks:</b> '
        'Weeks 5, 7, 8, 9, 10, 13, 16, 17, 19',
        body_style))
    story.append(Paragraph(
        'The Celery app configuration and task base class are in place, but '
        'several critical pieces are missing that prevent actual task '
        'execution in production. The 7 queues are defined but no actual '
        'task modules exist in any of the specialized queue directories. '
        'There is no Celery Beat scheduler configuration, meaning periodic '
        'tasks like daily overage charging (F-024, Week 5) cannot run. The '
        'worker entry point script is missing, so Celery workers cannot be '
        'started in production Docker containers. There is no dead letter '
        'queue (DLQ) configuration for permanently failed tasks, which the '
        'roadmap explicitly requires under BC-004. Finally, Celery health '
        'is not wired into the /health endpoint, so monitoring systems '
        'cannot detect worker failures or queue backups.',
        body_style))

    cel_data = [
        [Paragraph('<b>Missing Piece</b>', th_style),
         Paragraph('<b>Impact</b>', th_style),
         Paragraph('<b>Blocks</b>', th_style)],
        [Paragraph('DLQ configuration', td_style),
         Paragraph('Failed tasks after max retries are lost forever. No '
                   'recovery path for failed overage charges, webhooks, '
                   'or AI tasks.', td_just),
         Paragraph('F-024, F-022, F-055, all AI', td_style)],
        [Paragraph('Beat scheduler', td_style),
         Paragraph('Periodic tasks (daily overage billing at 02:00 UTC, '
                   'approval reminders at 2h/4h/8h/24h, approval timeout '
                   'at 72h) cannot run.', td_just),
         Paragraph('F-024, F-081, F-082', td_style)],
        [Paragraph('Worker entry point', td_style),
         Paragraph('Docker celery-worker service has no script to execute. '
                   'Cannot start workers in production.', td_just),
         Paragraph('All Celery features', td_style)],
        [Paragraph('Health in /health', td_style),
         Paragraph('Cannot detect worker crashes, queue backup, or broker '
                   'disconnection via monitoring.', td_just),
         Paragraph('BC-012, monitoring', td_style)],
        [Paragraph('No task modules', td_style),
         Paragraph('7 queues defined but empty. email/, webhook/, analytics/, '
                   'ai/ directories do not exist.', td_just),
         Paragraph('Weeks 5-19', td_style)],
    ]
    story.extend(make_table(
        cel_data, [3.5*cm, 9*cm, 4*cm],
        'Table 3: Celery Missing Pieces'))

    # 3.2 Health
    story.append(add_heading(
        '<b>3.2 Health Check System (HIGH)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> HLT-001 | <b>Severity:</b> HIGH | <b>Blocks:</b> '
        'Monitoring, Pre-launch checklist',
        body_style))
    story.append(Paragraph(
        'The /health endpoint currently checks only Redis and PostgreSQL '
        'connectivity. The Week 3 roadmap explicitly requires "Per-subsystem '
        'health (DB, Redis, Celery, external APIs), global health endpoint" '
        '(BC-012). Missing checks include: Celery worker availability (are '
        'workers running and consuming from queues?), external API '
        'connectivity (can the system reach Twilio, Brevo, Paddle, and '
        'LLM providers?), and queue depth monitoring (are any queues '
        'backing up?). Without these, production monitoring cannot detect '
        'external service outages or Celery worker failures, directly '
        'impacting reliability and the pre-launch checklist requirement '
        'for comprehensive health checks.',
        body_style))

    # 3.3 Audit
    story.append(add_heading(
        '<b>3.3 Audit Trail Persistence (MEDIUM)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> AUD-001 | <b>Severity:</b> MEDIUM | <b>Blocks:</b> '
        'Week 4, Week 5, Week 7',
        body_style))
    story.append(Paragraph(
        'The AuditEntry class exists with ActorType, AuditAction enums, '
        'and company_id validation (BC-001). However, audit entries are '
        'constructed but never written to the audit_logs database table. '
        'There is no auto-logging middleware for write operations (POST, PUT, '
        'DELETE), identified as gap FP11. Week 4 ticket operations, Week 5 '
        'billing events, and Week 7 approval actions all depend on reliable '
        'audit logging for compliance, debugging, and the undo system (F-084) '
        'which needs audit trails to reverse executed actions.',
        body_style))

    # 3.4 Socket.io
    story.append(add_heading(
        '<b>3.4 Socket.io Room Management (MEDIUM)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> SIO-001 | <b>Severity:</b> MEDIUM | <b>Blocks:</b> '
        'Week 4, Week 7, Week 14',
        body_style))
    story.append(Paragraph(
        'The Socket.io server supports tenant rooms (tenant_{company_id}) '
        'and JWT authentication. However, the Connection Map document '
        'specifies additional room patterns: agent-specific rooms '
        '(agent_{agent_id}) for ticket assignment notifications (F-050), '
        'private messaging between agents and supervisors, and GSD state '
        'terminal events (F-089). There is no mechanism for broadcasting '
        'to multiple rooms simultaneously, needed when a ticket event '
        'should notify both the tenant room and the assigned agent room.',
        body_style))

    # 3.5 Rate Limiting
    story.append(add_heading(
        '<b>3.5 Distributed Rate Limiting (LOW)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> RTL-001 | <b>Severity:</b> LOW | <b>Blocks:</b> '
        'Week 13, Week 16',
        body_style))
    story.append(Paragraph(
        'The rate limiting system uses an in-memory fallback with optional '
        'Redis. The infrastructure doc specifies per-tier limits (Free: 2 '
        'req/s through Enterprise: 50 req/s) requiring distributed '
        'Redis-backed limiting across multiple worker instances. The '
        'Connection Map also specifies channel-specific rate limits (email: '
        '100/min, chat: 30/min/user, SMS: 50/min, voice: 20/min, social: '
        '50/min) that need dedicated rate limit configurations for webhook '
        'endpoints.',
        body_style))

    # ============ 4. ENTIRELY MISSING ============
    story.append(add_heading(
        '<b>4. Entirely Missing Infrastructure</b>', h1_style, 0))
    story.append(Paragraph(
        'These infrastructure items do not exist in the codebase at all. '
        'They are foundational pieces that multiple future roadmap weeks '
        'depend on.',
        body_style))

    # 4.1 Webhook Framework
    story.append(add_heading(
        '<b>4.1 Webhook Base Framework (CRITICAL)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> WBK-001 | <b>Severity:</b> CRITICAL | <b>Blocks:</b> '
        'Week 5 (Paddle billing), Week 6 (Brevo inbound), Week 13 (Twilio, '
        'Shopify), Week 17 (custom webhooks)',
        body_style))
    story.append(Paragraph(
        'The webhook base framework is the single most critical missing '
        'infrastructure piece. BC-003 mandates: HMAC signature verification '
        'for all incoming webhooks, idempotency guarantees via event_id '
        'deduplication, async processing with response time under 3 seconds, '
        'and Celery dispatch for heavy processing. None of this exists. '
        'The Paddle webhook handler (F-022) is listed as CRITICAL in the '
        'Connection Map because the entire billing chain flows through it. '
        'Without this framework, no external service integration can receive '
        'events securely, blocking Paddle payments, Brevo inbound email, '
        'Twilio SMS/voice callbacks, and Shopify order sync.',
        body_style))
    story.append(Paragraph(
        'The framework needs: a generic webhook receiver endpoint that '
        'validates HMAC signatures per provider, a webhook_events table for '
        'idempotency (event_id + provider uniqueness), automatic Celery '
        'dispatch with provider-specific queue routing, a retry mechanism '
        'with DLQ, and delivery status tracking for monitoring.',
        body_style))

    # 4.2 HMAC
    story.append(add_heading(
        '<b>4.2 HMAC Signature Verification (CRITICAL)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> HMAC-001 | <b>Severity:</b> CRITICAL | <b>Blocks:</b> '
        'Week 5, Week 13, Week 17',
        body_style))
    story.append(Paragraph(
        'Each external service uses different signature verification. Paddle '
        'uses HMAC-SHA256 with PADDLE_WEBHOOK_SECRET. Twilio validates '
        'signatures based on its auth token and request URL. Brevo uses IP '
        'allowlist verification. Shopify uses HMAC-SHA256 with the shop '
        'secret. The Connection Map shows HMAC verification as step 1 in '
        'webhook processing for every channel. Without these utilities, '
        'webhook endpoints would be unprotected and vulnerable to spoofed '
        'events, which is a critical security vulnerability for a payment '
        'processing system.',
        body_style))

    # 4.3 File Storage
    story.append(add_heading(
        '<b>4.3 File Storage Service (HIGH)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> STR-001 | <b>Severity:</b> HIGH | <b>Blocks:</b> '
        'Week 6 (KB upload, KB processing), Week 19 (model weights), '
        'Week 20 (data export)',
        body_style))
    story.append(Paragraph(
        'The infrastructure doc specifies GCP Cloud Storage for documents, '
        'model weights, and exports. Config has GCP_STORAGE_BUCKET but no '
        'service exists. Week 6 onboarding needs file upload for KB documents '
        '(PDF, DOCX, TXT, Markdown, HTML, CSV) and the KB processing pipeline '
        'needs to read and write processed chunks. Week 19 needs model weight '
        'upload/download. Week 20 needs data export file generation. The '
        'service needs: tenant-isolated paths (parwa/{company_id}/...), '
        'upload with type/size validation, download with signed URLs, and '
        'delete operations.',
        body_style))

    # 4.4 IP Allowlist
    story.append(add_heading(
        '<b>4.4 IP Allowlist Middleware (HIGH)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> IPR-001 | <b>Severity:</b> HIGH | <b>Blocks:</b> '
        'Week 5 (Paddle webhooks), Week 13 (Brevo inbound, Twilio)',
        body_style))
    story.append(Paragraph(
        'The Connection Map specifies Brevo inbound email uses IP allowlist '
        'authentication (BC-006). The infrastructure doc (Section 8.2) lists '
        'ip_allowlist.py as a security component. No IP allowlist middleware '
        'exists. This is needed for Brevo inbound parse webhook, webhook '
        'endpoints receiving events from known IP ranges, and admin-only '
        'routes that should restrict access by source IP address.',
        body_style))

    # 4.5 PaginatedResponse
    story.append(add_heading(
        '<b>4.5 Standardized PaginatedResponse (HIGH)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> PGN-001 | <b>Severity:</b> HIGH | <b>Blocks:</b> '
        'Week 4 (ticket list), Week 5 (invoices), Week 7 (approvals), '
        'Week 16 (dashboard)',
        body_style))
    story.append(Paragraph(
        'The admin schemas have a local PaginatedResponse, but no standardized '
        'reusable PaginatedResponse[T] generic schema exists for all list '
        'endpoints. Week 4 introduces the ticket list with complex filtering '
        'and sorting. Every subsequent list endpoint (invoices, approvals, '
        'agents, customers, analytics) needs the same pagination pattern. '
        'Without standardization, each endpoint implements its own pagination, '
        'leading to inconsistent response formats and duplicated logic.',
        body_style))

    # 4.6 External Client Factory
    story.append(add_heading(
        '<b>4.6 External Service Client Factory (MEDIUM)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> SVC-001 | <b>Severity:</b> MEDIUM | <b>Blocks:</b> '
        'Week 5 (Paddle), Week 8 (LLM), Week 13 (Twilio, Brevo, Shopify)',
        body_style))
    story.append(Paragraph(
        'Config has API keys for Twilio, Paddle, Brevo, and LLM providers, '
        'but no service client factory exists. Each integration would need '
        'to create clients from scratch. The infrastructure doc shows '
        'specific client classes (paddle_client.py, etc.) with methods like '
        'create_subscription(), process_refund() with approval gate. The '
        'circuit breaker class exists but is not wired to any external '
        'calls. A factory pattern would centralize API key management, '
        'retry logic, circuit breaker wrapping, and error handling.',
        body_style))

    # 4.7 Migration Stubs
    story.append(add_heading(
        '<b>4.7 Database Migration Stubs (MEDIUM)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> MIG-001 | <b>Severity:</b> MEDIUM | <b>Blocks:</b> '
        'Deployment',
        body_style))
    story.append(Paragraph(
        'Alembic is configured with env.py override from DATABASE_URL, but '
        'no actual migration stubs have been generated from the 57+ table '
        'models. The infrastructure doc lists 11 migration groups and the '
        'pre-launch checklist requires "Alembic migrations applied (all '
        'versions)." Without migration files, the database schema cannot be '
        'versioned, and production deployments cannot apply schema changes '
        'safely. Stubs need to be generated via alembic revision '
        '--autogenerate and verified against model definitions.',
        body_style))

    # 4.8 Missing Tables
    story.append(add_heading(
        '<b>4.8 Missing Database Tables (MEDIUM)</b>', h2_style, 1))
    story.append(Paragraph(
        '<b>Gap ID:</b> DBT-001 | <b>Severity:</b> MEDIUM | <b>Blocks:</b> '
        'Week 7, Week 8, Week 9, Week 19',
        body_style))
    story.append(Paragraph(
        'The Day 6 analysis identified 13 missing tables; 4 critical ones '
        'were added. 9 remain missing: response_templates (Week 9 auto-'
        'response), email_logs (Week 5/13 tracking), rate_limit_counters '
        '(distributed limiting), feature_flags (feature access), '
        'classification_log (Week 8 AI classification), guardrails_audit_log '
        'and guardrails_blocked_queue (Week 8 guardrails), '
        'ai_response_feedback (Week 9 confidence), confidence_thresholds '
        '(Week 8 scoring), and human_corrections (Week 19 training). '
        'While these will be created when features are built, their absence '
        'means Connection Map data flows reference non-existent tables.',
        body_style))

    # ============ 5. PRIORITY MATRIX ============
    story.append(add_heading(
        '<b>5. Priority Matrix: Build Order</b>', h1_style, 0))
    story.append(Paragraph(
        'Based on dependency analysis, the following priority matrix shows '
        'the recommended build order. The ordering considers both the '
        'severity of the gap and how soon dependent features are needed.',
        body_style))

    pri_data = [
        [Paragraph('<b>Priority</b>', th_style),
         Paragraph('<b>Gap ID</b>', th_style),
         Paragraph('<b>Item</b>', th_style),
         Paragraph('<b>Effort</b>', th_style),
         Paragraph('<b>Blocks</b>', th_style)],
        [Paragraph('P0', td_center),
         Paragraph('WBK-001', td_center),
         Paragraph('Webhook Base Framework', td_style),
         Paragraph('1 day', td_center),
         Paragraph('Wk 5,6,13,17', td_center)],
        [Paragraph('P0', td_center),
         Paragraph('HMAC-001', td_center),
         Paragraph('HMAC Verification Utility', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 5,13,17', td_center)],
        [Paragraph('P0', td_center),
         Paragraph('CEL-001', td_center),
         Paragraph('Celery DLQ + Beat + Health', td_style),
         Paragraph('1 day', td_center),
         Paragraph('Wk 5,7,8,9', td_center)],
        [Paragraph('P1', td_center),
         Paragraph('STR-001', td_center),
         Paragraph('File Storage Service', td_style),
         Paragraph('1 day', td_center),
         Paragraph('Wk 6,19,20', td_center)],
        [Paragraph('P1', td_center),
         Paragraph('IPR-001', td_center),
         Paragraph('IP Allowlist Middleware', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 5,13', td_center)],
        [Paragraph('P1', td_center),
         Paragraph('PGN-001', td_center),
         Paragraph('Standardized PaginatedResponse', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 4,5,7,16', td_center)],
        [Paragraph('P2', td_center),
         Paragraph('SVC-001', td_center),
         Paragraph('External Service Client Factory', td_style),
         Paragraph('1 day', td_center),
         Paragraph('Wk 5,8,13', td_center)],
        [Paragraph('P2', td_center),
         Paragraph('AUD-001', td_center),
         Paragraph('Audit Trail DB Persistence', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 4,5,7', td_center)],
        [Paragraph('P2', td_center),
         Paragraph('HLT-001', td_center),
         Paragraph('Celery + External API Health', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Monitoring', td_center)],
        [Paragraph('P2', td_center),
         Paragraph('MIG-001', td_center),
         Paragraph('Alembic Migration Stubs', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Deploy', td_center)],
        [Paragraph('P3', td_center),
         Paragraph('DBT-001', td_center),
         Paragraph('Missing Database Tables', td_style),
         Paragraph('1 day', td_center),
         Paragraph('Wk 7,8,9,19', td_center)],
        [Paragraph('P3', td_center),
         Paragraph('SIO-001', td_center),
         Paragraph('Socket.io Room Management', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 4,7,14', td_center)],
        [Paragraph('P3', td_center),
         Paragraph('RTL-001', td_center),
         Paragraph('Distributed Rate Limiting', td_style),
         Paragraph('0.5 day', td_center),
         Paragraph('Wk 13,16', td_center)],
    ]
    story.extend(make_table(
        pri_data, [1.5*cm, 2*cm, 5*cm, 1.5*cm, 2.5*cm],
        'Table 4: Infrastructure Gap Priority Matrix'))

    story.append(Paragraph(
        'All P0 items should be completed before starting Week 3 feature '
        'work. They can be done in approximately 2.5 days and unblock the '
        'majority of downstream features. P1 items should be completed '
        'during Week 3. P2 and P3 items can be deferred to their respective '
        'feature weeks without significant rework, though completing them '
        'earlier reduces technical debt.',
        body_style))

    # ============ 6. RECOMMENDED PLAN ============
    story.append(add_heading(
        '<b>6. Recommended Completion Plan</b>', h1_style, 0))
    story.append(Paragraph(
        'The following plan integrates infrastructure gap completion into '
        'the existing Week 3 roadmap. Week 3 covers: Celery infrastructure, '
        'Socket.io server, Multi-tenant middleware, Webhook base framework, '
        'and Health check system. Several roadmap items directly correspond '
        'to the gaps identified in this report.',
        body_style))

    plan_data = [
        [Paragraph('<b>Day</b>', th_style),
         Paragraph('<b>Task</b>', th_style),
         Paragraph('<b>Gaps Addressed</b>', th_style),
         Paragraph('<b>Roadmap Mapping</b>', th_style)],
        [Paragraph('Day 15', td_center),
         Paragraph('Webhook base framework + HMAC utility + IP allowlist '
                   'middleware', td_style),
         Paragraph('WBK-001, HMAC-001, IPR-001', td_center),
         Paragraph('BC-003 Webhook Framework', td_style)],
        [Paragraph('Day 16', td_center),
         Paragraph('Celery DLQ + Beat scheduler + health endpoint wire-up '
                   '+ worker entry point script', td_style),
         Paragraph('CEL-001, HLT-001', td_center),
         Paragraph('BC-004 Celery Infra', td_style)],
        [Paragraph('Day 17', td_center),
         Paragraph('File storage service (GCP) + PaginatedResponse[T] + '
                   'audit trail DB persistence + middleware', td_style),
         Paragraph('STR-001, PGN-001, AUD-001', td_center),
         Paragraph('BC-012 Health + Monitoring', td_style)],
        [Paragraph('Day 18', td_center),
         Paragraph('External service client factory + Alembic migration '
                   'stubs + remaining DB tables + Socket.io rooms', td_style),
         Paragraph('SVC-001, MIG-001, DBT-001, SIO-001, RTL-001',
                   td_center),
         Paragraph('Infra Hardening', td_style)],
    ]
    story.extend(make_table(
        plan_data, [1.5*cm, 6*cm, 4*cm, 4.5*cm],
        'Table 5: 4-Day Infrastructure Completion Plan'))

    story.append(Paragraph(
        'This 4-day plan completes all P0 and P1 gaps plus the most impactful '
        'P2 gaps. After Day 18, the platform infrastructure would be fully '
        'ready to support all downstream feature work from Week 4 through '
        'Week 21 without infrastructure blockers. The plan adds 4 days to '
        'the original roadmap but ensures a solid foundation that prevents '
        'costly rework during feature implementation.',
        body_style))

    # ============ 7. OUT OF SCOPE ============
    story.append(add_heading(
        '<b>7. Explicitly Out of Scope</b>', h1_style, 0))
    story.append(Paragraph(
        'This analysis focuses exclusively on infrastructure that is missing '
        'or partially completed. The following items are out of scope because '
        'they are feature work planned for future weeks, and their '
        'infrastructure dependencies are either already met or will be built '
        'as part of the feature itself.',
        body_style))

    oos_data = [
        [Paragraph('<b>Item</b>', th_style),
         Paragraph('<b>Why Out of Scope</b>', th_style)],
        [Paragraph('Smart Router / LLM integration', td_style),
         Paragraph('Week 8 feature. LLM provider configs already exist in '
                   'config.py. No infra dependency missing.', td_just)],
        [Paragraph('RAG / pgvector / embeddings', td_style),
         Paragraph('Week 9 feature. pgvector is a PostgreSQL extension '
                   'enabled at deployment time, not in app code.', td_just)],
        [Paragraph('LangGraph / GSD State Engine', td_style),
         Paragraph('Week 10 feature. Uses Redis (built) and PostgreSQL '
                   'tables (created with feature).', td_just)],
        [Paragraph('Frontend (Next.js)', td_style),
         Paragraph('No frontend directory exists. Phase 4+ concern per '
                   'roadmap. Backend APIs define what frontend needs.',
                   td_just)],
        [Paragraph('Paddle subscription logic', td_style),
         Paragraph('Week 5 feature. Paddle env vars exist. Webhook '
                   'framework (this report) is the only blocker.',
                   td_just)],
        [Paragraph('MCP Servers', td_style),
         Paragraph('Week 17 feature. MCP config vars exist in config.py. '
                   'No infra dependency missing.', td_just)],
        [Paragraph('Kubernetes / CI/CD', td_style),
         Paragraph('Production deployment. Docker config exists in '
                   'infra/docker/. K8s per infrastructure doc.', td_just)],
        [Paragraph('Training pipeline', td_style),
         Paragraph('Week 19 feature. Depends on human_corrections table '
                   '(DBT-001) and file storage (STR-001) from this report.',
                   td_just)],
    ]
    story.extend(make_table(
        oos_data, [4.5*cm, 12*cm],
        'Table 6: Items Explicitly Out of Scope'))

    # -- BUILD PDF --
    doc.multiBuild(story)
    print(f"PDF generated: {PDF_PATH}")
    return PDF_PATH


if __name__ == "__main__":
    build_report()
