# HANDOFF PROMPT — Parwa Skills Box (paste this into the new chat)

You are continuing work on PARWA (parwa.buzz) — an AI customer-care SaaS. I (Abhay) have already decided the plan below with a previous session. Do NOT re-research or re-debate. Build it. Reply to me in simple English, short sentences.

## CONTEXT YOU NEED

- Repo: https://github.com/abhaythakur754-0/parwa.git (backend = Python FastAPI, 8-node LangGraph pipeline in `backend/app/core/parwa_pipeline/nodes/`)
- Read `/home/z/my-project/worklog.md` FIRST (it is huge — read the LAST 400 lines and search for "Task ID: 6" and "Task ID: 7"). It contains everything: audit results, exact file paths, and the recipe for 2 lost commits.
- Production backend runs on Render with only **512MB RAM**. NEVER run heavy models in-process there.
- Existing connection pattern to copy: `backend/app/core/superglue_client.py` — env-flag + client wrapper + graceful fallback. My OSS stack lives in `backend/app/core/oss_stack/` (flags in `__init__.py`; pii.py = Presidio, intent.py = GLiClass, entities.py = GLiNER — all DORMANT, flag exists but no importer).
- IMPORTANT: this sandbox is ONLY for building + running the skills box and connecting Parwa to it. I (Abhay) will give you every link, token and credential in chat when you ask. My old GitHub token is DEAD (revoked) — ask me for a fresh one before any push.
- The Phase-1 Parwa-side wiring was pushed as commit **6ff28d95** ("superglue: fix 3 wiring bugs + qwen purge + OSS skills-hub wiring (Phase 1)"). Your job for this part is VERIFY, not re-write. If that commit is missing on GitHub, STOP and tell me — do not rewrite from memory:
  1. After the Render deploy of 6ff28d95, create ONE order-status ticket and ONE refund ticket in the agent chat and confirm in logs/audit that tools execute under `tenant_{id}__{name}` ids (SUCCESS rows, not 404)
  2. If the deploy stuck >15 min, tell me to retrigger from the Render dashboard
  3. Also wired in 6ff28d95: `oss_stack/hub.py` (routes to SKILLS_BOX_URL → local flags → regex floor), node1 zero-shot capability + entity enrichment, node5 PII-scrub upgrade, qwen3.6→qwen3.8 purge. Do NOT redo these.

## THE DECIDED PLAN (do not change)

A "skills box" = ONE FastAPI service. ONE port (8055). ONE API key for ALL endpoints. It exposes 9 abilities as HTTP endpoints. Parwa's 512MB Render backend calls it like it calls SuperGlue (one URL env var + one key). Libraries do the work; NO local text-generation LLMs anywhere.

| Endpoint | Ability | Library |
|---|---|---|
| POST /classify | intent classification, kills 1 LLM call/ticket | GLiClass (zero-shot) |
| POST /entities | order numbers, emails, names, amounts | GLiNER |
| POST /mask | PII masking | Presidio (+regex fallback) |
| POST /ocr | screenshots → text | PaddleOCR |
| POST /transcribe | voice notes → text | faster-whisper (**base, int8** — start here; upgrade to small later only if voice quality feels weak) |
| POST /speak | text → voice | Piper |
| POST /translate | translate in/out | Argos Translate |
| POST /remember | customer memory | Mem0 (store: local SQLite or my Supabase Postgres) |
| POST /browse | act in admin panels with no API | browser-use + Playwright Chromium |
| GET /health | liveness + loaded models + **live RAM usage** | — |

Auth = ONE key on ALL endpoints: header `X-Skills-Key: <SKILLS_BOX_KEY>` (except /health).

Build phases (do them in this order):
- **Phase 1:** /classify /entities /mask (pure performance: −2–3 LLM calls per ticket)
- **Phase 2:** /ocr /transcribe (biggest coverage jump)
- **Phase 3:** /remember /browse /translate /speak

## PART 1 — BUILD (in this sandbox)

1. Create `mini-services/skills-box/` (independent Python project):
   - `main.py` (FastAPI, port **8055**), `requirements.txt`, `start.sh`, `README.md`
   - Auth: require header `X-Skills-Key: <SKILLS_BOX_KEY>` on every endpoint except /health. ONE key for all 9 skills.
   - LAZY-LOAD every model on first request; never load two heavy models at once (use a lock).
   - RAM GUARD: if total RSS crosses ~3.2GB, auto-unload the least-recently-used model. It reloads on demand.
   - Target: whole box ≤ 3GB RAM with whisper + OCR loaded. /health must report live RAM per loaded model.
   - Every endpoint: JSON in / JSON out, 200 on success, 4xx with `{"error": ...}` on bad input. 30s default timeout on /transcribe, 120s on /browse.
   - Every response includes `{"ok": true, "data": {...}, "ms": <latency>}`.
   - `start.sh`: installs deps, pre-downloads models (whisper base int8, PaddleOCR models, Argos en↔de/fr/es/it/pt, GLiClass + GLiNER weights), then `uvicorn main:app --host 0.0.0.0 --port 8055`.
2. Test each endpoint with curl INSIDE the sandbox and show me the outputs.
3. Write `setup_skills_box.sh` — a ONE-FILE script I will run on my own Ubuntu 4GB box. It must: install python3-pip + deps, copy the service, pre-download models, install cloudflared, and print next-step commands. Make it idempotent (safe to re-run).

## PART 2 — GLOBAL LAUNCH via CLOUDFLARE (on MY 4GB box, not the sandbox)

WHY: Render is outside any sandbox. The Cloudflare tunnel gives the box a public URL so Parwa can call it 24/7 from anywhere in the world.

Give me simple copy-paste commands for:
1. Copying the `skills-box` folder to my box (scp or zip download — ask me which I prefer)
2. Running `start.sh` there
3. Cloudflare tunnel — two options, give both:
   - Quick (5 min, URL changes on restart): `cloudflared tunnel --url http://localhost:8055` → prints a trycloudflare.com link
   - Permanent (I own parwa.buzz on Cloudflare): named tunnel → `skills.parwa.buzz` — ask me for the Cloudflare token when you reach this step
4. PROVE it is global: from INSIDE the sandbox, curl the public URL (`/health` + one real endpoint with the key) and show me the outputs. Only after the box answers from outside do we move on.
5. The script prints my **SKILLS_BOX_URL**; I generate a **SKILLS_BOX_KEY** (one long random string).

I will then paste the URL + key to you — those are my credentials, same flow as SuperGlue.

## PART 3 — INTEGRATE INTO PARWA (mostly VERIFY — already pushed in 6ff28d95)

1. `backend/app/core/oss_stack/skills_client.py` — if it exists from 6ff28d95, verify, don't rewrite. Otherwise copy superglue_client.py style: reads `SKILLS_BOX_URL` + `SKILLS_BOX_KEY` env vars, 5s timeout, **if box is unreachable → return None and let existing code path run unchanged** (never break a ticket because the box is down). Log every call (endpoint, ms, ok/error).
2. Wiring points (Phase 1):
   - node_1: replace the LLM classification fallback with /classify when box is up
   - node_1 customer_context: /entities for order numbers/emails/amounts
   - SafetyNet PII scrub (`_PII_RE` in node_4, email_utils, logs): /mask when box is up, keep regex floor
   - Behind ONE flag: `OSS_SKILLS_BOX=1`
3. Phase 2 wiring: ticket attachment ingestion (tickets.py) → if image attachment → /ocr, append text to ticket content; voice attachment → /transcribe. Behind `OSS_SKILLS_MEDIA=1`.
4. Add unit tests only for the client (mock HTTP), no test code for the ML parts.

## PART 4 — PUSH + DEPLOY

- Ask me for a fresh GitHub token (fine-grained, repo scope) so YOU can push. Previous sessions lost work because commits sat local.
- Push, then watch the Render deploy (backend-parwa service). Deploys sometimes stick — if the build hangs >15 min, tell me to retrigger manually from the Render dashboard.
- After deploy: I set `SKILLS_BOX_URL` + `SKILLS_BOX_KEY` + `OSS_SKILLS_BOX=1` on Render. Then I create a test ticket in the agent chat; verify in logs that /classify was called and LLM call count dropped.

## RULES

- Simple English only when talking to me. No long essays.
- Append your work record to `/home/z/my-project/worklog.md` (template: `---` / Task ID / Agent / Task / Work Log / Stage Summary) — read the last entries first.
- Use `bun run dev` for the Next.js frontend if needed; the skills box runs on port 8055 via uvicorn in background.
- NEVER run text-generation LLMs locally. Only the small models listed above.
- Start with Phase 1 now. Ask me before Phase 3 (Mem0 store choice: SQLite vs Supabase Postgres).

FIRST MESSAGE FROM YOU should be: 1) confirmation you read the worklog, 2) the Phase-1 file plan, 3) what you need from me (nothing yet — credentials come after Part 2).
