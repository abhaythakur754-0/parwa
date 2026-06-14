const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, PageNumber, PageBreak,
  BorderStyle, WidthType, ShadingType, TableOfContents, LevelFormat,
  ImageRun, TabStopType, TabStopPosition
} = require("docx");

// ── Palette: GO-1 Graphite Orange (proposal/plan) ──
const P = {
  primary: "1A2330", body: "000000", secondary: "607080",
  accent: "D4875A", surface: "FDF8F3",
  coverBg: "1A2330", coverPrimary: "FFFFFF", coverAccent: "D4875A", coverMuted: "90989F",
};
const c = (hex) => hex.replace("#", "");
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const allNoBorders = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };

// ── Helper functions ──
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 480, after: 200 },
    keepNext: true,
    children: [new TextRun({ text, bold: true, color: c(P.primary), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 32 })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 360, after: 160 },
    keepNext: true,
    children: [new TextRun({ text, bold: true, color: c(P.primary), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 28 })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 120 },
    keepNext: true,
    children: [new TextRun({ text, bold: true, color: c(P.secondary), font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 26 })],
  });
}
function body(text) {
  return new Paragraph({
    spacing: { after: 120, line: 312 },
    children: [new TextRun({ text, size: 22, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } })],
  });
}
function bodyBold(label, text) {
  return new Paragraph({
    spacing: { after: 120, line: 312 },
    children: [
      new TextRun({ text: label, bold: true, size: 22, color: c(P.primary), font: { ascii: "Calibri" } }),
      new TextRun({ text, size: 22, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } }),
    ],
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    spacing: { after: 60, line: 312 },
    indent: { left: 480 + level * 360 },
    bullet: { level },
    children: [new TextRun({ text, size: 22, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } })],
  });
}
function statusLine(label, status) {
  const colorMap = { "DONE": "2E7D32", "PARTIAL": "E65100", "NOT DONE": "C62828", "PENDING": "1565C0" };
  const col = colorMap[status] || c(P.body);
  return new Paragraph({
    spacing: { after: 80, line: 312 },
    indent: { left: 480 },
    children: [
      new TextRun({ text: label + " ", size: 22, color: c(P.body), font: { ascii: "Calibri" } }),
      new TextRun({ text: "[" + status + "]", bold: true, size: 22, color: col, font: { ascii: "Calibri" } }),
    ],
  });
}

// ── Table helpers ──
const TABLE_HEADER_BG = c("D4875A");
const TABLE_HEADER_TEXT = "FFFFFF";
const TABLE_ALT_ROW = c("FDF8F3");
const TABLE_BORDER_COLOR = "D0D0D0";

function tableHeaderCell(text, width) {
  return new TableCell({
    width: { size: width, type: WidthType.PERCENTAGE },
    shading: { type: ShadingType.CLEAR, fill: TABLE_HEADER_BG },
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 21, color: TABLE_HEADER_TEXT, font: { ascii: "Calibri" } })] })],
    borders: { top: NB, bottom: { style: BorderStyle.SINGLE, size: 2, color: "FFFFFF" }, left: NB, right: NB },
  });
}
function tableDataCell(text, width, rowIndex) {
  return new TableCell({
    width: { size: width, type: WidthType.PERCENTAGE },
    shading: rowIndex % 2 === 0 ? { type: ShadingType.CLEAR, fill: TABLE_ALT_ROW } : undefined,
    margins: { top: 60, bottom: 60, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, size: 21, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } })] })],
    borders: { top: NB, bottom: NB, left: NB, right: NB },
  });
}
function makeTable(headers, rows, colWidths) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => tableHeaderCell(h, colWidths[i])),
  });
  const dataRows = rows.map((row, ri) => new TableRow({
    children: row.map((cell, ci) => tableDataCell(cell, colWidths[ci], ri)),
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: TABLE_BORDER_COLOR }, insideVertical: NB },
    rows: [headerRow, ...dataRows],
  });
}

// ── Cover Page (R4 Top Color Block variant for Graphite Orange) ──
function buildCover() {
  const accentBarHeight = 600;
  const coverChildren = [
    new Paragraph({ spacing: { before: 2400 }, children: [] }),
    new Paragraph({
      spacing: { after: 200 },
      children: [new TextRun({ text: "PARWA", bold: true, size: 72, color: c(P.coverPrimary), font: { ascii: "Calibri" } })],
    }),
    new Paragraph({
      spacing: { after: 400, line: 400 },
      children: [new TextRun({ text: "10-Day Fix-All Roadmap", bold: true, size: 40, color: c(P.coverPrimary), font: { ascii: "Calibri" } })],
    }),
    new Paragraph({
      spacing: { after: 100 },
      children: [new TextRun({ text: "Merged Execution Plan: Days 4\u201310", size: 26, color: c(P.coverAccent), font: { ascii: "Calibri" } })],
    }),
    new Paragraph({
      spacing: { after: 100 },
      children: [new TextRun({ text: "Cross-Checked Codebase Audit + Gap Remediation", size: 24, color: c(P.coverMuted), font: { ascii: "Calibri" } })],
    }),
    new Paragraph({ spacing: { before: 1200 }, children: [] }),
    new Paragraph({
      children: [new TextRun({ text: "Version 2.0  |  May 2026  |  Phase-Wise Execution", size: 22, color: c(P.coverMuted), font: { ascii: "Calibri" } })],
    }),
    new Paragraph({
      children: [new TextRun({ text: "Days 1\u20133: VERIFIED  |  Days 4\u201310: MERGED PLAN", size: 22, color: c(P.coverAccent), font: { ascii: "Calibri" } })],
    }),
  ];
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: allNoBorders,
    rows: [
      new TableRow({
        height: { value: 16838, rule: "exact" },
        verticalAlign: "top",
        children: [
          new TableCell({
            width: { size: 100, type: WidthType.PERCENTAGE },
            shading: { type: ShadingType.CLEAR, fill: c(P.coverBg) },
            borders: allNoBorders,
            margins: { left: 1200, right: 1200, top: 0, bottom: 0 },
            children: coverChildren,
          }),
        ],
      }),
    ],
  });
}

// ── Build Document ──
async function main() {
  const doc = new Document({
    styles: {
      default: {
        document: {
          run: { font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" }, size: 22, color: c(P.body) },
          paragraph: { spacing: { line: 312 } },
        },
        heading1: { run: { font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 32, bold: true, color: c(P.primary) } },
        heading2: { run: { font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 28, bold: true, color: c(P.primary) } },
        heading3: { run: { font: { ascii: "Calibri", eastAsia: "SimHei" }, size: 26, bold: true, color: c(P.secondary) } },
      },
    },
    numbering: { config: [] },
    sections: [
      // ── COVER ──
      {
        properties: { page: { margin: { top: 0, bottom: 0, left: 0, right: 0 } } },
        children: [buildCover()],
      },
      // ── TOC ──
      {
        properties: {
          page: { margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 } },
        },
        headers: {
          default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "PARWA 10-Day Fix-All Roadmap", size: 18, color: c(P.secondary), font: { ascii: "Calibri" } })] })] }),
        },
        footers: {
          default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: c(P.secondary) })] })] }),
        },
        children: [
          new Paragraph({
            spacing: { after: 200 },
            children: [new TextRun({ text: "Table of Contents", bold: true, size: 36, color: c(P.primary), font: { ascii: "Calibri" } })],
          }),
          new TableOfContents("Table of Contents", {
            hyperlink: true,
            headingStyleRange: "1-3",
          }),
          new Paragraph({
            spacing: { before: 200, after: 100 },
            children: [new TextRun({ text: "(Right-click on the table of contents above and select 'Update Field' to refresh page numbers after opening in Word.)", italics: true, size: 20, color: c(P.secondary), font: { ascii: "Calibri" } })],
          }),
          new Paragraph({ children: [new PageBreak()] }),
        ],
      },
      // ── BODY ──
      {
        properties: {
          page: {
            margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 },
            pageNumbers: { start: 1 },
          },
        },
        headers: {
          default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "PARWA 10-Day Fix-All Roadmap", size: 18, color: c(P.secondary), font: { ascii: "Calibri" } })] })] }),
        },
        footers: {
          default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: c(P.secondary) })] })] }),
        },
        children: [
          // ═══════════════════════════════════════════
          // SECTION 1: EXECUTIVE SUMMARY
          // ═══════════════════════════════════════════
          h1("1. Executive Summary"),
          body("This document is the merged and cross-checked execution roadmap for bringing the PARWA AI Customer Care SaaS platform to production readiness. It consolidates two independent audit streams: the original 10-Day Fix-All Roadmap (covering 120+ gaps across security, AI integrity, and infrastructure) and a separate code-level audit that identified 6 major architectural gaps and 6 critical bugs. Days 1 through 3 of the original roadmap have been completed and are verified against the actual codebase in this document."),
          body("The cross-check audit examined every file referenced in the Day 1-3 checklist items. Day 1 (Critical Security: Auth and Access Control) scored 13 out of 13 items fully DONE, with real, verifiable code changes across frontend JWT authentication, httpOnly cookie migration, timing-safe OTP comparison, MFA temporary session tokens, platform admin access control, MCP server auth enforcement, and chat API authentication. Day 2 (Critical Security: Data Protection and Infrastructure) scored 8 out of 12 items DONE, with 3 items PARTIAL and 1 item NOT DONE. Day 3 (AI Rebuild: Core LLM Integration) confirmed that all 12 AI reasoning techniques make real LLM API calls through the llm_gateway.py module, contradicting the original roadmap's claim that they were pure regex stubs."),
          body("The remaining work from Days 4 through 10 has been reorganized to incorporate both the original roadmap's items and the additional gaps discovered during the independent audit. Key additions include: building 7 empty frontend dashboard stub pages, implementing the FAKE Voting system for the MAKER Framework, adding Socket.io real-time frontend integration, implementing Row Level Security (RLS), building the 25 Loophole Solutions module, and fixing 6 critical database and infrastructure bugs. Each day builds upon the previous day's work, with clear acceptance criteria and estimated effort hours."),

          // ═══════════════════════════════════════════
          // SECTION 2: CROSS-CHECK RESULTS
          // ═══════════════════════════════════════════
          h1("2. Days 1\u20133 Cross-Check Results"),
          body("The following section summarizes the independent verification of Days 1 through 3 against the actual codebase. Each item was checked by reading the specific file and line numbers referenced in the original roadmap. The results are organized by day with individual status indicators and evidence summaries."),

          h2("2.1 Day 1: Critical Security \u2014 Auth and Access Control"),
          body("Theme: Eliminate all authentication and access control vulnerabilities. All 13 items were verified as DONE with real code changes."),
          makeTable(
            ["ID", "Item", "Status", "Evidence"],
            [
              ["C-02", "Frontend JWT tokens (not parwa_at UUID)", "DONE", "jose library; SignJWT with claims"],
              ["C-03", "httpOnly cookies (not localStorage)", "DONE", "auth-cookies.ts: httpOnly: true"],
              ["H-03", "Email verification required", "DONE", "is_verified: false + sendEmail"],
              ["H-02", "Timing-safe OTP comparison", "DONE", "crypto.timingSafeEqual in verify/reset"],
              ["M-20", "Password complexity rules", "DONE", "validatePasswordStrength() 5 checks"],
              ["C-01", "Dashboard API auth middleware", "DONE", "middleware.ts: JWT verify + 401"],
              ["C-09", "MFA temp session token", "DONE", "_mfa_pending_sessions dict + 5min TTL"],
              ["C-10", "Platform admin flag", "DONE", "require_platform_admin() in deps.py"],
              ["C-11", "Billing status authenticated", "DONE", "require_platform_admin on endpoint"],
              ["C-12", "RAG scoped to JWT tenant", "DONE", "Depends(get_company_id), no body override"],
              ["C-04", "MCP auth token enforced", "DONE", "MCPAuthTokenMiddleware + hmac.compare"],
              ["H-14", "Chat widget company_id validated", "DONE", "DB lookup before session creation"],
              ["H-18", "Chat API authenticated", "DONE", "Token extraction + verifyToken + 401"],
            ],
            [8, 35, 10, 47]
          ),
          new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }),

          h2("2.2 Day 2: Critical Security \u2014 Data Protection"),
          body("Theme: Fix remaining CRITICAL vulnerabilities for secrets, cross-tenant isolation, and infrastructure. Scored 8 DONE, 3 PARTIAL, 1 NOT DONE."),
          makeTable(
            ["ID", "Item", "Status", "Evidence / Gap"],
            [
              ["C-05", "CORS wildcard removed", "DONE", "Fail-closed to localhost on exception"],
              ["C-06", "Config validators raise ValueError", "DONE", "4 validators raise in production"],
              ["C-07", ".env.prod removed from git", "NOT DONE", "Still in git ls-files; needs git rm --cached"],
              ["C-15", "No default refresh pepper", "PARTIAL", "Prod RuntimeError exists; dev defaults to empty"],
              ["C-08", "X-Company-ID not trusted", "DONE", "JWT-only extraction in variant_check.py"],
              ["C-13", "PostgreSQL SSL required", "DONE", "sslmode=require auto-appended"],
              ["C-14", "OAuth tokens encrypted at rest", "PARTIAL", "Fernet (AES-128-CBC), not AES-256-GCM"],
              ["H-05", "Billing/admin not in PUBLIC_PREFIXES", "DONE", "Explicitly excluded with comment"],
              ["H-22", "Workflow path param validated", "DONE", "JWT company_id check on all endpoints"],
              ["H-09", "Pricing key from env var", "PARTIAL", "Has hardcoded dev fallback string"],
              ["H-10", "Redis password required", "DONE", "Prod validator + TLS cert verification"],
              ["H-11", "SHA-256 for file integrity", "DONE", "All checksums use SHA-256; no MD5"],
            ],
            [8, 32, 12, 48]
          ),
          new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }),

          h2("2.3 Day 3: AI Rebuild \u2014 Core LLM Integration"),
          body("IMPORTANT FINDING: The original roadmap stated that the 12 AI techniques were 'pure regex and template matching with zero LLM API calls.' Cross-checking reveals this is INCORRECT. All 12 techniques import from llm_gateway.py and make real LLM calls via llm_gateway.generate(). The architecture is LLM-first with graceful template fallback, not 'pure regex.' This means Day 3's primary objective was already substantially met before the rebuild began. Two foundation items remain unmet: the shared client path and base class method."),
          makeTable(
            ["ID", "Item", "Status", "Evidence"],
            [
              ["AI-F01", "Shared LLM technique client", "PARTIAL", "llm_gateway.py exists at core/ (not techniques/)"],
              ["AI-F02", "execute_with_llm() in base.py", "NOT DONE", "Method does not exist; LLM calls in each file"],
              ["AI-01", "Chain of Thought", "REAL LLM", "2 LLM call sites + template fallback"],
              ["AI-02", "Tree of Thought", "REAL LLM", "1 LLM call site + heuristic fallback"],
              ["AI-03", "ReAct", "REAL LLM", "2 LLM call sites + pattern fallback"],
              ["AI-04", "Reflexion", "REAL LLM", "1 LLM call site + regex fallback"],
              ["AI-05", "Self-Consistency", "REAL LLM", "1 LLM call site + deterministic pipeline"],
              ["AI-06", "Universe of Thought", "REAL LLM", "1 LLM call site + weighted scoring"],
              ["AI-08", "Least-to-Most", "REAL LLM", "1 LLM call site + template decomposition"],
              ["AI-10", "Step-Back", "REAL LLM", "1 LLM call site + template broadening"],
              ["AI-11", "Reverse Thinking", "REAL LLM", "2 LLM call sites + template inversion"],
            ],
            [8, 30, 12, 50]
          ),
          new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }),

          h2("2.4 Items Carried Forward to Day 4"),
          body("The following 6 items from Days 2 and 3 were not fully resolved and must be addressed at the start of Day 4 before proceeding with new work. These are quick fixes (estimated 2-3 hours total) that close out the remaining security and architecture debt from the first three days."),
          bullet("[C-07] Run git rm --cached .env.prod and commit to fully de-track the production environment file from version control."),
          bullet("[C-15] Add a startup warning when REFRESH_TOKEN_PEPPER is empty in development mode, matching the production RuntimeError pattern."),
          bullet("[C-14] Evaluate whether Fernet (AES-128-CBC + HMAC-SHA256) provides sufficient security or upgrade to AES-256-GCM. Fernet is authenticated encryption and may be acceptable with a documented decision."),
          bullet("[H-09] Add a production guard for PRICING_SIGNING_KEY that raises ValueError if the env var is empty, consistent with other config validators."),
          bullet("[AI-F01] Create a symlink or re-export at backend/app/core/techniques/llm_client.py that wraps llm_gateway.py for the specified path."),
          bullet("[AI-F02] Add execute_with_llm() method to BaseTechniqueNode in base.py that centralizes LLM call patterns from individual techniques."),

          // ═══════════════════════════════════════════
          // SECTION 3: MERGED ROADMAP DAYS 4-10
          // ═══════════════════════════════════════════
          h1("3. Merged Roadmap: Days 4\u201310"),
          body("The following 7-day plan merges the original Days 4-10 roadmap items with 6 additional gaps identified during the independent code audit: (1) Agent Lightning training system, (2) FAKE Voting for MAKER Framework, (3) 7 empty frontend dashboard pages, (4) Socket.io frontend integration, (5) Row Level Security (RLS), and (6) 25 Loophole Solutions module. Six critical database and infrastructure bugs are also included at the appropriate days."),

          // ── DAY 4 ──
          h2("3.1 Day 4: Leftover Fixes + Dashboard Frontend + FAKE Voting"),
          bodyBold("Theme: ", "Close out Days 1-3 debt, start building the 7 empty dashboard pages, and implement the FAKE Voting system for the MAKER Framework. This day addresses both quick wins and begins the larger frontend and AI framework work."),
          bodyBold("Estimated Effort: ", "10-12 hours"),
          bodyBold("Dependencies: ", "Days 1-3 completed and cross-checked"),

          h3("Day 4.1: Close Day 2-3 Leftovers (2-3 hours)"),
          body("[C-07] Remove .env.prod from git tracking entirely. Run git rm --cached .env.prod, commit the change, and add a pre-commit hook that prevents committing any .env files. The file should remain in .gitignore but must no longer appear in git ls-files output. Verify with git status after the commit."),
          body("[C-15] Add a non-silent warning for empty REFRESH_TOKEN_PEPPER in development. While the production RuntimeError guard is already in place, development environments silently use an empty pepper, making refresh token hashing effectively useless during development. Add a logging.warning() call that fires on startup when the pepper is empty, regardless of environment."),
          body("[C-14] Document the encryption decision for OAuth tokens. The current implementation uses Fernet (AES-128-CBC + HMAC-SHA256) which provides authenticated encryption. This is a different algorithm than the AES-256-GCM specified in the roadmap, but Fernet is a well-vetted, standard encryption scheme from the cryptography library. Create a brief ADR (Architecture Decision Record) documenting why Fernet was chosen and under what conditions an upgrade to AES-256-GCM would be warranted."),
          body("[H-09] Add a production guard to the PRICING_SIGNING_KEY configuration. Currently the key reads from an environment variable but falls back to a hardcoded dev string. Add a check in config.py that raises ValueError when ENVIRONMENT=production and the key still contains the dev default, matching the pattern used by other secret validators."),
          body("[AI-F01] Create backend/app/core/techniques/llm_client.py as a thin re-export wrapper around the existing llm_gateway.py module. This satisfies the roadmap's path requirement without duplicating the 632-line gateway implementation. The wrapper should re-export llm_gateway, LLMResponse, and any technique-specific helper methods."),
          body("[AI-F02] Add an execute_with_llm() method to BaseTechniqueNode in backend/app/core/techniques/base.py. This method should centralize the common LLM call pattern used across all 12 techniques: call llm_gateway.generate() with the technique's prompt, check for empty response, log token usage, and return a structured result. Individual techniques can then call self.execute_with_llm() instead of directly importing llm_gateway."),

          h3("Day 4.2: FAKE Voting System for MAKER Framework (3-4 hours)"),
          body("The MAKER Framework's validator node (11_maker_validator.py) currently generates K solutions and scores them but lacks the FAKE Voting mechanism described in the DMD. FAKE Voting is the process where multiple AI responses compete for selection through a structured scoring and voting system, with the highest-quality response winning. This is distinct from simple scoring because it involves adversarial evaluation where each response is critiqued by the others."),
          body("Implementation plan: (1) Extend the existing K-solution generation in 11_maker_validator.py to produce 3-5 candidate responses instead of the current single-response pattern. (2) Implement a voting phase where each candidate response is evaluated against the others using the LLM as a judge. (3) Each LLM judge call scores responses on accuracy, helpfulness, tone, and completeness using a structured rubric. (4) Aggregate scores across all judges and select the winner. (5) Implement the Red-Flagging subsystem that detects and penalizes responses containing hallucinations, policy violations, or PII leakage. (6) If all candidates are flagged, escalate to human review. Files: backend/app/core/langgraph/nodes/11_maker_validator.py, backend/app/core/maker_voting.py (new)."),

          h3("Day 4.3: Frontend Dashboard Pages - Batch 1 (5-6 hours)"),
          body("Seven dashboard sub-pages are currently empty stubs with placeholder content. These pages are the core operational interface for PARWA customers and must display real data from the backend APIs. Build the first batch of 4 pages on Day 4, with the remaining 3 on Day 6."),
          body("Tickets Page (src/app/(dashboard)/tickets/page.tsx): Build a full ticket management interface with a data table showing ticket ID, customer name, subject, status (open/in-progress/resolved/closed), priority, assigned agent, created date, and last updated. Implement filtering by status, priority, and date range. Add a ticket detail drawer/modal that shows the full conversation thread with the AI agent. Connect to backend GET /api/tickets endpoint."),
          body("Billing Page (src/app/(dashboard)/billing/page.tsx): Build a billing dashboard showing current subscription plan, next billing date, usage metrics (tickets resolved, tokens consumed, API calls made), and invoice history. Include an upgrade/downgrade plan selector that connects to the Paddle integration. Show cost breakdown by feature usage. Connect to backend GET /api/billing/status and GET /api/billing/invoices endpoints."),
          body("Knowledge Base Page (src/app/(dashboard)/knowledge/page.tsx): Build a knowledge base management interface with document list, upload functionality (PDF, DOCX, TXT), search, and category management. Show document processing status (pending/embedding/ready/error) and embedding statistics. Connect to backend GET /api/knowledge-base and POST /api/knowledge-base/upload endpoints."),
          body("AI Agents Page (src/app/(dashboard)/agents/page.tsx): Build an AI agent management interface showing all configured agents (Refund Agent, Technical Agent, Billing Agent, Complaint Agent, FAQ Agent), their current status, performance metrics (resolution rate, avg response time, customer satisfaction), and configuration controls. Connect to backend GET /api/ai-engine/agents endpoint."),

          h3("Day 4 Acceptance Criteria"),
          body("All 6 leftover items from Days 2-3 are resolved. The FAKE Voting system generates 3-5 candidates per query and selects the winner through adversarial LLM judging. Red-Flagging detects hallucinations and policy violations. The first 4 dashboard pages display real data from backend APIs with loading states and error handling. No more placeholder content on these pages."),

          // ── DAY 5 ──
          h2("3.2 Day 5: AI Frameworks + RAG + DSPy + Agent Lightning"),
          bodyBold("Theme: ", "Rebuild the higher-level AI systems that compose individual techniques into a complete customer care pipeline. This includes CLARA RAG, MAKER Framework full pipeline, DSPy integration, and Agent Lightning training."),
          bodyBold("Estimated Effort: ", "12-14 hours"),
          bodyBold("Dependencies: ", "Day 4 (FAKE Voting and dashboard infrastructure must be in place)"),

          h3("Day 5.1: CLARA RAG Rebuild (4 hours)"),
          body("[AI-14] Replace the current scoring wrapper in clara_quality_gate.py with actual advanced RAG capabilities. The CLARA (Contextual Learning and Retrieval Augmentation) system is PARWA's knowledge retrieval backbone and must implement three key features that are currently missing or stubbed."),
          body("HyDE (Hypothetical Document Embedding): When a customer query arrives, use the LLM to generate a hypothetical answer document. Embed this hypothetical document using the vector store and use it as the primary retrieval query. This technique improves retrieval quality because the hypothetical answer is semantically closer to relevant documents than the original question might be. Implement in backend/app/core/rag_retrieval.py as a new method generate_hyde_and_retrieve()."),
          body("Multi-Query Retrieval: Generate 3 alternative phrasings of the customer query using the LLM, then retrieve documents for all 4 queries (original + 3 alternatives). Merge and deduplicate the results, ranking by aggregate relevance score. This catches cases where the customer's phrasing doesn't match the knowledge base terminology. Implement as expand_query_multi() in rag_retrieval.py."),
          body("Contextual Compression: After initial retrieval, use the LLM to extract only the relevant portions from each retrieved document. Pass each document chunk + query pair to the LLM and ask it to identify and extract the specific sentences that answer the query. This reduces context window usage by 50-70% and improves response accuracy by eliminating noise. Implement in a new backend/app/core/rag_compression.py module."),

          h3("Day 5.2: MAKER Framework Full Pipeline (4 hours)"),
          body("[AI-15] The MAKER Framework (Maximal Agentic Decomposition + FAKE + Red-Flagging) should execute 6-24 LLM calls per query depending on complexity. Currently many LangGraph nodes are thin wrappers or pass-through implementations. Rebuild the full MAKER pipeline with real multi-LLM processing at each stage."),
          body("Map stage: Use the LLM to classify the query type (refund, technical, billing, complaint, FAQ, general) and determine which specialized agent should handle it. This classification drives the entire downstream pipeline. Node: 01_classifier."),
          body("Analyze stage: Run sentiment analysis and urgency detection using the LLM with structured output. Extract key entities (order numbers, product names, dates) using named entity recognition. This context flows into the agent selection and response generation. Node: 02_empathy_engine, 03_sentiment."),
          body("Knowledge stage: Execute CLARA RAG retrieval (HyDE + Multi-Query + Compression) to gather relevant documents from the knowledge base. Node: 04_base_domain_agent."),
          body("Evaluate stage: Run the FAKE Voting system (built on Day 4) to generate and evaluate K candidate responses. Apply Red-Flagging to detect and penalize problematic responses. Node: 11_maker_validator."),
          body("Refine stage: Take the winning response and apply final quality checks including PII redaction, brand voice enforcement, and channel-specific formatting. Nodes: 14_guardrails, 15_channel_delivery."),

          h3("Day 5.3: DSPy Integration + Agent Lightning (4-5 hours)"),
          body("[AI-12] Replace the current StubModule with actual DSPy integration. DSPy is a framework for programmatically optimizing language model prompts and weights. Implement: (1) A DSPy Signature for customer care responses that defines the input (query + context) and output (response) schema. (2) A DSPy Module that chains Chain of Thought and ReAct techniques into a composed pipeline. (3) DSPy Teleprompt optimization that uses example quality scoring to fine-tune the prompt selection. (4) Remove the try/except import guard that silently falls back to the stub. File: backend/app/core/dspy_integration.py."),
          body("[AI-13] Rebuild Agent Lightning, the weekly self-learning system that fine-tunes LLaMA-3-8B via Unsloth. The current implementation returns zero samples and null training job IDs. Implement: (1) prepare_dataset() must load real conversation logs from the tickets table, filter for high-quality interactions (customer satisfaction rating >= 4), and format them as supervised fine-tuning examples with instruction/response pairs. (2) schedule_training() must submit actual fine-tuning jobs to the configured provider API (OpenAI, Cerebras, or Groq) with proper parameters. (3) Implement a training job status monitor that polls the provider API and updates the database when training completes. (4) On completion, update the model configuration to route a percentage of traffic to the fine-tuned model. File: backend/app/tasks/training_tasks.py."),

          h3("Day 5.4: 3-Tier Hybrid Optimization (2 hours)"),
          body("[AI-16] Implement the 3-tier optimization engine that routes queries to genuinely different AI strategies based on the product variant. Tier 1 (Mini PARWA, $1K/mo) uses the fastest single technique (usually Chain of Thought) with minimal processing. Tier 2 (PARWA, $2.5K/mo) uses the best single technique based on intent classification (ReAct for technical, Self-Consistency for complex queries, etc.). Tier 3 (PARWA High, $4K/mo) uses the full MAKER multi-technique composition with FAKE Voting and Red-Flagging. The variant_capability_service.py already has the tier definitions; this work connects them to actual routing logic. Files: backend/app/core/technique_router.py, backend/app/core/variant_tier_mapper.py."),

          h3("Day 5 Acceptance Criteria"),
          body("CLARA RAG performs real HyDE generation, multi-query retrieval, and contextual compression on every knowledge base query. The MAKER Framework executes 6+ LLM calls per query through its multi-stage pipeline. DSPy integration uses actual DSPy Signatures and Modules with no StubModule fallback. Agent Lightning can load real conversation data and submit training jobs to a provider API. The 3-Tier system routes to genuinely different strategies per product variant."),

          // ── DAY 6 ──
          h2("3.3 Day 6: Security HIGH + Socket.io + Dashboard Pages Batch 2"),
          bodyBold("Theme: ", "Address the 22 HIGH severity security findings, implement Socket.io real-time frontend integration, and complete the remaining 3 dashboard pages."),
          bodyBold("Estimated Effort: ", "12-14 hours"),
          bodyBold("Dependencies: ", "Days 4-5 (AI frameworks must be functional before securing their endpoints)"),

          h3("Day 6.1: Middleware and Access Control (3 hours)"),
          body("[H-01] Open Redirect on Login Page: Validate the redirect query parameter against a whitelist of allowed paths. The current isSafeRedirect() function blocks basic patterns but should also enforce that redirect URLs start with a single forward slash and contain no double-encoding tricks. File: src/lib/auth-cookies.ts."),
          body("[H-04] Content-Security-Policy Header: Add a comprehensive CSP header to the security headers middleware. Policy must include: default-src 'self', script-src 'self' 'nonce-{random}', style-src 'self' 'unsafe-inline' (required for Tailwind CSS runtime), img-src 'self' data: https:, connect-src 'self' https://api.cerebras.ai https://api.groq.com. Generate a fresh nonce per request. File: backend/app/middleware/security_headers.py."),
          body("[H-06] IP Extraction Inconsistency: Standardize IP extraction across all middleware using a shared get_client_ip() utility that respects TRUSTED_PROXY_COUNT. Currently ip_allowlist.py, request_logger.py, and rate_limit.py each extract IPs differently, which causes inconsistent rate limiting and allowlisting behavior. Create a shared utility in backend/app/core/utils.py."),
          body("[H-13] Billing Role Restrictions: Add role checks to all billing endpoints. Only users with 'owner' or 'admin' roles should be able to cancel subscriptions, process refunds, or modify billing details. Currently any authenticated user can access these endpoints. File: backend/app/api/billing.py."),
          body("[H-21] Auth Endpoint Rate Limiting: Add application-level rate limiting on all /api/auth/* routes using Redis sliding window. Login: 5 attempts per minute per email. Register: 3 per minute per IP. OTP: 10 per minute per phone. Password Reset: 3 per hour per email. File: backend/app/middleware/rate_limit.py."),

          h3("Day 6.2: Webhook and CSRF Security (3 hours)"),
          body("[H-07] Webhook Signature Verification: Change the webhook handler logic from 'if webhook_secret and not verify' to 'if not webhook_secret: reject request.' Missing webhook secrets must cause request rejection, not silent acceptance. File: backend/app/api/billing_webhooks.py."),
          body("[H-08] Webhook Replay Protection: Add timestamp validation to all webhook handlers (Paddle, Twilio, Brevo, Shopify). Reject any webhook with a timestamp older than 5 minutes. Store processed webhook IDs in Redis with TTL to prevent replay attacks. Files: backend/app/webhooks/paddle_handler.py, twilio_handler.py, brevo_handler.py, shopify_handler.py."),
          body("[H-19] CSRF Protection: Implement CSRF token generation and validation for all POST/PUT/DELETE routes that use cookie-based authentication. Generate tokens server-side, store in httpOnly cookies, and validate on every state-changing request. For Bearer token auth, CSRF is less critical but should still be enforced for cookie-based auth endpoints."),
          body("[H-20] Mock Login in Production: Remove or disable the mock login endpoint in production environments. Gate it behind ENVIRONMENT != 'production' with a clear development-only marker. File: dashboard/src/app/api/auth/login/route.ts."),

          h3("Day 6.3: Socket.io Frontend Integration (3-4 hours)"),
          body("[GAP-4] The backend has a full Socket.io event system implemented (real-time ticket updates, typing indicators, agent status changes, new message notifications) but the frontend has zero Socket.io client code. This means the dashboard cannot receive real-time updates and must poll for new data."),
          body("Implementation plan: (1) Install socket.io-client in the frontend. (2) Create a shared useSocket hook in src/hooks/useSocket.ts that manages connection lifecycle, reconnection, and event subscription. (3) Integrate real-time updates into the Tickets page: new ticket notifications, status change events, and typing indicators. (4) Add real-time agent status indicators to the AI Agents page. (5) Implement real-time notification toasts for critical events (escalation, SLA breach, new high-priority ticket). (6) Add Socket.io authentication using the JWT token from httpOnly cookies. Files: src/hooks/useSocket.ts (new), src/lib/socket.ts (new), dashboard components."),

          h3("Day 6.4: Dashboard Pages - Batch 2 (3 hours)"),
          body("Settings Page (src/app/(dashboard)/settings/page.tsx): Build a settings interface with tabs for Company Profile, Team Management (invite/remove users, role assignment), API Keys (generate/revoke), Channel Configuration (email, SMS, chat widget, voice), Notification Preferences, and Security Settings (2FA, session management). Connect to backend settings APIs."),
          body("Monitoring Page (src/app/(dashboard)/monitoring/page.tsx): Build a real-time monitoring dashboard showing AI pipeline health, LLM provider status (latency, error rates, fallback frequency), active conversations count, queue depths, and token usage trends. Use charts for time-series data. Connect to backend monitoring APIs and Socket.io events."),
          body("Variants Page (src/app/(dashboard)/variants/page.tsx): Build a variant management interface showing the 3 product tiers (Mini PARWA, PARWA, PARWA High) with their feature matrices, usage limits, and current utilization. Include an upgrade flow and feature comparison table. Connect to backend variant capability APIs."),

          h3("Day 6 Acceptance Criteria"),
          body("All 22 HIGH severity findings are resolved. CSP header is active. IP extraction is consistent. Webhook handlers reject replayed requests and missing secrets. CSRF tokens are validated. Rate limiting is active on all auth endpoints. Socket.io provides real-time updates across all dashboard pages. All 7 dashboard pages display real data with loading and error states."),

          // ── DAY 7 ──
          h2("3.4 Day 7: Security MEDIUM + Incomplete Features"),
          bodyBold("Theme: ", "Fix MEDIUM severity security issues and complete partially-implemented features including voice server, sentiment analysis, confidence scoring, PII redaction, and hallucination detection."),
          bodyBold("Estimated Effort: ", "10-12 hours"),

          h3("Day 7.1: Security MEDIUM Fixes (5 hours)"),
          body("[M-01] Remove user_role from AuthorizationError details. Return only generic 'access denied' without revealing the user's actual role. File: backend/app/api/deps.py."),
          body("[M-04] Replace simple '@' email validation with proper RFC 5322 validation using the email-validator Python package. File: backend/app/api/verification.py."),
          body("[M-05] Change rate limiter to fail-closed: when Redis is down, block requests rather than allowing all through. Log the Redis failure clearly. File: backend/app/middleware/rate_limit.py."),
          body("[M-33] Escape % and _ characters in search queries before passing to ILIKE operations to prevent SQL wildcard injection. Files: backend/app/api/admin.py, tickets.py."),
          body("[M-16] Add Pydantic models for all ai_engine endpoints that currently accept raw dict bodies. This prevents mass assignment and ensures type safety. File: backend/app/api/ai_engine.py."),
          body("[M-26] Add security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP) directly to Next.js API routes via middleware. File: src/middleware.ts."),
          body("[M-28] Sanitize email content before passing to Brevo API. Use a proper HTML escaping library to prevent phishing vectors. File: dashboard/src/app/api/send-email/route.ts."),
          body("[D-01] Fix the notification service that sends SMS to hardcoded +1234567890 instead of the actual customer phone number. Route SMS through the backend API. File: dashboard/src/lib/notifications.ts."),
          body("[D-02] Connect dashboard analytics to real backend APIs. The current analytics-api.ts silently returns mock data. File: dashboard/src/lib/analytics-api.ts."),

          h3("Day 7.2: Incomplete Feature Completion (5-6 hours)"),
          body("[IC-01] Voice Server - Replace Keyword Matching with LLM: The parwa_voice_server.py currently uses keyword-based intent detection. Replace with real LLM-based intent classification using the Smart Router. Maintain the existing Twilio call handling infrastructure. File: backend/app/core/parwa_voice_server.py."),
          body("[IC-02] Sentiment Analysis - Replace Keywords with NLP: Replace keyword-based sentiment analysis with real LLM-powered analysis producing structured output (sentiment_score: 0-1, emotion_labels: [], urgency_level: low/medium/high/critical). File: backend/app/core/sentiment_engine.py."),
          body("[IC-09] PII Redaction - Add NER-Based Detection: Extend PII redaction beyond regex patterns to include LLM-based named entity recognition for person names, addresses, and custom entity types. Use the LLM for ambiguous cases where regex patterns may miss or over-match. File: backend/app/core/pii_redaction_engine.py."),
          body("[IC-11] Hallucination Detector - Real Implementation: Implement actual hallucination detection that cross-checks AI responses against knowledge base facts, verifies numerical claims and order details against real data, and flags responses where the AI states something not supported by the knowledge base or conversation context. File: backend/app/core/hallucination_detector.py."),
          body("[BUG-4] Jarvis Sessions Persistence: Currently Jarvis sessions are stored in-memory using a Map(), meaning all conversation history is lost on server restart. Migrate to Redis-backed session storage with TTL and persistence. File: backend/app/services/jarvis_service.py."),

          h3("Day 7 Acceptance Criteria"),
          body("All targeted MEDIUM security issues are resolved. Input validation uses proper libraries. Rate limiter fails closed on Redis failure. SQL wildcards are escaped. Voice server uses real LLM intent classification. Sentiment analysis produces structured NLP output. PII redaction uses NER for entity detection. Hallucination detector cross-checks responses against facts. Jarvis sessions persist across server restarts."),

          // ── DAY 8 ──
          h2("3.5 Day 8: AI Pipeline + LangGraph Full Completion"),
          bodyBold("Theme: ", "Complete all 19 LangGraph nodes by connecting them to real implementations, building specialized agent nodes, and validating end-to-end AI pipeline quality."),
          bodyBold("Estimated Effort: ", "12-14 hours"),
          bodyBold("Dependencies: ", "Day 5 (AI frameworks and RAG must be working)"),

          h3("Day 8.1: Core LangGraph Node Completion (6 hours)"),
          body("[LG-01] Node 02 - Empathy Engine: Implement real empathy detection using the LLM. Analyze customer emotional state from their message text (anger, frustration, confusion, satisfaction, urgency) and adjust response tone accordingly. Map emotional states to response tone parameters that flow into downstream nodes. File: backend/app/core/langgraph/nodes/02_empathy_engine.py."),
          body("[LG-02] Node 04 - Base Domain Agent: Connect to CLARA RAG for knowledge retrieval and use the appropriate AI technique (selected by the technique router) for response generation. This is the primary response generation node and must produce high-quality, contextually relevant responses. File: backend/app/core/langgraph/nodes/04_base_domain_agent.py."),
          body("[LG-04] Node 12 - Control System: Implement the Jarvis Control System node that monitors AI response quality and can override or escalate. Check response accuracy against knowledge base, policy compliance, tone appropriateness, and PII leakage. If quality score is below threshold, route back for regeneration or escalate to human agent. File: backend/app/core/langgraph/nodes/12_control_system.py."),
          body("[LG-06] Node 14 - Guardrails: Implement real output guardrails that block harmful content, enforce brand voice guidelines, check for off-topic responses, verify response length constraints, and ensure regulatory compliance. File: backend/app/core/langgraph/nodes/14_guardrails.py."),
          body("[LG-07] Node 15 - Channel Delivery: Implement channel-specific response formatting: truncate for SMS (160 chars), format HTML for email, add TTS markup for voice, include quick-reply buttons for chat widget, and apply channel-appropriate tone adjustments. File: backend/app/core/langgraph/nodes/15_channel_delivery.py."),

          h3("Day 8.2: Specialized Agent Nodes (4 hours)"),
          body("[LG-08] Node 06 - Refund Agent: Connect to the Paddle payment provider API for real refund processing. Agent should verify refund eligibility by checking order status and refund policy, calculate refund amounts including pro-rations, and initiate refunds through the billing system. File: backend/app/core/langgraph/nodes/06_refund_agent.py."),
          body("[LG-09] Node 07 - Technical Agent: Implement technical support with real diagnostic capabilities. Use the ReAct technique with diagnostic tools to check service health, search knowledge base for known issues, and guide customers through troubleshooting steps. File: backend/app/core/langgraph/nodes/07_technical_agent.py."),
          body("[LG-10] Node 08 - Billing Agent: Connect to the real billing system. Handle subscription queries, invoice lookups, payment troubleshooting, plan changes, and credit applications through the Paddle integration. File: backend/app/core/langgraph/nodes/08_billing_agent.py."),
          body("[LG-11] Node 09 - Complaint Agent: Implement complaint handling with emotional intelligence. Use sentiment analysis to detect frustration levels, apply service recovery playbooks (apology + resolution + compensation), and escalate to human agents when complaint severity exceeds AI confidence threshold. File: backend/app/core/langgraph/nodes/09_complaint_agent.py."),
          body("[LG-12] Node 10 - Escalation Agent: Implement proper escalation logic. Determine when to escalate based on topic complexity, sentiment severity, and AI confidence score. Route to the correct human agent queue with full conversation context transfer including AI reasoning summary. File: backend/app/core/langgraph/nodes/10_escalation_agent.py."),

          h3("Day 8.3: End-to-End Pipeline Validation (2 hours)"),
          body("Create a comprehensive integration test that sends a realistic customer complaint through the full 19-node LangGraph pipeline. Verify that real LLM calls occur at each relevant node, that the response passes through guardrails, that the empathy engine adjusts tone, and that the final output is properly formatted for the target channel. Test with all 4 verticals (E-Commerce, SaaS, Logistics, Healthcare) and all 3 variant tiers. File: backend/app/tests/test_e2e_pipeline.py."),

          h3("Day 8 Acceptance Criteria"),
          body("All 19 LangGraph nodes perform real processing with no pass-through stubs. The empathy engine adjusts response tone based on detected emotion. Domain agents use CLARA RAG for knowledge retrieval. Guardrails block harmful and off-topic responses. Channel delivery formats correctly for each channel. Specialized agents connect to real backend services. End-to-end pipeline test passes for all verticals and tiers."),

          // ── DAY 9 ──
          h2("3.6 Day 9: Infrastructure + Production Hardening + Critical Bugs"),
          bodyBold("Theme: ", "Harden infrastructure for production deployment, implement Row Level Security, and fix the remaining critical database and infrastructure bugs."),
          bodyBold("Estimated Effort: ", "10-12 hours"),

          h3("Day 9.1: Critical Database Bug Fixes (3-4 hours)"),
          body("[BUG-1] Migration Chain Break: Alembic migrations 003 and 005 reference sessions.id as a foreign key, but the sessions table was renamed to tickets (BL01) without updating the migration files. This means a fresh database deployment WILL FAIL. Fix by creating a new migration that correctly references the tickets table and its columns, ensuring both forward migration and rollback work cleanly. Test by running alembic upgrade head on a fresh database. Files: database/alembic/versions/."),
          body("[BUG-2] UUID Type Inconsistency: The OutboundEmail and EmailDeliveryEvent models use UUID(as_uuid=True) for their id columns (PostgreSQL native UUID type), while all other 95 models use String(36). This inconsistency causes foreign key reference failures when other tables try to reference these UUID columns. Standardize all id columns to String(36) for consistency, or migrate all models to UUID. Given that 95 models use String(36), the lower-risk approach is to convert the 2 outlier models. File: database/models/core.py."),
          body("[BUG-3] Route Prefix Mismatch: The variant_check.py middleware checks for /api/v1/tickets but the tickets.py router uses the prefix /tickets (without /api/v1). This means variant resource limits are never enforced for ticket endpoints. Fix by aligning the prefix in variant_check.py with the actual router prefix, or by adding the /api/v1 prefix to the tickets router. Files: backend/app/middleware/variant_check.py, backend/app/api/tickets.py."),

          h3("Day 9.2: Row Level Security (RLS) (3 hours)"),
          body("[GAP-5] Implement PostgreSQL Row Level Security policies as a defense-in-depth measure alongside the application-level tenant isolation. Even though the SQLAlchemy tenant middleware correctly filters queries by company_id, RLS provides database-level enforcement that protects against any application-level bypass (SQL injection, ORM bypass, direct database access)."),
          body("Implementation plan: (1) Create an Alembic migration that enables RLS on all tenant-scoped tables (93 out of 97 tables have company_id). (2) For each table, create a policy that restricts SELECT, UPDATE, INSERT, and DELETE operations to rows where company_id matches the current database user's company. (3) Implement a function that extracts the company_id from the JWT token passed as a PostgreSQL session variable (SET app.current_company_id). (4) Apply this function as the USING clause in all RLS policies. (5) Ensure the RLS bypass role (for migrations and admin operations) is restricted. File: database/alembic/versions/ (new migration)."),

          h3("Day 9.3: Production Infrastructure (3-4 hours)"),
          body("[L-01] Migrate JWT signing from HS256 (symmetric) to RS256 (asymmetric) to allow frontend token verification without sharing the signing key. Generate RSA key pair and configure both backend signing and frontend verification. File: backend/app/core/auth.py."),
          body("[INF-01] Production Docker Security: Ensure all production containers run as non-root users, remove unnecessary system packages, set CPU and memory resource limits, enable read-only root filesystem where possible, and configure health checks for all services. Files: infra/docker/*.Dockerfile, docker-compose.yml."),
          body("[INF-02] Environment Variable Audit: Create a comprehensive .env.production.template with all required variables, descriptions, and examples. Ensure no hardcoded values in any source file. Add startup validation that checks all required env vars are set. File: backend/app/config.py."),
          body("[BUG-5] Smart Router HealthTracker: The HealthTracker that monitors LLM provider health is stored in-memory and won't work across multiple Celery workers. Migrate to Redis-backed state with TTL and atomic updates. File: backend/app/core/smart_router.py."),
          body("[BUG-6] MockVectorStore Default: The RAG system uses MockVectorStore with SHA-256 pseudo-embeddings by default unless PostgreSQL+pgvector is configured. Add a production startup check that warns if MockVectorStore is active, and document the pgvector setup procedure. File: backend/app/core/rag_retrieval.py."),

          h3("Day 9 Acceptance Criteria"),
          body("All 3 critical database bugs are fixed. Fresh database deployment succeeds with alembic upgrade head. UUID types are consistent across all models. Variant limits enforce correctly on ticket endpoints. RLS policies are active on all tenant-scoped tables. Production Docker containers run as non-root with resource limits. Environment variables are validated on startup. Smart Router health tracking works across Celery workers."),

          // ── DAY 10 ──
          h2("3.7 Day 10: 25 Loophole Solutions + Testing + Documentation"),
          bodyBold("Theme: ", "Build the 25 Loophole Solutions safety module, run comprehensive regression testing, and update all documentation to reflect real system capabilities."),
          bodyBold("Estimated Effort: ", "12-14 hours"),

          h3("Day 10.1: 25 Loophole Solutions Module (5-6 hours)"),
          body("[GAP-6] The DMD describes 25 structured loophole solutions as a comprehensive safety framework that prevents AI agents from finding and exploiting loopholes in customer care policies. This module currently has no dedicated implementation in the codebase. Build a LoopholeDetectionEngine that runs alongside the guardrails system."),
          body("Implementation plan: (1) Define the 25 loophole categories as an enum in backend/app/core/loophole_types.py. Categories include: freebie exploitation (customer repeatedly claims free replacements), policy boundary confusion (agent misinterprets policy limits), circular logic traps (agent gets stuck in reasoning loops), empathy manipulation (customer uses emotional language to bypass rules), and 21 others from the DMD specification. (2) Implement a detection engine in backend/app/core/loophole_engine.py that scans AI responses for loophole patterns using both rule-based checks and LLM-based analysis. (3) Integrate the loophole engine into the LangGraph guardrails node (14_guardrails.py) so every response is checked before delivery. (4) Implement counter-measures for each detected loophole type (response modification, escalation, flagging). (5) Add loophole detection metrics to the monitoring dashboard. Files: backend/app/core/loophole_types.py (new), backend/app/core/loophole_engine.py (new)."),

          h3("Day 10.2: Comprehensive Regression Testing (3-4 hours)"),
          body("[TEST-01] Run the full existing test suite: pytest backend/app/tests/ with coverage reporting. Fix any failing tests. Ensure test coverage is at least 80% for all modified files."),
          body("[TEST-02] Write targeted verification tests for all items fixed during Days 4-10. Each test should verify the specific fix is effective and no regression was introduced. Create: backend/app/tests/test_days4_10_verification.py."),
          body("[TEST-03] AI technique integration tests: Verify each of the 12 techniques makes real LLM calls. Mock LLM responses for deterministic testing but verify call structure, prompt format, and response parsing. Create: backend/app/tests/test_ai_techniques_real.py."),
          body("[TEST-04] End-to-end pipeline test: Send a customer query through the full 19-node pipeline and verify real LLM calls at each stage, proper guardrail enforcement, and correct channel formatting. Create: backend/app/tests/test_e2e_full.py."),
          body("[TEST-05] Load testing: Simulate 50 concurrent customer conversations. Verify no connection pool exhaustion, no memory leaks, consistent response times, and proper rate limiting under load."),

          h3("Day 10.3: Documentation Update (3 hours)"),
          body("[DOC-01] Update the PARWA Architecture Design Document to reflect the real AI architecture. Remove any claims about capabilities that were not actually implemented. Document the actual LLM integration architecture through llm_gateway.py, the real CLARA RAG capabilities (HyDE, Multi-Query, Compression), and the MAKER Framework's actual pipeline stages with FAKE Voting."),
          body("[DOC-02] Audit all documents in the /documents/ and /docs/ directories. Update or remove any claims about AI capabilities that don't match the actual implementation. Ensure the documentation accurately describes the LLM-first with template fallback architecture, not the 'pure regex' characterization from the original roadmap."),
          body("[DOC-03] Create a production deployment runbook including: environment setup, database migration procedure, Docker deployment steps, SSL certificate installation, monitoring configuration, and rollback procedures."),

          h3("Day 10 Acceptance Criteria"),
          body("The 25 Loophole Solutions module detects and counters all 25 defined loophole categories. All existing tests pass with no regressions. New verification tests cover all Days 4-10 fixes. AI technique tests confirm real LLM integration. End-to-end pipeline test passes. Load test shows stable performance under 50 concurrent conversations. All documentation accurately describes real system capabilities."),

          // ═══════════════════════════════════════════
          // SECTION 4: GAP MAPPING
          // ═══════════════════════════════════════════
          h1("4. Complete Gap-to-Day Mapping"),
          body("The following table maps every identified gap to its assigned day, source audit, and dependency chain. Items marked with an asterisk (*) are additions from the independent code audit that were not in the original 10-Day roadmap."),
          makeTable(
            ["Day", "Gap ID", "Category", "Description"],
            [
              ["4", "C-07", "Security", ".env.prod still tracked in git"],
              ["4", "C-15", "Security", "Empty dev pepper fallback"],
              ["4", "C-14", "Security", "Fernet vs AES-256-GCM decision"],
              ["4", "H-09", "Security", "Pricing key hardcoded fallback"],
              ["4", "AI-F01", "AI Foundation", "LLM client path mismatch"],
              ["4", "AI-F02", "AI Foundation", "Missing execute_with_llm()"],
              ["4", "*GAP-2", "AI Framework", "FAKE Voting system for MAKER"],
              ["4", "*GAP-3a", "Frontend", "Dashboard: Tickets page"],
              ["4", "*GAP-3b", "Frontend", "Dashboard: Billing page"],
              ["4", "*GAP-3c", "Frontend", "Dashboard: Knowledge Base page"],
              ["4", "*GAP-3d", "Frontend", "Dashboard: AI Agents page"],
              ["5", "AI-14", "AI RAG", "CLARA RAG: HyDE + Multi-Query + Compression"],
              ["5", "AI-15", "AI Framework", "MAKER full pipeline (6-24 LLM calls)"],
              ["5", "AI-12", "AI DSPy", "Real DSPy integration (no StubModule)"],
              ["5", "*GAP-1", "AI Training", "Agent Lightning real training pipeline"],
              ["5", "AI-16", "AI Routing", "3-Tier Hybrid optimization"],
              ["6", "H-01/04/06", "Security HIGH", "Middleware + CSP + IP + Rate Limit"],
              ["6", "H-07/08/19/20", "Security HIGH", "Webhook + CSRF + Mock login"],
              ["6", "*GAP-4", "Real-time", "Socket.io frontend integration"],
              ["6", "*GAP-3e", "Frontend", "Dashboard: Settings page"],
              ["6", "*GAP-3f", "Frontend", "Dashboard: Monitoring page"],
              ["6", "*GAP-3g", "Frontend", "Dashboard: Variants page"],
              ["7", "M-xx (9 items)", "Security MED", "9 MEDIUM security fixes"],
              ["7", "IC-01/02/09/11", "Incomplete", "Voice + Sentiment + PII + Hallucination"],
              ["7", "*BUG-4", "Bug", "Jarvis sessions in-memory only"],
              ["8", "LG-01 through LG-12", "LangGraph", "All 19 node implementations"],
              ["8", "TEST-04", "Testing", "End-to-end pipeline validation"],
              ["9", "*BUG-1", "Critical Bug", "Migration chain break"],
              ["9", "*BUG-2", "Critical Bug", "UUID type inconsistency"],
              ["9", "*BUG-3", "Critical Bug", "Route prefix mismatch"],
              ["9", "*GAP-5", "Security", "Row Level Security (RLS)"],
              ["9", "L-01 + INF-01/02", "Infra", "JWT RS256 + Docker + Env vars"],
              ["9", "*BUG-5", "Bug", "Smart Router HealthTracker state"],
              ["9", "*BUG-6", "Bug", "MockVectorStore default warning"],
              ["10", "*GAP-6", "Safety", "25 Loophole Solutions module"],
              ["10", "TEST-01/02/03/05", "Testing", "Full regression test suite"],
              ["10", "DOC-01/02/03", "Documentation", "Architecture + marketing docs + runbook"],
            ],
            [6, 14, 16, 64]
          ),
          new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }),

          // ═══════════════════════════════════════════
          // SECTION 5: EFFORT SUMMARY
          // ═══════════════════════════════════════════
          h1("5. Effort Summary and Risk Assessment"),
          body("The total estimated effort for Days 4-10 is approximately 78-96 hours. This is a significant undertaking that requires disciplined execution and scope management. The following table summarizes the estimated effort per day, the primary risk areas, and the key dependencies that must be satisfied before each day can begin."),
          makeTable(
            ["Day", "Hours", "Primary Risk", "Key Dependencies"],
            [
              ["Day 4", "10-12", "FAKE Voting prompt engineering quality", "Days 1-3 verified"],
              ["Day 5", "12-14", "DSPy integration complexity; training API differences", "Day 4 complete"],
              ["Day 6", "12-14", "Socket.io auth with httpOnly cookies", "Days 4-5 complete"],
              ["Day 7", "10-12", "Voice server Twilio integration edge cases", "Day 6 complete"],
              ["Day 8", "12-14", "LangGraph node interdependencies", "Day 5 complete"],
              ["Day 9", "10-12", "Migration breakage on fresh DB; RLS performance", "Day 8 complete"],
              ["Day 10", "12-14", "Loophole detection accuracy; test coverage", "Days 4-9 complete"],
              ["TOTAL", "78-92", "", ""],
            ],
            [10, 12, 38, 40]
          ),
          new Paragraph({ spacing: { before: 80, after: 80 }, children: [] }),

          h2("5.1 Primary Risks and Mitigations"),
          body("Scope Creep Risk: Each fix may reveal additional issues. Mitigation: Each day has clear acceptance criteria and strict scope boundaries. If a fix takes longer than estimated, defer lower-priority items to a buffer day rather than cascading delays into subsequent days."),
          body("AI Quality Risk: The FAKE Voting system and loophole detection engine require careful prompt engineering. Poorly implemented voting could produce worse results than single-response generation. Mitigation: Each system includes structured output parsing and quality validation. The Day 10 regression tests will catch quality regressions."),
          body("Dependency Chain Risk: Day 5 (AI frameworks) depends on Day 4 (FAKE Voting). Day 8 (LangGraph) depends on Day 5 (RAG + MAKER). A delay in any day cascades forward. Mitigation: Implement items in priority order within each day. The most critical items should be completed first, allowing subsequent days to begin even if lower-priority items are still in progress."),
          body("Database Migration Risk: Fixing the migration chain break (BUG-1) is high-risk because it involves modifying historical migrations. A mistake could corrupt the migration history. Mitigation: Create a new migration that corrects the FK references without modifying existing migration files. Test on a fresh database before applying to any environment with data."),

          h2("5.2 Daily Git Workflow"),
          body("As requested, the daily git workflow must be followed strictly throughout the execution phase. At the start of each work session, pull the latest code from the remote repository to incorporate any parallel changes. After completing the day's work, create a feature branch for the day's changes, commit with a descriptive message referencing the specific gap IDs addressed, push the branch, and create a pull request for review before merging into the main branch. This ensures clean separation of changes and enables easy rollback if any day's work introduces issues."),
          body("The workflow for each day: (1) git pull origin main, (2) git checkout -b day-N-fixes, (3) Implement all items for the day, (4) git add . && git commit -m 'Day N: [gap IDs] description', (5) git push origin day-N-fixes, (6) Create PR and merge after verification."),

          // ═══════════════════════════════════════════
          // SECTION 6: SUCCESS METRICS
          // ═══════════════════════════════════════════
          h1("6. Success Metrics"),
          body("The roadmap will be considered successful when the following metrics are achieved at the end of Day 10. These metrics cover security posture, AI capability, frontend completeness, infrastructure readiness, and documentation accuracy. Each metric is measurable and can be verified through automated testing or manual inspection."),
          bullet("Zero CRITICAL vulnerabilities remain in the codebase (currently 1 remaining from Day 2: C-07)."),
          bullet("Zero HIGH vulnerabilities remain unaddressed (all 22 from the original audit must be resolved by Day 6)."),
          bullet("At minimum 80% of MEDIUM findings are resolved (currently targeting 15 of 39 by Day 7)."),
          bullet("All 12 AI techniques make real LLM API calls with measurable quality metrics (VERIFIED by Day 3 cross-check)."),
          bullet("CLARA RAG performs HyDE, multi-query retrieval, and contextual compression (Day 5)."),
          bullet("MAKER Framework executes 6+ LLM calls per query with FAKE Voting (Day 5)."),
          bullet("Agent Lightning can load real conversation data and submit training jobs (Day 5)."),
          bullet("All 19 LangGraph nodes perform real processing with no pass-through stubs (Day 8)."),
          bullet("All 7 dashboard pages display real data from backend APIs (Days 4 and 6)."),
          bullet("Socket.io provides real-time updates across all dashboard pages (Day 6)."),
          bullet("Row Level Security is active on all 93 tenant-scoped tables (Day 9)."),
          bullet("25 Loophole Solutions module detects and counters all defined loophole categories (Day 10)."),
          bullet("Fresh database deployment succeeds with alembic upgrade head (Day 9)."),
          bullet("Full test suite passes with no regressions and minimum 80% code coverage on modified files (Day 10)."),
          bullet("All documentation accurately describes real system capabilities (Day 10)."),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync("/home/z/my-project/download/PARWA_10Day_Merged_Roadmap.docx", buffer);
  console.log("Document generated successfully!");
}

main().catch(console.error);
