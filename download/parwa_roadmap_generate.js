const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  PageBreak, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, WidthType, BorderStyle, ShadingType,
  TableOfContents, LevelFormat,
} = require("docx");

// ═══════════════════════════════════════════════════════════════
// PALETTE — DM-1 Deep Cyan (Tech / AI / Digital)
// ═══════════════════════════════════════════════════════════════
const P = {
  primary: "162235", body: "000000", secondary: "5A6080",
  accent: "D4875A", surface: "F8F0EB",
  cover: { bg: "1A2330", titleColor: "FFFFFF", subtitleColor: "B0B8C0", metaColor: "90989F", footerColor: "687078" },
  table: { headerBg: "D4875A", headerText: "FFFFFF", accentLine: "D4875A", innerLine: "DDD0C8", surface: "F8F0EB" },
};
const c = (hex) => (hex || "").replace("#", "");

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: NB, bottom: NB, left: NB, right: NB };
const allNoBorders = { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: NB, insideVertical: NB };

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 360 : 240, after: 120 },
    children: [new TextRun({ text, bold: true, color: c(P.primary), font: { ascii: "Calibri", eastAsia: "Calibri" } })],
  });
}

function h2(text) { return heading(text, HeadingLevel.HEADING_2); }
function h3(text) { return heading(text, HeadingLevel.HEADING_3); }

function body(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 80 },
    children: [new TextRun({ text, size: 24, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Calibri" } })],
  });
}

function bodyBold(label, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 80 },
    children: [
      new TextRun({ text: label, bold: true, size: 24, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Calibri" } }),
      new TextRun({ text, size: 24, color: c(P.body), font: { ascii: "Calibri", eastAsia: "Calibri" } }),
    ],
  });
}

// ═══════════════════════════════════════════════════════════════
// TABLE BUILDER
// ═══════════════════════════════════════════════════════════════
function makeTable(headers, rows) {
  const colWidth = Math.floor(100 / headers.length);
  const headerRow = new TableRow({
    tableHeader: true, cantSplit: true,
    children: headers.map(text => new TableCell({
      width: { size: colWidth, type: WidthType.PERCENTAGE },
      shading: { type: ShadingType.CLEAR, fill: P.table.headerBg },
      borders: { top: NB, bottom: { style: BorderStyle.SINGLE, size: 2, color: P.table.accentLine }, left: NB, right: NB },
      margins: { top: 60, bottom: 60, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 21, color: c(P.table.headerText), font: { ascii: "Calibri" } })] })],
    })),
  });
  const dataRows = rows.map((cells, i) => new TableRow({
    cantSplit: true,
    children: cells.map(text => new TableCell({
      width: { size: colWidth, type: WidthType.PERCENTAGE },
      shading: i % 2 === 0 ? { type: ShadingType.CLEAR, fill: P.table.surface } : { type: ShadingType.CLEAR, fill: "FFFFFF" },
      borders: { top: NB, bottom: NB, left: NB, right: NB, insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: P.table.innerLine } },
      margins: { top: 60, bottom: 60, left: 120, right: 120 },
      children: [new Paragraph({ spacing: { line: 280 }, children: [new TextRun({ text, size: 21, color: c(P.body), font: { ascii: "Calibri" } })] })],
    })),
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { top: { style: BorderStyle.SINGLE, size: 2, color: P.table.accentLine }, bottom: { style: BorderStyle.SINGLE, size: 2, color: P.table.accentLine }, left: NB, right: NB, insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: P.table.innerLine }, insideVertical: NB },
    rows: [headerRow, ...dataRows],
  });
}

// ═══════════════════════════════════════════════════════════════
// COVER — R4 Top Color Block with GO-1 Graphite Orange palette
// ═══════════════════════════════════════════════════════════════
function buildCover() {
  return new Table({
    borders: allNoBorders,
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({
      height: { value: 16838, rule: "exact" },
      verticalAlign: "top",
      children: [new TableCell({
        width: { size: 100, type: WidthType.PERCENTAGE },
        shading: { type: ShadingType.CLEAR, fill: P.cover.bg },
        borders: allNoBorders,
        margins: { top: 0, bottom: 0, left: 0, right: 0 },
        children: [
          new Paragraph({ spacing: { before: 4800 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            children: [new TextRun({ text: "PARWA", size: 72, bold: true, color: c(P.cover.titleColor), font: { ascii: "Calibri" } })] }),
          new Paragraph({ spacing: { before: 80 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            children: [new TextRun({ text: "Production Readiness Roadmap", size: 40, color: c(P.cover.accent), font: { ascii: "Calibri" } })] }),
          new Paragraph({ spacing: { before: 400 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            border: { top: { style: BorderStyle.SINGLE, size: 6, color: c(P.accent), space: 12 } }, children: [] }),
          new Paragraph({ spacing: { before: 300 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            children: [new TextRun({ text: "Bridging the 30% Gap: Critical Bugs, Missing Features &", size: 22, color: c(P.cover.subtitleColor), font: { ascii: "Calibri" } })] }),
          new Paragraph({ spacing: { before: 40 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            children: [new TextRun({ text: "Full Frontend Dashboard to Achieve Production Launch", size: 22, color: c(P.cover.subtitleColor), font: { ascii: "Calibri" } })] }),
          new Paragraph({ spacing: { before: 2000 }, alignment: AlignmentType.LEFT, indent: { left: 1200 },
            children: [new TextRun({ text: "Version 1.0  |  May 2025  |  Confidential", size: 18, color: c(P.cover.footerColor), font: { ascii: "Calibri" } })] }),
        ],
      })],
    })],
  });
}

// ═══════════════════════════════════════════════════════════════
// DOCUMENT
// ═══════════════════════════════════════════════════════════════
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Calibri", eastAsia: "Calibri" }, size: 24, color: c(P.body) },
        paragraph: { spacing: { line: 312 } },
      },
      heading1: { run: { font: { ascii: "Calibri" }, size: 32, bold: true, color: c(P.primary) }, paragraph: { spacing: { before: 360, after: 160, line: 312 } } },
      heading2: { run: { font: { ascii: "Calibri" }, size: 28, bold: true, color: c(P.primary) }, paragraph: { spacing: { before: 240, after: 120, line: 312 } } },
      heading3: { run: { font: { ascii: "Calibri" }, size: 24, bold: true, color: c(P.primary) }, paragraph: { spacing: { before: 200, after: 100, line: 312 } } },
    },
  },
  numbering: {
    config: [
      { reference: "phase-list", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "Phase %1", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "task-list", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  sections: [
    // ── SECTION 1: COVER ──
    { properties: { page: { margin: { top: 0, bottom: 0, left: 0, right: 0 }, size: { width: 11906, height: 16838 } } }, children: [buildCover()] },

    // ── SECTION 2: TOC ──
    {
      properties: { page: { pageNumbers: { start: 1, formatType: NumberFormat.UPPER_ROMAN } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "PARWA Production Roadmap", size: 18, color: "808080", font: { ascii: "Calibri" } })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "PAGE  * ROMAN  * MERGEFORMAT", size: 18, color: "808080", font: { ascii: "Calibri" } }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "808080" })] })] }) },
      children: [
        new Paragraph({ spacing: { before: 200, after: 200 }, children: [new TextRun({ text: "Table of Contents", bold: true, size: 32, color: c(P.primary), font: { ascii: "Calibri" } })] }),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
        new Paragraph({ children: [new PageBreak()] }),
      ],
    },

    // ── SECTION 3: BODY ──
    {
      properties: { page: { pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL }, size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "PARWA Production Roadmap", size: 18, color: "808080", font: { ascii: "Calibri" } })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "PAGE  * arabic  * MERGEFORMAT", size: 18, color: "808080" }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "808080" })] })] }) },
      children: [
        // ── 1. EXECUTIVE SUMMARY ──
        heading("1. Executive Summary"),
        body("This roadmap defines the precise path to take PARWA from its current 70% completion state to full production readiness. The audit conducted on May 11, 2025, examined all 2,200+ Python files (16 MB of backend code), 145+ frontend source files, 97 database models across 28 model files, 19 sequential Alembic migrations, and 154+ test files. The findings confirm that the backend AI engine is genuinely massive and substantially built, with real LLM calls via LiteLLM, real payment integration via Paddle, real multi-tenant isolation, and 12 fully implemented AI technique nodes totaling over 17,000 lines of production code."),
        body("However, the audit also identified critical gaps that must be resolved before the product can serve real customers. These gaps fall into three categories: critical database bugs that will break fresh deployments, missing feature implementations that represent the DMD specification's core value propositions, and an incomplete frontend where 7 of 10 dashboard sub-pages display placeholder text. This roadmap organizes all remaining work into 5 phases spanning approximately 6 weeks, with clear priorities, dependencies, and acceptance criteria for every task."),
        bodyBold("Current State: ", "70% built. Backend is production-grade. Frontend is a polished shell with empty interior. Critical deployment bugs exist."),
        bodyBold("Target State: ", "100% production-ready with all DMD specifications implemented, tested, and deployable."),

        // ── 2. AUDIT SUMMARY ──
        heading("2. Audit Summary: What Exists vs. What's Missing"),

        h2("2.1 What Is Fully Built (Verified by Code Inspection)"),
        body("The following components were confirmed as real, working implementations with actual logic, not scaffolding or stubs. Each was verified by reading the source code directly."),
        makeTable(
          ["Component", "Files", "Lines", "Status"],
          [
            ["GSD State Engine", "gsd_engine.py", "1,100+", "Complete 8-state machine"],
            ["Smart Router", "smart_router.py", "1,848", "3-tier routing, 3 providers"],
            ["MAKER K-Solution Validator", "11_maker_validator.py", "684", "K=3/5/7 per variant"],
            ["12 AI Technique Nodes", "techniques/*.py (17 files)", "17,121", "All real LLM calls"],
            ["LangGraph Pipeline", "langgraph/ (19 nodes)", "9,781", "Full pipeline"],
            ["3 Variant Graphs", "mini_parwa/ parwa/ parwa_high/", "3,512", "Per-variant workflows"],
            ["Confidence Scoring", "confidence_scoring_engine.py", "1,615", "5 sub-scores"],
            ["CLARA Quality Gate", "clara_quality_gate.py", "703", "Response quality"],
            ["Hallucination Detector", "hallucination_detector.py", "1,451", "Multi-method"],
            ["Guardrails Engine", "guardrails_engine.py", "1,928", "Prompt injection defense"],
            ["PII Redaction", "pii_redaction_engine.py", "1,206", "Full detection"],
            ["Sentiment Engine", "sentiment_engine.py", "854", "Frustration scoring"],
            ["98 Backend Services", "services/ (98 files)", "67,459", "All real implementations"],
            ["97 Database Models", "models/ (28 files)", "~5,000", "Complete schema"],
            ["19 Alembic Migrations", "versions/ (001-019)", "~3,000", "Migration chain"],
            ["Billing (Paddle)", "paddle_service.py + APIs", "~2,000", "Real payments"],
            ["Multi-channel", "email/sms/chat/voice", "~5,000", "All 4 channels"],
            ["Frontend Landing/Auth", "src/app/", "~3,000", "Polished, production-quality"],
            ["Jarvis AI Chat", "jarvis page + API route", "~1,800", "Real multi-provider AI"],
          ]
        ),

        h2("2.2 What Is Missing or Broken"),
        body("The following gaps were identified through manual code inspection. Each item has been categorized by severity and assigned to a specific phase in this roadmap."),
        makeTable(
          ["Gap", "Severity", "Category", "Phase"],
          [
            ["Migration chain FK mismatch (sessions/tickets)", "CRITICAL", "Database Bug", "Phase 1"],
            ["UUID type inconsistency (OutboundEmail)", "CRITICAL", "Database Bug", "Phase 1"],
            ["Route prefix mismatch (variant_check)", "CRITICAL", "Backend Bug", "Phase 1"],
            ["Jarvis sessions in-memory only", "HIGH", "Backend Gap", "Phase 1"],
            ["Smart Router HealthTracker in-memory", "MEDIUM", "Backend Gap", "Phase 2"],
            ["MockVectorStore as default", "MEDIUM", "Backend Gap", "Phase 2"],
            ["FAKE Voting sub-system missing", "HIGH", "AI Engine Gap", "Phase 2"],
            ["Agent Lightning (training loop)", "HIGH", "AI Engine Gap", "Phase 3"],
            ["25 Loophole Solutions framework", "MEDIUM", "AI Engine Gap", "Phase 3"],
            ["Tickets Dashboard page", "HIGH", "Frontend Stub", "Phase 3"],
            ["Billing Dashboard page", "HIGH", "Frontend Stub", "Phase 4"],
            ["Knowledge Base Dashboard", "MEDIUM", "Frontend Stub", "Phase 4"],
            ["Settings Dashboard page", "MEDIUM", "Frontend Stub", "Phase 4"],
            ["AI Agents Dashboard page", "MEDIUM", "Frontend Stub", "Phase 4"],
            ["Monitoring Dashboard page", "MEDIUM", "Frontend Stub", "Phase 4"],
            ["Variants Dashboard page", "MEDIUM", "Frontend Stub", "Phase 4"],
            ["Socket.io Frontend Integration", "HIGH", "Frontend Gap", "Phase 4"],
            ["PostgreSQL Row-Level Security", "HIGH", "Security Gap", "Phase 5"],
            ["Production testing & QA", "HIGH", "Testing", "Phase 5"],
          ]
        ),

        // ── 3. PHASE 1 ──
        heading("3. Phase 1: Critical Bug Fixes (Days 1-3)"),
        body("Phase 1 addresses the three critical deployment bugs that will cause immediate failures on any fresh environment setup. These must be fixed before any other work can proceed, as they block basic system functionality. No new features should be built until these are resolved and verified with integration tests."),

        h2("3.1 Migration Chain FK Mismatch"),
        bodyBold("Problem: ", "Alembic migrations 003 (ai_pipeline_tables) and 005 (audit_billing_tables) reference sessions.id as a foreign key for gsd_sessions, confidence_scores, guardrail_blocks, and model_usage_logs. However, the sessions table was renamed to tickets as part of BL01, and the current models reference tickets.id. This means migration 003 and 005 will fail on a fresh database because they try to create foreign keys to sessions.id, but if the rename happened without a dedicated migration, the FK targets are inconsistent."),
        bodyBold("Fix: ", "Create migration 020 that explicitly handles the sessions-to-tickets rename. This migration should: (a) ALTER TABLE sessions RENAME TO tickets IF NOT ALREADY DONE, (b) Update all foreign key references in gsd_sessions, confidence_scores, guardrail_blocks, and model_usage_logs to point to tickets.id, (c) Update index names accordingly. Also modify migrations 003 and 005 to use tickets.id directly if the migration chain is not yet applied in production."),
        bodyBold("Acceptance Criteria: ", "A fresh database can be created from scratch using alembic upgrade head without errors. All foreign key constraints validate correctly. Existing data (if any) migrates cleanly."),

        h2("3.2 UUID Type Inconsistency"),
        bodyBold("Problem: ", "The OutboundEmail and EmailDeliveryEvent models in outbound_email.py and email_delivery_event.py import UUID from sqlalchemy.dialects.postgresql and use UUID(as_uuid=True) for their primary keys and foreign keys. Every other model in the entire codebase (95 out of 97 models) uses String(36) with a _uuid() helper function. This type mismatch means that any foreign key relationship between OutboundEmail/EmailDeliveryEvent and other tables (like tickets, companies) will fail at the database level because String(36) and UUID are not directly compatible types in PostgreSQL."),
        bodyBold("Fix: ", "Convert OutboundEmail and EmailDeliveryEvent to use String(36) with _uuid() consistently, matching all other models. Update migration 017 and 018 accordingly. Update any service code that constructs queries using these models. Verify no other models have the same inconsistency."),
        bodyBold("Acceptance Criteria: ", "All 97 models use String(36) for primary keys. No UUID type imports remain. Migration chain completes cleanly. All FK relationships validate."),

        h2("3.3 Route Prefix Mismatch in Variant Check Middleware"),
        bodyBold("Problem: ", "The variant_check.py ASGI middleware (307 lines) checks POST routes against /api/v1/tickets, /api/v1/team/invite, /api/v1/agents, and /api/v1/kb/documents. However, the actual tickets.py API route uses /tickets prefix (not /api/v1/tickets). This means that when a customer creates a ticket, the variant limit check never fires, and Mini PARWA customers could exceed their ticket limits without being blocked."),
        bodyBold("Fix: ", "Update variant_check.py to check the actual route prefixes used by each API module. Map /tickets (not /api/v1/tickets) for ticket creation. Verify all four route prefixes match their corresponding API files. Add a comment block documenting the correct prefix-to-API mapping."),
        bodyBold("Acceptance Criteria: ", "Variant limit enforcement triggers on ticket creation. Mini PARWA customers are correctly blocked at their limit (returns 402 Payment Required). All route prefix checks match their corresponding API route definitions."),

        h2("3.4 Jarvis Session Persistence"),
        bodyBold("Problem: ", "The frontend Jarvis API route handler (src/app/api/jarvis/[...path]/route.ts) stores all chat sessions in an in-memory JavaScript Map. This means every server restart loses all active Jarvis sessions, their context, and conversation history. For a production system where managers rely on persistent Jarvis interactions, this is unacceptable data loss."),
        bodyBold("Fix: ", "Move Jarvis session storage from in-memory Map to the database. The backend already has JarvisSession and JarvisMessage models with full schema (context_json memory, message types, action tickets). The frontend API route should delegate to the backend /api/jarvis/ endpoints instead of maintaining its own session store. As an interim fix, add Redis-backed session storage with serialization."),
        bodyBold("Acceptance Criteria: ", "Jarvis sessions persist across server restarts. Conversation history is retrievable after restart. No data loss when the Next.js server restarts."),

        h2("Phase 1 Timeline"),
        makeTable(
          ["Task", "Days", "Dependencies", "Owner"],
          [
            ["Migration chain FK fix", "Day 1-2", "None", "Backend"],
            ["UUID type normalization", "Day 1", "None", "Backend"],
            ["Route prefix mismatch fix", "Day 1", "None", "Backend"],
            ["Jarvis session persistence", "Day 2-3", "None", "Full-Stack"],
            ["Integration tests for all fixes", "Day 3", "All above", "Testing"],
          ]
        ),

        // ── 4. PHASE 2 ──
        heading("4. Phase 2: Backend Reliability & AI Engine Gaps (Days 4-10)"),
        body("Phase 2 addresses the remaining backend reliability issues and the most critical AI engine gaps. The Smart Router HealthTracker needs Redis backing for multi-worker support. The RAG system needs to default to PgVectorStore instead of MockVectorStore for production-quality embeddings. And the FAKE Voting sub-system within the MAKER framework needs implementation to complete the full MAKER pipeline as specified in the DMD."),

        h2("4.1 Smart Router HealthTracker Redis Backing"),
        bodyBold("Problem: ", "The Smart Router (smart_router.py, 1,848 lines) maintains provider health state (consecutive failure counts, rate limit cooldown timestamps, per-minute request counters) in Python class-level dictionaries. When running multiple Celery workers (the docker-compose configuration supports 8 queues with separate worker processes), each worker has its own independent HealthTracker instance. This means one worker might mark Google as failed while another worker continues sending requests to it, defeating the purpose of health tracking."),
        bodyBold("Fix: ", "Refactor the HealthTracker to store all state in Redis with atomic operations. Use Redis HASH for per-provider stats, Redis STRING with TTL for rate limit cooldowns, and Redis INCR/DECR for request counters. Ensure all reads and writes are atomic. Fall back to in-memory if Redis is unavailable (BC-008 graceful degradation)."),
        bodyBold("Acceptance Criteria: ", "Health state is shared across all Celery workers. Marking a provider as failed in one worker immediately affects all workers. Rate limit cooldowns are globally enforced."),

        h2("4.2 PgVectorStore as Default RAG Backend"),
        bodyBold("Problem: ", "The vector search system (vector_search.py) defaults to MockVectorStore, which generates deterministic SHA-256 pseudo-embeddings (768-dimensional) and uses in-memory cosine similarity. While this is an acceptable development fallback (BC-008), it produces terrible RAG quality in production because the pseudo-embeddings have no semantic meaning. Documents about refunds and documents about technical support will have random similarity scores."),
        bodyBold("Fix: ", "Reverse the default selection logic: use PgVectorStore when PostgreSQL+pgvector is available (which it always is in production via docker-compose), and fall back to MockVectorStore only when pgvector extension is not installed or the connection fails. Mount schema.sql in docker-compose to auto-enable the vector extension. Ensure the embedding service uses a real embedding model (even a free one via the Smart Router) instead of SHA-256 hashes."),
        bodyBold("Acceptance Criteria: ", "Production deployments use real pgvector embeddings by default. RAG search returns semantically relevant results. Fallback to mock only occurs when pgvector is genuinely unavailable."),

        h2("4.3 FAKE Voting Sub-System for MAKER Framework"),
        bodyBold("Problem: ", "The DMD specifies the MAKER (Multiple Assessment Knowledge Evaluation & Ranking) framework with a FAKE (Fallacy Analysis & Knowledge Evaluation) voting sub-system. The current MAKER Validator (684 lines) generates K candidate solutions and scores them in a single pass, but it does NOT implement the multi-round voting process where multiple independent LLM calls evaluate each solution and vote on correctness. The Smart Router's AtomicStepType enum defines FAKE_VOTING and CONSENSUS_ANALYSIS step types, but no dedicated implementation file exists for these steps."),
        bodyBold("Fix: ", "Implement the FAKE Voting engine as a new module in backend/app/core/maker_fake_voting.py. For each of the K candidate solutions: (a) Send each solution to N independent LLM evaluators (N=3 for Mini, N=5 for PARWA, N=7 for PARWA High), (b) Each evaluator scores the solution on correctness, completeness, safety, and customer-appropriateness, (c) Calculate weighted consensus score, (d) Flag solutions where evaluator agreement is below threshold, (e) Pass final consensus scores back to MAKER validator for selection. Use the Smart Router for all LLM calls with appropriate tier assignments."),
        bodyBold("Acceptance Criteria: ", "FAKE voting produces multi-evaluator consensus scores for each K solution. Evaluator disagreement triggers red flags. The MAKER validator uses consensus scores instead of single-pass scores. Token budget accounts for N*K additional LLM calls."),

        h2("Phase 2 Timeline"),
        makeTable(
          ["Task", "Days", "Dependencies", "Owner"],
          [
            ["HealthTracker Redis backing", "Day 4-5", "Phase 1 complete", "Backend"],
            ["PgVectorStore default swap", "Day 4-5", "Phase 1 complete", "Backend"],
            ["FAKE Voting engine implementation", "Day 6-9", "Phase 1 complete", "Backend"],
            ["FAKE Voting integration with MAKER", "Day 9-10", "FAKE Voting engine", "Backend"],
            ["Unit tests for all Phase 2 items", "Day 10", "All above", "Testing"],
          ]
        ),

        // ── 5. PHASE 3 ──
        heading("5. Phase 3: Agent Lightning, Loophole Framework & Tickets Page (Days 11-21)"),
        body("Phase 3 tackles the two biggest missing feature implementations from the DMD specification: Agent Lightning (the weekly self-learning loop that fine-tunes LLaMA-3-8B via Unsloth) and the structured 25 Loophole Solutions framework. Additionally, the Tickets dashboard page (the most important frontend stub) gets built. These are the core differentiators that separate PARWA from a generic AI customer service tool."),

        h2("5.1 Agent Lightning: Self-Learning Training Loop"),
        bodyBold("What DMD Specifies: ", "Agent Lightning is PARWA's proprietary self-improvement system. Every week, it collects AI mistakes (incorrect responses, customer escalations, low-confidence classifications), and when the mistake count crosses a 50-mistake threshold, it automatically triggers a fine-tuning run on LLaMA-3-8B using Unsloth on Google Colab (free GPU). The fine-tuned model is then deployed as a custom model option in the Smart Router. This creates a virtuous cycle where PARWA gets better every week without any manual intervention."),
        bodyBold("Current State: ", "The database models exist (TrainingDataset, TrainingCheckpoint, AgentMistake, AgentPerformance, TrainingRun in training.py). The Celery worker has training queues configured. But no actual training logic exists. There is no mistake collection code, no threshold detection, no Unsloth integration, no Colab connector, and no model deployment pipeline."),
        bodyBold("Implementation Plan: ", "Build the Agent Lightning system in 4 layers. Layer 1: Mistake Collection Service that monitors all AI responses, identifies low-confidence outputs, customer escalations, and negative feedback, then writes them to AgentMistake table. Layer 2: Threshold Detection as a Celery periodic task that runs daily, counts accumulated mistakes per variant, and triggers training when count exceeds 50. Layer 3: Training Pipeline that formats the mistake dataset into instruction-tuning format, prepares the Colab notebook execution, and manages the fine-tuning run via Google Colab API or local Unsloth. Layer 4: Model Deployment that registers the fine-tuned model with the Smart Router as a custom provider option."),
        bodyBold("Files to Create: ", "backend/app/services/agent_lightning_service.py, backend/app/tasks/training_tasks.py (extend existing), backend/app/core/model_registry.py, backend/app/api/model_management.py"),
        bodyBold("Acceptance Criteria: ", "AI mistakes are automatically collected and stored. Threshold detection triggers training at 50 mistakes. Training dataset is formatted correctly for instruction tuning. Fine-tuned model is registered in Smart Router. The entire pipeline runs end-to-end without manual intervention."),

        h2("5.2 Structured Loophole Solutions Framework"),
        bodyBold("What DMD Specifies: ", "The DMD defines 25 specific production loophole scenarios (edge cases where AI could cause harm, leak data, or make incorrect decisions) with corresponding solutions. Each loophole has an ID, description, severity, affected component, and mitigation strategy. The DMD requires these to be tracked, tested, and verified as implemented."),
        bodyBold("Current State: ", "Individual safeguards are scattered across the codebase (guardrails_engine.py, prompt_injection_defense.py, pii_redaction_engine.py, etc.), but there is no centralized loophole tracking system. No file, model, or module matches the structured 25 Loophole Solutions framework. The test files include some loophole-specific tests (test_day15_loopholes.py through test_day29_loopholes.py) but these test individual components rather than a unified framework."),
        bodyBold("Implementation Plan: ", "Create a centralized LoopholeRegistry in backend/app/core/loophole_registry.py that defines all 25 loopholes with their IDs, descriptions, severity levels, affected components, and current implementation status. Create a LoopholeVerifier service that runs verification checks for each loophole. Add an admin API endpoint to view loophole status and trigger verification runs. Map each loophole to its existing implementation file(s) and test file(s) for traceability."),
        bodyBold("Acceptance Criteria: ", "All 25 loopholes are defined in a centralized registry. Each loophole maps to its implementation and test files. An admin endpoint shows loophole coverage status. Verification runs can be triggered programmatically."),

        h2("5.3 Tickets Dashboard Page (Frontend)"),
        bodyBold("Current State: ", "The dashboard/tickets/page.tsx file is 15 lines that just say 'Connect your backend to view tickets'. The backend already has a fully implemented tickets API (762 lines) with CRUD, bulk operations, priority detection, category detection, PII scanning, assignment, tags, and attachments."),
        bodyBold("Implementation Plan: ", "Build a full-featured ticket management page with: (a) Ticket list view with sortable columns (ID, customer, subject, status, priority, assigned agent, created date), (b) Filters panel (status, priority, category, assigned agent, date range), (c) Ticket detail drawer/modal showing full conversation history, (d) Quick actions (assign, change status, add internal note, add tag), (e) Bulk action bar (bulk status change, bulk assign), (f) Real-time updates via Socket.io (connect to Phase 4), (g) Pagination with configurable page size. Use the existing API client (src/lib/api.ts) and backend /tickets endpoints."),
        bodyBold("Acceptance Criteria: ", "Ticket list loads with real data from backend. All CRUD operations work. Filters function correctly. Bulk actions work. Page is responsive and accessible. Loading states and error states are handled."),

        h2("Phase 3 Timeline"),
        makeTable(
          ["Task", "Days", "Dependencies", "Owner"],
          [
            ["Agent Lightning Layer 1: Mistake Collection", "Day 11-13", "Phase 2 complete", "Backend"],
            ["Agent Lightning Layer 2: Threshold Detection", "Day 14-15", "Layer 1", "Backend"],
            ["Agent Lightning Layer 3: Training Pipeline", "Day 16-18", "Layer 2", "Backend"],
            ["Agent Lightning Layer 4: Model Deployment", "Day 19-20", "Layer 3", "Backend"],
            ["Loophole Registry and Verifier", "Day 11-14", "Phase 2 complete", "Backend"],
            ["Tickets Dashboard Page", "Day 15-21", "Phase 1 complete", "Frontend"],
            ["Tests for Phase 3", "Day 21", "All above", "Testing"],
          ]
        ),

        // ── 6. PHASE 4 ──
        heading("6. Phase 4: Complete Frontend Dashboard (Days 22-35)"),
        body("Phase 4 builds out all remaining frontend dashboard pages and implements real-time Socket.io integration. The current frontend has a polished landing page, auth system, Jarvis chat, and main dashboard page, but 6 dashboard sub-pages are empty stubs displaying 'Coming Soon'. This phase transforms those stubs into fully functional pages connected to the real backend APIs."),

        h2("6.1 Billing Dashboard Page"),
        body("Build the billing management page with: subscription overview showing current plan, renewal date, and usage meters (tickets, messages, storage); invoice list with PDF download capability; payment method management; usage history with charts; upgrade/downgrade flow using the existing Paddle integration; overage alerts and notifications. Connect to backend /api/billing/* endpoints which are fully implemented (974 lines)."),

        h2("6.2 Knowledge Base Dashboard Page"),
        body("Build the knowledge base management page with: document upload (drag-and-drop with progress), document list showing status (indexed, indexing, failed), search across knowledge base articles, chunk preview and management, reindex triggering, document deletion with confirmation. Connect to backend /api/rag/* endpoints which are fully implemented (308 lines)."),

        h2("6.3 Settings Dashboard Page"),
        body("Build the settings page with tabbed interface covering: Company Profile (name, industry, timezone, language), API Keys (generate, view, revoke, usage stats), Team Management (invite, roles, permissions), Notification Preferences (email, in-app, channel-specific), Security (MFA setup, password change, active sessions, IP allowlist), Integration Settings (webhook URLs, channel configuration). Connect to the appropriate backend services."),

        h2("6.4 AI Agents Dashboard Page"),
        body("Build the AI agents management page showing: agent list with status (active, idle, training), agent performance metrics (resolution rate, avg response time, customer satisfaction), agent capability matrix per variant, training history for Agent Lightning, agent configuration options. Connect to backend /api/ai/agents/* endpoints."),

        h2("6.5 Monitoring Dashboard Page"),
        body("Build the monitoring and observability page with: system health overview (API latency, error rates, queue depths), AI engine metrics (token usage per provider, confidence score distribution, technique execution counts), real-time alert feed, SLA compliance tracking, cost tracking (daily/weekly/monthly spend). Connect to backend /api/ai/monitoring/* endpoints and Prometheus metrics."),

        h2("6.6 Variants Dashboard Page"),
        body("Build the variant configuration page showing: current variant tier with feature comparison matrix, capability toggles per feature (170+ features in the Feature Registry), workload distribution across instances, token budget configuration, variant transition management (upgrade/downgrade). Connect to backend /api/ai/capabilities/* and /api/ai/instances/* endpoints."),

        h2("6.7 Socket.io Frontend Integration"),
        body("The backend has a full Socket.io server (backend/app/core/socketio.py) but the frontend has zero Socket.io client code. Implement: Socket.io client initialization with JWT authentication, event listeners for ticket updates, new messages, agent status changes, and system alerts. Add real-time indicators to the dashboard (live ticket count, active agents, pending escalations). Implement optimistic UI updates with server reconciliation. Add connection status indicator. Use the existing socket.io-client npm package."),

        h2("Phase 4 Timeline"),
        makeTable(
          ["Task", "Days", "Dependencies", "Owner"],
          [
            ["Billing Dashboard Page", "Day 22-26", "Phase 1 complete", "Frontend"],
            ["Knowledge Base Dashboard Page", "Day 24-27", "Phase 1 complete", "Frontend"],
            ["Settings Dashboard Page", "Day 27-30", "Phase 1 complete", "Frontend"],
            ["AI Agents Dashboard Page", "Day 28-31", "Phase 3 complete", "Frontend"],
            ["Monitoring Dashboard Page", "Day 30-33", "Phase 2 complete", "Frontend"],
            ["Variants Dashboard Page", "Day 31-34", "Phase 2 complete", "Frontend"],
            ["Socket.io Frontend Integration", "Day 33-35", "All pages built", "Frontend"],
            ["E2E tests for all dashboard pages", "Day 35", "All above", "Testing"],
          ]
        ),

        // ── 7. PHASE 5 ──
        heading("7. Phase 5: Security Hardening & Production QA (Days 36-42)"),
        body("Phase 5 is the final push before production launch. It addresses the remaining security gap (PostgreSQL Row-Level Security), runs comprehensive production testing, and ensures the entire system is deployable and stable."),

        h2("7.1 PostgreSQL Row-Level Security (RLS)"),
        bodyBold("Problem: ", "The DMD/ADD architecture specification (P-09) mandates PostgreSQL Row-Level Security policies to enforce tenant isolation at the database level. Currently, all tenant isolation is enforced at the application layer via TenantSession middleware. If a database connection is compromised (SQL injection, connection pool leak), an attacker could potentially access data from other tenants."),
        bodyBold("Implementation Plan: ", "Create RLS policies on all tables that have company_id. Enable RLS with ALTER TABLE ... ENABLE ROW LEVEL SECURITY. Create policies that restrict SELECT, INSERT, UPDATE, DELETE operations to rows matching the current tenant context. Use PostgreSQL's SET app.current_tenant_id mechanism to pass the tenant ID at connection time. Modify the database connection factory to set the tenant context on every connection checkout. Ensure the RLS policies do not break admin operations (which need cross-tenant access)."),
        bodyBold("Acceptance Criteria: ", "RLS policies are active on all tenant-scoped tables. Direct database queries without app.current_tenant_id return no rows. Admin operations bypass RLS via a superuser role. Connection pool correctly sets tenant context."),

        h2("7.2 Production Testing & QA"),
        body("Run comprehensive production readiness testing: (a) Load testing with 120 concurrent requests (test already exists at tests/production/test_120_requests.py), (b) End-to-end ticket lifecycle testing, (c) Payment flow testing with Paddle sandbox, (d) Multi-tenant isolation verification (cross-tenant data access attempts), (e) Failover testing (kill individual services and verify degradation), (f) Socket.io reconnection testing, (g) Security penetration testing (SQL injection, XSS, CSRF, prompt injection). Fix all discovered issues."),

        h2("7.3 Deployment Readiness"),
        body("Prepare the production deployment: (a) Verify docker-compose.prod.yml works correctly with all services, (b) Ensure all environment variables are documented, (c) Create production database migration script, (d) Set up monitoring dashboards (Grafana configs already exist in monitoring/grafana_dashboards/), (e) Configure alerting rules (Prometheus + AlertManager configs exist in monitoring/), (f) Test the nginx reverse proxy configuration, (g) Verify SSL/TLS setup, (h) Create runbook for common operations."),

        h2("Phase 5 Timeline"),
        makeTable(
          ["Task", "Days", "Dependencies", "Owner"],
          [
            ["PostgreSQL RLS implementation", "Day 36-39", "Phase 1 complete", "Backend"],
            ["RLS testing and verification", "Day 39-40", "RLS implementation", "Testing"],
            ["Production load testing (120 req)", "Day 40", "All features", "Testing"],
            ["E2E payment flow testing", "Day 40-41", "Phase 1 complete", "Testing"],
            ["Multi-tenant isolation testing", "Day 41", "RLS complete", "Testing"],
            ["Failover and resilience testing", "Day 41", "Phase 2 complete", "Testing"],
            ["Security penetration testing", "Day 42", "All features", "Security"],
            ["Deployment readiness checklist", "Day 42", "All above", "DevOps"],
          ]
        ),

        // ── 8. RESOURCE REQUIREMENTS ──
        heading("8. Resource Requirements & Dependencies"),

        h2("8.1 Technical Dependencies"),
        makeTable(
          ["Dependency", "Purpose", "Status"],
          [
            ["PostgreSQL 15 + pgvector", "Primary database with vector search", "Available (docker-compose)"],
            ["Redis 7", "Cache, session store, Celery broker", "Available (docker-compose)"],
            ["LiteLLM", "Unified LLM API for Smart Router", "Installed (requirements.txt)"],
            ["Google AI Studio API Key", "Primary LLM provider (free tier)", "Required - free"],
            ["Cerebras API Key", "Secondary LLM provider (free tier)", "Required - free"],
            ["Groq API Key", "Tertiary LLM provider (free tier)", "Required - free"],
            ["Paddle Account", "Payment processing", "Required - free sandbox"],
            ["Brevo Account", "Email delivery (OTP, notifications)", "Required - free tier"],
            ["Google Colab (for Agent Lightning)", "Free GPU for model fine-tuning", "Required - free"],
            ["Unsloth (Colab notebook)", "Efficient LLaMA fine-tuning library", "Required - open source"],
          ]
        ),

        h2("8.2 Risk Mitigation"),
        makeTable(
          ["Risk", "Probability", "Impact", "Mitigation"],
          [
            ["Free API tier rate limits exhausted", "Medium", "High", "Smart Router already has failover chains; add request queuing"],
            ["Google Colab session timeout during training", "Medium", "Medium", "Implement checkpoint save/resume in training pipeline"],
            ["Migration breaks existing production data", "Low", "Critical", "Test on staging copy first; backup before migration"],
            ["Frontend complexity exceeds timeline", "Medium", "Medium", "Prioritize tickets/billing pages first; stubs acceptable for others"],
            ["RLS policies break admin operations", "Medium", "High", "Test admin bypass role thoroughly; use superuser for admin ops"],
          ]
        ),

        // ── 9. MILESTONES ──
        heading("9. Key Milestones & Success Metrics"),
        makeTable(
          ["Milestone", "Day", "Success Criteria"],
          [
            ["M1: Deployment Bugs Fixed", "Day 3", "Fresh DB deploys without errors; variant limits enforce"],
            ["M2: Backend Reliability Complete", "Day 10", "HealthTracker shared across workers; FAKE voting operational"],
            ["M3: AI Self-Learning Operational", "Day 21", "Mistakes auto-collected; training triggers at threshold"],
            ["M4: Full Frontend Dashboard", "Day 35", "All 10 dashboard pages functional with real data"],
            ["M5: Production Security Verified", "Day 42", "RLS active; penetration test passed; 120 req load test passed"],
            ["M6: Production Launch Ready", "Day 42", "All phases complete; deployment playbook ready; monitoring active"],
          ]
        ),

        body("This roadmap represents a conservative 6-week timeline that accounts for the complexity of the remaining work. The phases are designed so that each phase delivers independently valuable improvements, meaning that even if the timeline extends, the product improves progressively rather than waiting for a big-bang delivery. The priority order ensures that the most critical issues (deployment bugs, data persistence, core AI gaps) are resolved first, while less critical features (monitoring dashboard, variants page) can be deferred if needed without blocking production launch."),
      ],
    },
  ],
});

// ═══════════════════════════════════════════════════════════════
// GENERATE
// ═══════════════════════════════════════════════════════════════
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("/home/z/my-project/download/PARWA_Production_Readiness_Roadmap.docx", buf);
  console.log("Document generated: PARWA_Production_Readiness_Roadmap.docx");
});
