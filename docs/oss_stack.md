# OSS Stack — what each piece does + what YOU need to do

All code lives in `backend/app/core/oss_stack/`. Everything is optional,
flag-gated, and degrades gracefully: if a library is missing, PARWA keeps
its old behaviour. Nothing here can crash the pipeline.

**Local LLM is deliberately NOT part of this stack** (a 7B model needs
5–6 GB RAM and runs at ~13–15 tok/s — too slow for live tickets). LLMs
stay on APIs. Everything below runs on CPU, light.

Verify everything with:

```bash
pip install -r backend/requirements.txt   # light deps only
python scripts/verify_oss_stack.py        # PASS/FAIL table, exit 0 = good
```

## The pieces

| # | Module (file) | Library | What it does for PARWA | Env flag (default) |
|---|---|---|---|---|
| 1 | `guard.py` | stdlib only | Strips `<think>` blocks, rejects empty/think-only answers with a quality score — the trust layer so tickets are never "resolved" with garbage | always on |
| 2 | `docparse.py` | MarkItDown | PDF/DOCX/XLSX/PPT → clean text at KB upload (was: UTF-8 garbage for PDFs) | `OSS_DOCPARSE=1` |
| 3 | `embeddings.py` | fastembed (ONNX MiniLM, 384-dim, ~150 MB RAM) | LOCAL embeddings at KB upload + retrieval fallback so vector search works even when Google/NVIDIA embedding APIs fail | `OSS_EMBEDDINGS=1` |
| 4 | `kb.py` | rank-bm25 + RapidFuzz | BM25 keyword ranking (with light stemming) even when chunks have no embeddings; fuzzy dedupe | always on (libs optional) |
| 5 | `pii.py` | Presidio (+ regex fallback) | Redacts cards/emails/phones/gov-IDs before LLM calls and logs | `OSS_PII=0` → turn on when ready |
| 6 | `intent.py` | GLiClass or embedding-similarity | Zero-shot intent + urgency classification in ms at ₹0 (replaces one LLM call per ticket in triage) | `OSS_INTENT=0` until wired into triage UI |
| 7 | `entities.py` | GLiNER optional + regex floor | Pulls order numbers, amounts, emails, dates from ticket text → clean tool inputs for variants | import anytime |
| 8 | `structured.py` | Instructor + LiteLLM | Guaranteed-JSON LLM extraction; LiteLLM fallback chains with per-call budgets | `OSS_LITELLM=0` until provider keys set |
| 9 | `channels/poller.py` | imap-tools / aiogram | Email + Telegram → normalized messages for intake | `OSS_CHANNEL_EMAIL/TELEGRAM=0` |

## Bugs fixed in this push (pipeline patches)

1. **`backend/app/api/knowledge_base.py` (upload)**
   - PDF/DOCX no longer UTF-8-mangled: binary formats go through MarkItDown; unreadable binary uploads are REJECTED with a clear message.
   - Every chunk gets a best-effort LOCAL embedding (384-dim) at upload → vector search works out of the box.
2. **`node_3_knowledge_fetch.py` (retrieval)**
   - NEW Tier 1.5: BM25 keyword search runs ALWAYS (previously it only ran inside the `has_embeddings` branch — fresh uploads with zero embeddings were completely invisible → the "empty POLICIES AND FACTS" production bug).
   - Tier 1.5 also fuses local 384-dim vector similarity, so even with the external embedding API dead, semantic search still works.
   - Tier 2 no longer dumps ALL tenant chunks into the prompt: ranked (BM25-lite) and capped at 12.

## What YOU need to do (per piece)

**Do nothing (already active):** guard, docparse (text formats), kb ranking, embeddings fallback — they turn on with defaults and fall back safely.

**On Render (backend service), add env vars when ready:**

| To enable | Add |
|---|---|
| PDF uploads (MarkItDown) | nothing — it's in requirements.txt |
| Presidio PII (higher accuracy than regex) | `OSS_PII=1` |
| Intent triage | `OSS_INTENT=1` |
| LiteLLM fallback chains | `OSS_LITELLM=1` + provider keys (`OPENAI_API_KEY` etc.) |
| Email channel | `OSS_CHANNEL_EMAIL=1` + `KB_EMAIL_IMAP_HOST/USER/PASS/PORT` |
| Telegram channel | `OSS_CHANNEL_TELEGRAM=1` + `KB_TELEGRAM_BOT_TOKEN` |

**First deploy note:** the fastembed model (~90 MB) downloads once from
Hugging Face on first embedding call. If the download fails, uploads and
retrieval still work (BM25 path) — check logs for `oss_embeddings`.

**Heavy extras (NOT in requirements.txt — torch-based, only if you ever
want them on a bigger box):** `gliclass`, `gliner`. intent/entities fall
back to embeddings/regex without them.
