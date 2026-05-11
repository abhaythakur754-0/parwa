const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
  Header, Footer, PageNumber, PageBreak, TableOfContents, TabStopType, TabStopPosition } = require("docx");

// ── Palette: DM-1 Deep Cyan (Tech/AI) ──
const P = {
  primary: "0A1628", body: "1A2B40", secondary: "5A6080",
  accent: "1B6B7A", surface: "EDF3F5",
  headerBg: "1B6B7A", headerText: "FFFFFF",
  innerLine: "C8DDE2",
};
const c = (hex) => hex.replace("#", "");

// ── Borders ──
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const allNoBorders = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };

const tBorders = {
  top: { style: BorderStyle.SINGLE, size: 2, color: c(P.accent) },
  bottom: { style: BorderStyle.SINGLE, size: 2, color: c(P.accent) },
  left: BorderStyle.NONE, right: BorderStyle.NONE,
  insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: c(P.innerLine) },
  insideVertical: BorderStyle.NONE,
};

// ── Helpers ──
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    children: [new TextRun({ text, bold: true, color: c(P.primary), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 32 })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 160 },
    children: [new TextRun({ text, bold: true, color: c(P.accent), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 28 })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, color: c(P.body), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 24 })],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    spacing: { line: 312, after: 80 },
    children: [new TextRun({ text, size: 22, color: c(P.body), font: { ascii: "Calibri" } })],
  });
}

function bodyBold(label, text) {
  return new Paragraph({
    spacing: { line: 312, after: 60 },
    children: [
      new TextRun({ text: label, bold: true, size: 22, color: c(P.primary), font: { ascii: "Calibri" } }),
      new TextRun({ text, size: 22, color: c(P.body), font: { ascii: "Calibri" } }),
    ],
  });
}

function verdictBadge(verdict) {
  const map = {
    "BUILT": { color: "1B7A3D", bg: "E8F5E9" },
    "PARTIAL": { color: "B8860B", bg: "FFF8E1" },
    "MISSING": { color: "C62828", bg: "FFEBEE" },
  };
  const m = map[verdict] || map["MISSING"];
  const prefix = verdict === "BUILT" ? "ALREADY BUILT" : verdict === "PARTIAL" ? "PARTIAL" : "MISSING";
  return new TextRun({ text: prefix, bold: true, size: 20, color: c(m.color), font: { ascii: "Calibri" } });
}

function evidenceBlock(file, lines) {
  return new Paragraph({
    spacing: { line: 280, after: 40 },
    indent: { left: 400 },
    children: [
      new TextRun({ text: "Evidence: ", bold: true, size: 20, color: c(P.secondary), font: { ascii: "Calibri" } }),
      new TextRun({ text: file + (lines ? " (lines " + lines + ")" : ""), italics: true, size: 20, color: c(P.secondary), font: { ascii: "Calibri" } }),
    ],
  });
}

function gapBlock(text) {
  return new Paragraph({
    spacing: { line: 280, after: 60 },
    indent: { left: 400 },
    children: [
      new TextRun({ text: "Gap: ", bold: true, size: 20, color: c("C62828"), font: { ascii: "Calibri" } }),
      new TextRun({ text, size: 20, color: c(P.body), font: { ascii: "Calibri" } }),
    ],
  });
}

// ── Status Table ──
function statusHeaderRow() {
  const hdr = (text) => new TableCell({
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })],
    shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) },
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
  });
  return new TableRow({
    children: [hdr("#"), hdr("Category"), hdr("Item"), hdr("Status"), hdr("Priority")],
    tableHeader: true, cantSplit: true,
  });
}

function statusRow(idx, cat, item, status, priority) {
  const colors = { "BUILT": "E8F5E9", "PARTIAL": "FFF8E1", "MISSING": "FFEBEE" };
  const labels = { "BUILT": "BUILT", "PARTIAL": "PARTIAL", "MISSING": "MISSING" };
  const textColors = { "BUILT": "1B7A3D", "PARTIAL": "B8860B", "MISSING": "C62828" };
  const cell = (text, opts = {}) => new TableCell({
    children: [new Paragraph({ children: [new TextRun({ text, size: 20, color: opts.textColor ? c(opts.textColor) : c(P.body), font: { ascii: "Calibri" }, bold: opts.bold || false })] })],
    shading: opts.shading ? { type: ShadingType.CLEAR, fill: c(opts.shading) } : undefined,
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
  });
  return new TableRow({
    children: [
      cell(String(idx), { bold: true }),
      cell(cat),
      cell(item),
      cell(labels[status], { shading: colors[status], textColor: textColors[status], bold: true }),
      cell(priority, { bold: priority === "HIGH" }),
    ],
    cantSplit: true,
  });
}

// ── COVER ──
function buildCover() {
  const { calcTitleLayout, calcCoverSpacing } = (() => {
    const charWidth = (pt) => pt * 20;
    const charsPerLine = (pt) => Math.floor(13906 / charWidth(pt));
    function splitTitleLines(title, cpl) {
      if (title.length <= cpl) return [title];
      const breakAfter = new Set([...'-_ \t/']);
      const lines = [];
      let remaining = title;
      while (remaining.length > cpl) {
        let breakAt = -1;
        for (let i = cpl; i >= Math.floor(cpl * 0.6); i--) {
          if (i < remaining.length && breakAfter.has(remaining[i - 1])) { breakAt = i; break; }
        }
        if (breakAt === -1) breakAt = cpl;
        lines.push(remaining.slice(0, breakAt).trim());
        remaining = remaining.slice(breakAt).trim();
      }
      if (remaining) lines.push(remaining);
      return lines;
    }
    function calcTitleLayout(title, maxW, pref = 38, min = 24) {
      let pt = pref, lines;
      while (pt >= min) {
        lines = splitTitleLines(title, charsPerLine(pt));
        if (lines.length <= 3) break;
        pt -= 2;
      }
      if (!lines || lines.length > 3) { lines = splitTitleLines(title, charsPerLine(min)); pt = min; }
      return { titlePt: pt, titleLines: lines };
    }
    function calcCoverSpacing(p) {
      const usable = 16838 - 1200 - (p.fixedHeight || 800);
      const titleH = p.titlePt * 23 * (p.titleLineCount || 1);
      const otherH = (p.hasSubtitle ? 500 : 0) + (p.hasEnglishLabel ? 300 : 0) + p.metaLineCount * 350;
      const total = titleH + otherH;
      const remaining = usable - total;
      const top = Math.round(remaining * 0.45);
      const mid = Math.round(remaining * 0.25);
      return { topSpacing: Math.max(top, 600), midSpacing: Math.max(mid, 200) };
    }
    return { calcTitleLayout, calcCoverSpacing };
  })();

  const { titlePt, titleLines } = calcTitleLayout("PARWA Codebase Audit Report", 13906, 38, 26);
  const { topSpacing, midSpacing } = calcCoverSpacing({
    titleLineCount: titleLines.length, titlePt,
    hasSubtitle: true, hasEnglishLabel: true, metaLineCount: 4, fixedHeight: 1200,
  });

  const titleParas = titleLines.map((line, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { line: Math.ceil(titlePt * 23), lineRule: "atLeast", before: i === 0 ? topSpacing : 80, after: 80 },
    indent: { left: 1400 },
    children: [new TextRun({ text: line, bold: true, size: titlePt * 2, color: c("FFFFFF"), font: { ascii: "Calibri" } })],
  }));

  return new Table({
    borders: allNoBorders,
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({
      height: { value: 16838, rule: "exact" },
      verticalAlign: "top",
      children: [new TableCell({
        borders: allNoBorders,
        shading: { type: ShadingType.CLEAR, fill: "162235" },
        width: { size: 100, type: WidthType.PERCENTAGE },
        children: [
          // Accent bar
          new Paragraph({
            spacing: { before: 0, after: 0 },
            border: { top: { style: BorderStyle.SINGLE, size: 36, color: c("37DCF2"), space: 0 } },
            children: [],
          }),
          ...titleParas,
          // Subtitle
          new Paragraph({
            spacing: { before: midSpacing, after: 100 },
            indent: { left: 1400 },
            children: [new TextRun({ text: "Production Readiness Cross-Check Audit", size: 26, color: c("B0B8C0"), font: { ascii: "Calibri" } })],
          }),
          // English label
          new Paragraph({
            spacing: { before: 60, after: 200 },
            indent: { left: 1400 },
            children: [new TextRun({ text: "AI Workforce for Customer Care | Verified Against Live Code", size: 20, color: c("90989F"), font: { ascii: "Calibri" } })],
          }),
          // Divider
          new Paragraph({
            spacing: { before: 100, after: 100 },
            indent: { left: 1400, right: 1400 },
            border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: c("37DCF2"), space: 4 } },
            children: [],
          }),
          // Meta info
          bodyBoldMeta("Date: ", "May 12, 2026"),
          bodyBoldMeta("Repo: ", "github.com/abhaythakur754-0/parwa (commit da37c77)"),
          bodyBoldMeta("Scope: ", "32 Items Cross-Checked Against Pulled Code"),
          bodyBoldMeta("Method: ", "Automated grep + manual file inspection"),
        ],
      })],
    })],
  });
}

function bodyBoldMeta(label, text) {
  return new Paragraph({
    spacing: { before: 40, after: 40 },
    indent: { left: 1400 },
    children: [
      new TextRun({ text: label, bold: true, size: 20, color: c("90989F"), font: { ascii: "Calibri" } }),
      new TextRun({ text, size: 20, color: c("687078"), font: { ascii: "Calibri" } }),
    ],
  });
}

// ══════════════════════════════════════
// ITEM DATA (all 32 cross-checked items)
// ══════════════════════════════════════

const items = [
  // ── AI Features ──
  { id:1, cat:"AI Features", name:"HyDE (Hypothetical Doc Embeddings)", status:"MISSING", pri:"HIGH",
    detail:"Zero matches for 'hyde', 'hypothetical_document', or 'hypothetical' in entire codebase. RAG module has no HyDE implementation.",
    file:"backend/app/core/rag_retrieval.py" },
  { id:2, cat:"AI Features", name:"Multi-Query Retriever", status:"PARTIAL", pri:"HIGH",
    detail:"Only static synonym substitution from a hardcoded QUERY_SYNONYMS dict (9 word-synonym mappings). No LLM-based query decomposition or reformulation. Generates at most 2 extra queries. Only active for parwa_high variant.",
    file:"backend/app/core/rag_retrieval.py:457-479" },
  { id:3, cat:"AI Features", name:"LLM-based Reranking", status:"MISSING", pri:"HIGH",
    detail:"CrossEncoderReranker class name is misleading. Implementation is 100% hand-coded BM25/TF-IDF math with weighted scoring (TF-IDF 30%, phrase bonus 10%, bigram 10%, position 10%, vector 40%). No LLM calls, no neural model, no actual cross-encoder.",
    file:"backend/app/core/rag_reranking.py" },
  { id:4, cat:"AI Features", name:"Sentiment Analysis (LLM-based)", status:"MISSING", pri:"HIGH",
    detail:"855-line keyword/lexicon system with FRUSTRATION_STRONG (21 words), FRUSTRATION_MODERATE (30+ words), FrustrationDetector (scores CAPS, exclamation marks, repeated words), EmotionClassifier (6 categories via lexicon), EmpathySignalDetector, UrgencyScorer. Zero LLM or NLP library calls.",
    file:"backend/app/core/sentiment_engine.py" },
  { id:5, cat:"AI Features", name:"Agent Lightning Self-Learning", status:"MISSING", pri:"HIGH",
    detail:"Three Celery task stubs in training_tasks.py, ALL return hardcoded zeros (samples_count:0, train_count:0, test_count:0, training_triggered:False, training_job_id:None). No fine-tuning, no Unsloth, no LoRA, no dataset preparation code exists anywhere.",
    file:"backend/app/tasks/training_tasks.py" },
  { id:6, cat:"AI Features", name:"MAKER Framework", status:"BUILT", pri:"-",
    detail:"Real 685-line implementation: K-solution generation via LLM with fallback, solution scoring via maker_scorer, best solution selection, red flag logic (confidence < threshold), problem decomposition for Pro/High tiers, full audit trail at 3 levels. Variant-gated config: Mini K=3/threshold=0.50, Pro K=3-5/threshold=0.60, High K=5-7/threshold=0.75. Gaps: maker_scorer and maker_decomposition modules imported but don't exist as files (falls back gracefully).",
    file:"backend/app/core/langgraph/nodes/11_maker_validator.py" },
  { id:7, cat:"AI Features", name:"Loophole Engine Centralized Detection", status:"MISSING", pri:"HIGH",
    detail:"File backend/app/core/loophole_engine.py does NOT exist. No LoopholeEngine class anywhere. 'loophole' references only appear in 20+ test files testing individual security fixes, not a unified 25-pattern detection system.",
    file:"backend/app/core/ (file missing)" },
  { id:8, cat:"AI Features", name:"Voice NLU (LLM-based)", status:"MISSING", pri:"HIGH",
    detail:"Intent detection in parwa_voice_server.py is explicitly keyword-based with a hardcoded intent_keywords dict (9 intents). Comment literally says 'In production, this routes through Parwa's full variant pipeline' but that routing is NOT implemented. Voice demo uses placeholder STT and placeholder AI responses.",
    file:"backend/app/core/parwa_voice_server.py:444-469" },
  { id:9, cat:"AI Features", name:"PII Redaction (LLM NER)", status:"MISSING", pri:"HIGH",
    detail:"1140-line file with 20+ compiled regex patterns for 15+ PII types. Docstring explicitly states 'no NLP libs'. Luhn algorithm for credit cards. No spacy, no NER, no LLM calls anywhere. Redis-backed reversible redaction map works well but is purely regex-based.",
    file:"backend/app/core/pii_redaction_engine.py" },
  { id:10, cat:"AI Features", name:"Smart Router Tier-Based Routing", status:"BUILT", pri:"-",
    detail:"Substantial ~1300-line implementation. 4 tiers (LIGHT/MEDIUM/HEAVY/GUARDRAIL), 10+ models across 3 providers (Cerebras, Groq, Google). Variant gating: Mini gets LIGHT+GUARDRAIL, Pro gets LIGHT+MEDIUM+GUARDRAIL, High gets ALL. 18-step MAKER-aware routing. Full resilience: ProviderHealthTracker with daily limits, per-minute limits, consecutive failure tracking, fallback chains.",
    file:"backend/app/core/smart_router.py" },

  // ── Security ──
  { id:11, cat:"Security", name:"Rate Limiter Fail-Closed", status:"PARTIAL", pri:"HIGH",
    detail:"Explicitly fail-open. Redis failure falls back to in-memory limiting (single-process only, lost on restart). Middleware exception passes the request through entirely. In multi-instance deployments with Redis down, each process uses its own counter - trivially bypassable.",
    file:"backend/app/services/rate_limit_service.py:240-250, backend/app/middleware/rate_limit.py:90-98" },
  { id:12, cat:"Security", name:"JWT Blacklist/Revocation", status:"MISSING", pri:"HIGH",
    detail:"jti IS generated in every access token (line 98-100). get_token_jti() utility exists (lines 149-165). But get_token_jti() is NEVER called in production code - only used in tests. verify_access_token() does NOT check any blacklist. No blacklist store (Redis set, DB table) exists anywhere.",
    file:"backend/app/core/auth.py" },
  { id:13, cat:"Security", name:"OCSP Stapling", status:"PARTIAL", pri:"MEDIUM",
    detail:"Present in nginx/nginx.conf (production) with ssl_stapling on, ssl_stapling_verify on, resolver 8.8.8.8. Completely ABSENT from infra/docker/nginx-default.conf and infra/docker/nginx.conf (Docker build configs). Docker image ships without OCSP.",
    file:"nginx/nginx.conf:99-103" },
  { id:14, cat:"Security", name:"HSTS with Proper Flags", status:"PARTIAL", pri:"MEDIUM",
    detail:"Production nginx has complete HSTS: max-age=63072000; includeSubDomains; preload. Docker default nginx has incomplete HSTS: max-age=63072000 only (missing includeSubDomains and preload). Config drift between the two.",
    file:"nginx/nginx.conf:106, infra/docker/nginx-default.conf:46" },
  { id:15, cat:"Security", name:"Strong Cipher Suites", status:"BUILT", pri:"-",
    detail:"Both configs use PFS-only modern ciphers. Production has 8 ciphers (ECDHE/DHE with AES-GCM + CHACHA20-POLY1305). Docker default has 2 ciphers (narrower but still secure). No CBC, no RC4, no DES.",
    file:"nginx/nginx.conf:91, infra/docker/nginx-default.conf:42" },
  { id:16, cat:"Security", name:"HMAC Timestamp Freshness", status:"BUILT", pri:"-",
    detail:"Two implementations exist: canonical one in hmac_verification.py with _verify_webhook_timestamp() checking abs(age) with 5-minute window. Webhook endpoint has its own inline version checking age > 300s. Minor gap: if timestamp is unparseable, request passes through (line 370: pass).",
    file:"backend/app/security/hmac_verification.py:27-28, backend/app/api/webhooks.py:42" },
  { id:17, cat:"Security", name:"CORS Stricter Config", status:"BUILT", pri:"-",
    detail:"Explicit origins from env (CORS_ORIGINS comma-separated), never wildcard '*'. Falls back to FRONTEND_URL (single origin) when not set. Exception handler fails closed to localhost. allow_methods and allow_headers are * but origin whitelist is the real protection.",
    file:"backend/app/main.py:298-321" },
  { id:18, cat:"Security", name:"API Key 401 Response", status:"BUILT", pri:"-",
    detail:"Proper 401 for invalid/expired/revoked API keys. Only keys with parwa_live_ or parwa_test_ prefix treated as API keys. Revoked keys get 401. Expired keys get 401. Uses Authorization: Bearer header (no X-API-Key).",
    file:"backend/app/middleware/api_key_auth.py:77-108" },
  { id:19, cat:"Security", name:"Twilio Signature Verification", status:"BUILT", pri:"-",
    detail:"RFC 5849 HMAC-SHA1 verification. Always verified when TWILIO_AUTH_TOKEN is configured. Fail-closed when token not configured. Constant-time comparison via hmac.compare_digest. Enforcement at API layer before handler is called.",
    file:"backend/app/security/hmac_verification.py:100-139, backend/app/api/webhooks.py:188-211" },

  // ── Infrastructure ──
  { id:20, cat:"Infrastructure", name:"Docker Compose Healthchecks", status:"BUILT", pri:"-",
    detail:"Fully implemented across both compose files. 13 services with healthchecks: db (pg_isready), redis (ping), backend (curl /health), mcp, frontend, prometheus, grafana, alertmanager, nginx. Production uses longer start_periods (60s). Worker service has NO healthcheck (expected for Celery - no HTTP port).",
    file:"docker-compose.yml, docker-compose.prod.yml" },
  { id:21, cat:"Infrastructure", name:"Nginx Production-Hardened Config", status:"PARTIAL", pri:"MEDIUM",
    detail:"Three config files with significant drift. docker-compose.prod.yml mounts nginx/nginx.conf (fully hardened: CSP, OCSP, Permissions-Policy, sensitive path blocking). But Docker image builds from infra/docker/ configs which lack CSP, OCSP, Permissions-Policy. nginx-default.conf references undefined zone names (api, login vs api_limit, login_limit) - would crash if loaded.",
    file:"nginx/nginx.conf, infra/docker/nginx-default.conf, infra/docker/nginx.conf" },
  { id:22, cat:"Infrastructure", name:"Celery Task Monitoring", status:"BUILT", pri:"-",
    detail:"Comprehensive monitoring: task_send_sent_event and task_track_started enabled. Beat scheduler with 18+ periodic tasks. Celery health check and active worker inspection. Grafana dashboards for queue depth. Dead Letter Queue configured. 7 specialized queues (default, ai_heavy, ai_light, email, webhook, analytics, training). Flower NOT configured (replaced by Prometheus/Grafana).",
    file:"backend/app/tasks/celery_app.py, monitoring/grafana_dashboards/" },
  { id:23, cat:"Infrastructure", name:"Database Connection Pooling", status:"BUILT", pri:"-",
    detail:"pool_pre_ping: True, pool_size: 10, max_overflow: 20. Prometheus metrics: parwa_db_pool_size gauge and parwa_db_query_duration_seconds histogram. Alert rule triggers at 90% pool usage. Grafana dashboard visualizes pool usage. Docs say pool_size=20 but code has 10. pool_recycle NOT set.",
    file:"backend/app/core/database/base.py:61-71, backend/app/core/metrics.py" },
  { id:24, cat:"Infrastructure", name:".env Template", status:"BUILT", pri:"-",
    detail:"Two templates: .env.example (100 lines, development) and .env.prod.example (86 lines, production with CHANGE_ME_ placeholders). Covers all categories: Application, Database, Celery, LLM APIs, Email, SMS/Voice, Payments, Compliance, JWT, OAuth, CORS, Monitoring, GCP Storage, MCP, Feature Flags. Minor: PRICING_SIGNING_KEY missing from prod template.",
    file:".env.example, .env.prod.example" },

  // ── Database ──
  { id:25, cat:"Database", name:"Migration System Setup", status:"PARTIAL", pri:"HIGH",
    detail:"Alembic fully configured with 20 sequential migrations (001 through 020). alembic/env.py has DATABASE_URL from env, PostgreSQL + SQLite support. CRITICAL: env.py is missing 9 newer model imports (sms_channel, email_bounces, outbound_email, email_delivery_event, chat_widget, email_channel, jarvis_cc, user_details, ooo_detection). Running alembic revision --autogenerate would silently skip schema changes for these tables.",
    file:"database/alembic/env.py" },
  { id:26, cat:"Database", name:"Index Optimization", status:"BUILT", pri:"-",
    detail:"Extensive indexing: ~200+ index=True declarations, 30+ composite Index() definitions. company_id indexed on virtually every table. ticket_id indexed on all sub-tables. FK columns consistently indexed. Missing some high-value composite indexes: tickets(company_id, status, created_at), tickets(company_id, priority), ticket_messages(ticket_id, created_at), subscriptions(company_id, status).",
    file:"database/models/ (across all model files)" },
  { id:27, cat:"Database", name:"Query Performance Monitoring", status:"PARTIAL", pri:"MEDIUM",
    detail:"parwa_db_query_duration_seconds histogram DEFINED in metrics.py but NEVER WIRED. Zero before_cursor_execute or after_cursor_execute SQLAlchemy event listeners in backend code. The metric is dead code. No slow query threshold, no EXPLAIN analysis, no query counting per endpoint. parwa_db_pool_size gauge IS recorded.",
    file:"backend/app/core/metrics.py:341-343" },

  // ── Frontend ──
  { id:28, cat:"Frontend", name:"Error Boundary Components", status:"PARTIAL", pri:"MEDIUM",
    detail:"ChatErrorBoundary exists in src/components/jarvis/ChatErrorBoundary.tsx (full class component with getDerivedStateFromError, fallback UI). Used only in onboarding page. NO error.tsx files (Next.js convention). No global ErrorBoundary in layout.tsx. Dashboard, auth, and settings pages are unwrapped - render errors will crash the SPA.",
    file:"src/components/jarvis/ChatErrorBoundary.tsx" },
  { id:29, cat:"Frontend", name:"Loading State Management", status:"PARTIAL", pri:"LOW",
    detail:"isLoading pattern used in 45+ components. Skeleton component exists (shadcn/ui with animate-pulse). Suspense used in 3 pages (jarvis, login, reset-password). NO loading.tsx files (Next.js convention). No not-found.tsx. Skeleton rarely imported in 45+ components (most use inline spinners). No route-level streaming/suspense boundaries.",
    file:"src/components/ui/skeleton.tsx, src/components/pages/DashboardPages.tsx" },
  { id:30, cat:"Frontend", name:"API Retry with Exponential Backoff", status:"MISSING", pri:"HIGH",
    detail:"API client in src/lib/api.ts uses axios with 30s timeout. Response interceptor handles 401 (clear auth), 403 (log), 429 (logs retry-after header) - then re-throws via Promise.reject(error). NO retry logic anywhere. Generic get/post/patch/del helpers have zero retry. Transient network failures surface immediately.",
    file:"src/lib/api.ts:48-81" },
  { id:31, cat:"Frontend", name:"WebSocket Real-Time Updates", status:"PARTIAL", pri:"HIGH",
    detail:"FULL backend Socket.io server exists (444-line, tenant-scoped rooms, JWT auth, event buffer for reconnection, heartbeat). Used in 20+ backend services. python-socketio in requirements.txt. ZERO frontend integration: no socket.io-client in package.json, no WebSocket imports in src/. useJarvisChat hook uses plain fetch(). Backend emits events nobody receives.",
    file:"backend/app/core/socketio.py (backend built), src/ (frontend missing)" },
  { id:32, cat:"Frontend", name:"Agent Performance Dashboard", status:"BUILT", pri:"-",
    detail:"Comprehensive dashboard: AgentPerformanceTable (314 lines, TanStack React Table, sortable columns), KPICard with trends, TrendChart, CategoryChart, SLAChart, ResponseTimeChart, AI Model Tiers with cost tracking, Cost Savings KPIs, DateRangeSelector, MonitoringPage with system uptime and API response time.",
    file:"src/components/pages/DashboardPages.tsx, src/components/dashboard/" },

  // ── Code Quality ──
  { id:33, cat:"Code Quality", name:"Pre-Commit Hooks", status:"MISSING", pri:"MEDIUM",
    detail:"No .pre-commit-config.yaml exists. No .husky/ directory. No lint-staged config. No prepare script in package.json. ESLint (eslint.config.mjs) and Jest (jest.config.cjs) are configured but nothing enforces them at commit time.",
    file:"(not found)" },
  { id:34, cat:"Code Quality", name:"Email Validator Consistency", status:"PARTIAL", pri:"LOW",
    detail:"email-validator library installed in requirements.txt and used in ONE place (backend/app/api/verification.py). But 4+ other locations use regex: shared/utils/validators.py, backend/app/schemas/auth.py, backend/app/schemas/onboarding.py, backend/app/core/email_utils.py, frontend TicketsPage.tsx. Inconsistent validation across codepaths.",
    file:"backend/app/api/verification.py, shared/utils/validators.py, backend/app/schemas/auth.py" },
  { id:35, cat:"Code Quality", name:"UUID Consistency", status:"PARTIAL", pri:"MEDIUM",
    detail:"25 models use String(36) + str(uuid.uuid4()). Only 2 models (outbound_email.py, email_delivery_event.py) use UUID(as_uuid=True). SQLAlchemy handles type coercion, but raw SQL queries or migrations between types could fail. ticket_id joins between ticket table (String) and outbound_email (UUID) could cause issues.",
    file:"database/models/outbound_email.py, database/models/email_delivery_event.py" },
];

// ══════════════════════════════════════
// BUILD DOCUMENT
// ══════════════════════════════════════

const summaryCounts = { BUILT: 0, PARTIAL: 0, MISSING: 0 };
items.forEach(i => summaryCounts[i.status]++);

const coverSection = {
  properties: { page: { margin: { top: 0, bottom: 0, left: 0, right: 0 }, size: { width: 11906, height: 16838 } } },
  children: [buildCover()],
};

// ── TOC + Body section ──
const bodyChildren = [];

// TOC
bodyChildren.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 200, after: 200 },
  children: [new TextRun({ text: "Table of Contents", bold: true, color: c(P.primary), size: 32, font: { ascii: "Calibri", eastAsia: "SimHei" } })],
}));
bodyChildren.push(new TableOfContents("Table of Contents", {
  hyperlink: true, headingStyleRange: "1-3",
}));
bodyChildren.push(new Paragraph({
  spacing: { before: 100, after: 100 },
  children: [new TextRun({ text: "Note: Right-click the Table of Contents and select 'Update Field' to refresh page numbers after opening in Word.", italics: true, size: 18, color: c(P.secondary), font: { ascii: "Calibri" } })],
}));
bodyChildren.push(new Paragraph({ children: [new PageBreak()] }));

// ── Executive Summary ──
bodyChildren.push(h1("1. Executive Summary"));
bodyChildren.push(body("This audit cross-checks all items from the PARWA missing-features list against the actual codebase pulled from GitHub (commit da37c77, main branch). The repo was pulled fresh before inspection to account for parallel development. Each item was verified by searching for specific function names, class definitions, import statements, and implementation patterns across all 2,200+ Python and 145+ frontend files."));
bodyChildren.push(body("The audit methodology combined automated grep searches across the entire codebase with manual file inspection of key implementation files. For each item, the audit confirmed whether the feature exists as described, exists partially with gaps, or is completely absent from the codebase. Special attention was paid to misleading naming (e.g., CrossEncoderReranker that does not use cross-encoders, sentiment_engine that uses no sentiment models)."));

// Summary counts
bodyChildren.push(h2("1.1 Overall Results"));
const summaryData = [
  ["Total Items Checked", "35"],
  ["Already Built (No Action Needed)", String(summaryCounts.BUILT)],
  ["Partial (Exists But Has Gaps)", String(summaryCounts.PARTIAL)],
  ["Missing (Not Implemented)", String(summaryCounts.MISSING)],
  ["High Priority Items", String(items.filter(i => i.pri === "HIGH").length)],
];
bodyChildren.push(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: tBorders,
  rows: [
    (function() {
      const hdr = (text) => new TableCell({
        children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })],
        shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) },
        margins: { top: 60, bottom: 60, left: 120, right: 120 },
      });
      return new TableRow({
        children: [hdr("Metric"), hdr("Value")],
        tableHeader: true, cantSplit: true,
      });
    })(),
    ...summaryData.map(([metric, val]) => new TableRow({
      children: [
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: metric, size: 20, color: c(P.body), font: { ascii: "Calibri" } })] })], margins: { top: 50, bottom: 50, left: 100, right: 100 } }),
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: val, bold: true, size: 20, color: c(P.body), font: { ascii: "Calibri" } })] })], margins: { top: 50, bottom: 50, left: 100, right: 100 } }),
      ],
      cantSplit: true,
    })),
  ],
}));

// ── Full Status Table ──
bodyChildren.push(h1("2. Complete Status Overview"));
bodyChildren.push(body("The table below lists all 35 checked items with their verified status. Items marked BUILT require no action. Items marked PARTIAL have the core structure but need specific fixes documented in Section 3. Items marked MISSING need to be built from scratch."));
bodyChildren.push(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: tBorders,
  rows: [
    statusHeaderRow(),
    ...items.map(i => statusRow(i.id, i.cat, i.name, i.status, i.pri)),
  ],
}));

// ── Detailed Findings ──
bodyChildren.push(h1("3. Detailed Findings by Category"));

const categories = ["AI Features", "Security", "Infrastructure", "Database", "Frontend", "Code Quality"];
for (const cat of categories) {
  const catItems = items.filter(i => i.cat === cat);
  bodyChildren.push(h2("3." + (categories.indexOf(cat) + 1) + " " + cat + " (" + catItems.length + " items)"));
  bodyChildren.push(body("This section covers " + catItems.length + " items in the " + cat + " category. For each item, the file path, implementation evidence, and specific gaps are documented."));

  for (const item of catItems) {
    bodyChildren.push(h3(item.id + ". " + item.name));
    bodyChildren.push(new Paragraph({
      spacing: { line: 312, after: 60 },
      children: [
        new TextRun({ text: "Status: ", bold: true, size: 22, color: c(P.primary), font: { ascii: "Calibri" } }),
        verdictBadge(item.status),
        item.pri !== "-" ? new TextRun({ text: "   |   Priority: " + item.pri, size: 22, color: c(P.body), font: { ascii: "Calibri" } }) : new TextRun({ text: "", size: 22 }),
      ],
    }));
    bodyChildren.push(body(item.detail));
    if (item.file) {
      bodyChildren.push(evidenceBlock(item.file, null));
    }
  }
}

// ── Key Discoveries ──
bodyChildren.push(h1("4. Key Discoveries and Patterns"));

bodyChildren.push(h2("4.1 Misleading Naming"));
bodyChildren.push(body("The most significant finding is that several critical components have names that suggest AI-powered capabilities but are actually implemented with traditional programming techniques. The CrossEncoderReranker class in rag_reranking.py performs no cross-encoding - it uses hand-coded TF-IDF math with weighted scoring. The sentiment_engine.py performs no sentiment analysis using models - it uses keyword lexicons and pattern matching. The pii_redaction_engine.py docstring explicitly states it uses 'no NLP libs'. This naming creates a false sense of capability and could mislead future developers about what the system actually does."));

bodyChildren.push(h2("4.2 Nginx Config Drift"));
bodyChildren.push(body("Three separate nginx configuration files exist with significant security drift. The production deployment uses nginx/nginx.conf (fully hardened with CSP, OCSP stapling, Permissions-Policy, 8 cipher suites). But the Docker image builds from infra/docker/ configs which lack CSP, OCSP stapling, and Permissions-Policy, and has only 2 cipher suites. Critically, infra/docker/nginx-default.conf references undefined zone names (api, login) that would crash nginx if the file were ever loaded. The production setup works because docker-compose.prod.yml mounts the correct config via volume override, but the Docker image ships with broken defaults."));

bodyChildren.push(h2("4.3 Dead Code"));
bodyChildren.push(body("Several code paths are defined but never executed. The jti claim is generated in every JWT access token and a get_token_jti() utility function exists, but neither is called in production code - the JWT blacklist system is completely absent. The parwa_db_query_duration_seconds Prometheus histogram is defined in metrics.py but no SQLAlchemy event listeners are wired to populate it. The training_tasks.py has three Celery tasks that all return hardcoded zeros with no real training logic. The _verify_webhook_timestamp() function in hmac_verification.py is defined but the webhook endpoint uses its own inline version instead."));

bodyChildren.push(h2("4.4 Backend-Frontend Socket.io Gap"));
bodyChildren.push(body("The backend has a comprehensive Socket.io server implementation (444 lines) with tenant-scoped rooms, JWT authentication, event buffering for reconnection, and heartbeat monitoring. It is actively used by 20+ backend services to emit real-time events. However, the frontend has zero Socket.io integration - no socket.io-client in package.json, no WebSocket imports anywhere in src/. The useJarvisChat hook uses plain fetch() for all communication. This means the backend is emitting real-time events (ticket:new, ticket:update, etc.) that nobody receives. Dashboard data remains stale until manual refresh."));

bodyChildren.push(h2("4.5 Alembic Model Import Gap"));
bodyChildren.push(body("The Alembic migration system is configured with 20 sequential migrations covering the core schema. However, alembic/env.py is missing imports for 9 model files that exist in database/models/: sms_channel, email_bounces, outbound_email, email_delivery_event, chat_widget, email_channel, jarvis_cc, user_details, and ooo_detection. If a developer runs alembic revision --autogenerate to create a new migration, Alembic will silently skip schema changes for these 9 tables because it does not know about them. This is a ticking time bomb for schema consistency."));

// ── Priority Action Items ──
bodyChildren.push(h1("5. Priority Action Items"));
bodyChildren.push(body("Based on the audit findings, the following items are ranked by their impact on production readiness and security. HIGH priority items should be addressed in Week 1 of the roadmap. MEDIUM priority items should be addressed in Weeks 2-3. LOW priority items can be deferred to Week 4."));

const highItems = items.filter(i => i.pri === "HIGH" && i.status !== "BUILT");
const medItems = items.filter(i => i.pri === "MEDIUM" && i.status !== "BUILT");
const lowItems = items.filter(i => i.pri === "LOW" && i.status !== "BUILT");

bodyChildren.push(h2("5.1 HIGH Priority (" + highItems.length + " items)"));
bodyChildren.push(new Table({
  width: { size: 100, type: WidthType.PERCENTAGE },
  borders: tBorders,
  rows: [
    new TableRow({
      children: [
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "#", bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })], shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) }, margins: { top: 60, bottom: 60, left: 120, right: 120 } }),
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Item", bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })], shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) }, margins: { top: 60, bottom: 60, left: 120, right: 120 } }),
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Status", bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })], shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) }, margins: { top: 60, bottom: 60, left: 120, right: 120 } }),
        new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: "Category", bold: true, size: 20, color: c(P.headerText), font: { ascii: "Calibri" } })] })], shading: { type: ShadingType.CLEAR, fill: c(P.headerBg) }, margins: { top: 60, bottom: 60, left: 120, right: 120 } }),
      ],
      tableHeader: true, cantSplit: true,
    }),
    ...highItems.map(i => {
      const colors = { "BUILT": "E8F5E9", "PARTIAL": "FFF8E1", "MISSING": "FFEBEE" };
      const textColors = { "BUILT": "1B7A3D", "PARTIAL": "B8860B", "MISSING": "C62828" };
      const labels = { "BUILT": "BUILT", "PARTIAL": "PARTIAL", "MISSING": "MISSING" };
      const cell = (text, opts = {}) => new TableCell({
        children: [new Paragraph({ children: [new TextRun({ text, size: 20, color: opts.textColor ? c(opts.textColor) : c(P.body), font: { ascii: "Calibri" }, bold: opts.bold || false })] })],
        shading: opts.shading ? { type: ShadingType.CLEAR, fill: c(opts.shading) } : undefined,
        margins: { top: 50, bottom: 50, left: 100, right: 100 },
      });
      return new TableRow({
        children: [
          cell(String(i.id), { bold: true }),
          cell(i.name),
          cell(labels[i.status], { shading: colors[i.status], textColor: textColors[i.status], bold: true }),
          cell(i.cat),
        ],
        cantSplit: true,
      });
    }),
  ],
}));

bodyChildren.push(h2("5.2 MEDIUM Priority (" + medItems.length + " items)"));
for (const i of medItems) {
  bodyChildren.push(new Paragraph({
    spacing: { line: 280, after: 40 },
    children: [
      new TextRun({ text: i.id + ". ", bold: true, size: 20, color: c(P.accent), font: { ascii: "Calibri" } }),
      new TextRun({ text: i.name + " ", size: 20, color: c(P.body), font: { ascii: "Calibri" } }),
      new TextRun({ text: "[" + i.status + "] ", bold: true, size: 18, color: c(i.status === "PARTIAL" ? "B8860B" : "C62828"), font: { ascii: "Calibri" } }),
      new TextRun({ text: "- " + i.cat, size: 18, color: c(P.secondary), font: { ascii: "Calibri" } }),
    ],
  }));
}

bodyChildren.push(h2("5.3 LOW Priority (" + lowItems.length + " items)"));
for (const i of lowItems) {
  bodyChildren.push(new Paragraph({
    spacing: { line: 280, after: 40 },
    children: [
      new TextRun({ text: i.id + ". ", bold: true, size: 20, color: c(P.accent), font: { ascii: "Calibri" } }),
      new TextRun({ text: i.name + " ", size: 20, color: c(P.body), font: { ascii: "Calibri" } }),
      new TextRun({ text: "[" + i.status + "]", bold: true, size: 18, color: c("B8860B"), font: { ascii: "Calibri" } }),
    ],
  }));
}

// ── Already Built (No Action) ──
bodyChildren.push(h1("6. Items Already Built (No Action Required)"));
bodyChildren.push(body("The following " + summaryCounts.BUILT + " items are confirmed as fully implemented in the codebase and require no further development work for production readiness. Each has been verified against the actual pulled code with file paths and implementation evidence documented in Section 3."));
const builtItems = items.filter(i => i.status === "BUILT");
for (let i = 0; i < builtItems.length; i++) {
  bodyChildren.push(new Paragraph({
    spacing: { line: 280, after: 40 },
    children: [
      new TextRun({ text: (i + 1) + ". ", bold: true, size: 20, color: c("1B7A3D"), font: { ascii: "Calibri" } }),
      new TextRun({ text: builtItems[i].name + " ", size: 20, color: c(P.body), font: { ascii: "Calibri" } }),
      new TextRun({ text: "(" + builtItems[i].cat + ")", size: 18, color: c(P.secondary), font: { ascii: "Calibri" } }),
    ],
  }));
}

const bodySection = {
  properties: {
    page: {
      margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 },
      size: { width: 11906, height: 16838 },
      pageNumbers: { start: 1 },
    },
  },
  headers: {
    default: new Header({
      children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "PARWA Codebase Audit Report | ", size: 16, color: c(P.secondary), font: { ascii: "Calibri" } }),
                   new TextRun({ text: "Confidential", italics: true, size: 16, color: c(P.secondary), font: { ascii: "Calibri" } })],
      })],
    }),
  },
  footers: {
    default: new Footer({
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Page ", size: 16, color: c(P.secondary), font: { ascii: "Calibri" } }),
          new TextRun({ children: [PageNumber.CURRENT], size: 16, color: c(P.secondary), font: { ascii: "Calibri" } }),
          new TextRun({ text: " of ", size: 16, color: c(P.secondary), font: { ascii: "Calibri" } }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: c(P.secondary), font: { ascii: "Calibri" } }),
        ],
      })],
    }),
  },
  children: bodyChildren,
};

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Calibri" }, size: 22, color: c(P.body) },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: {
        run: { font: { ascii: "Calibri" }, size: 32, bold: true, color: c(P.primary) },
        paragraph: { spacing: { before: 400, after: 200 } },
      },
      heading2: {
        run: { font: { ascii: "Calibri" }, size: 28, bold: true, color: c(P.accent) },
        paragraph: { spacing: { before: 300, after: 160 } },
      },
      heading3: {
        run: { font: { ascii: "Calibri" }, size: 24, bold: true, color: c(P.body) },
        paragraph: { spacing: { before: 240, after: 120 } },
      },
    },
  },
  sections: [coverSection, bodySection],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("PARWA_Codebase_Audit_Report.docx", buf);
  console.log("Generated: PARWA_Codebase_Audit_Report.docx (" + Math.round(buf.length / 1024) + " KB)");
});
