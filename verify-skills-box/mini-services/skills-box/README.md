# Parwa Skills Box

ONE FastAPI service. ONE port (8055). ONE key for ALL 9 skills.
Small local models do the work — **no text-generation LLMs anywhere**.

Parwa's 512MB Render backend calls this box like it calls SuperGlue:
one URL env var (`SKILLS_BOX_URL`) + one key (`SKILLS_BOX_KEY`).

## Endpoints

| Endpoint | Ability | Library | Phase |
|---|---|---|---|
| `POST /classify` | zero-shot intent classification (kills 1 LLM call/ticket) | GLiClass | 1 |
| `POST /entities` | order numbers, emails, names, amounts | GLiNER | 1 |
| `POST /mask` | PII masking (+regex floor, never fails) | Presidio | 1 |
| `POST /ocr` | screenshots → text | PaddleOCR | 2 |
| `POST /transcribe` | voice notes → text (base **int8**) | faster-whisper | 2 |
| `POST /translate` | translate in/out (en↔de/fr/es/it/pt) | Argos | 3 |
| `POST /speak` | text → voice (wav) | Piper | 3 |
| `POST /remember` | customer memory in a **DATABASE** (free space) | SQLite / Supabase | 3 |
| `POST /browse` | act in admin panels | browser-use | 3 — **501 until LLM brain chosen** |
| `GET /health` | liveness + loaded models + **live RAM** | — | no auth |
| `POST /warm` | pre-load skills after boot | — | auth |

## Auth

ONE key on every endpoint except `/health`:

```
X-Skills-Key: <SKILLS_BOX_KEY>
```

Set `SKILLS_BOX_KEY` env var, or the box generates one on first boot and
saves it to `.skills_key` (chmod 600) next to `main.py`.

## Response contract

```json
{"ok": true, "data": {...}, "ms": 42}
```

Errors: `4xx/5xx` with `{"ok": false, "error": "..."}`.

## RAM safety (the 4GB box)

- Models **lazy-load** on first request.
- Only **one heavy model loads at a time** (global lock).
- **RAM guard**: process RSS over `SKILLS_RAM_LIMIT_MB` (default 3200)
  auto-unloads the least-recently-used model; it reloads on demand.
- `/health` shows live RSS + per-model RAM, loads/unloads, last-used age.
- `/transcribe` times out at 30s, `/browse` at 120s (model loading is never timed).

## Run

```bash
./start.sh          # installs deps + models (idempotent), serves :8055
```

Env knobs (all optional):

| Var | Default | Meaning |
|---|---|---|
| `SKILLS_BOX_KEY` | auto-generated | the ONE API key |
| `SKILLS_RAM_LIMIT_MB` | 3200 | RAM guard threshold |
| `GLICLASS_MODEL` | knowledgator/gliclass-base-v1.0 | classify model |
| `GLINER_MODEL` | urchade/gliner_multi-v2.1 | entities model |
| `WHISPER_MODEL` | base | faster-whisper size (upgrade to `small` only if voice feels weak) |
| `WHISPER_COMPUTE` | int8 | whisper quantization |
| `ARGOS_PAIRS` | en-de,en-fr,en-es,en-it,en-pt | translate pairs to preload |
| `SKILLS_MEM_STORE` | sqlite | `sqlite` (zero-config) or `postgres` (Supabase free tier) |
| `SKILLS_MEM_DB_URL` | — | Postgres DSN for Supabase mode (**SECRET** — put in `skills.env`) |
| `SKILLS_MEM_MAX_PER_USER` | 500 | auto-prune oldest beyond this cap |
| `SKILLS_WARMUP` | none | `phase1` or `all` = preload models at boot |
| `SKILLS_PORT` | 8055 | listen port |

### Customer memory (/remember)

Abhay picked the **database route** (2026-09-25): memory lives in a DB so the
4GB box spends **zero local disk** on it.

- **Default — SQLite**: works from the zip, data in `data/memory.db`.
- **Free cloud — Supabase Postgres**: create a free project at
  supabase.com → Project Settings → Database → copy the **Session pooler**
  connection string (works on IPv4-only home boxes), then create
  `skills.env` next to `start.sh`:

```bash
# skills.env (gitignored, NEVER commit)
SKILLS_MEM_STORE=postgres
SKILLS_MEM_DB_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-xx-x.pooler.supabase.com:5432/postgres
```

Restart the box — `start.sh` sources `skills.env` automatically. `sslmode=require`
is added for you. The table + indexes are created on first use; nothing to run.

Search is full-text (tsvector / FTS5) + recency boost — no embedding model,
no vector RAM, honoring the no-local-LLM rule. Keywords (order ids, emails,
phones, amounts, dates) are extracted on write to sharpen recall.

## curl examples

```bash
KEY=$(cat .skills_key)

curl -s localhost:8055/health | python3 -m json.tool

curl -s localhost:8055/classify -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Where is my order 45812? It is 3 days late","labels":["order status","refund","complaint","chitchat"]}'

curl -s localhost:8055/entities -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"I am Priya Sharma, order 45812 was $129.99, email priya@gmail.com"}'

curl -s localhost:8055/mask -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"my email is priya@gmail.com and card 4111 1111 1111 1111"}'

# ── remember: add → search → wipe ────────────────────────────────
curl -s localhost:8055/remember -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"action":"add","user_id":"customer:123","text":"Priya prefers email, order 45812 arrived 3 days late, promised 10% coupon","mask":true}'

curl -s localhost:8055/remember -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"action":"search","user_id":"customer:123","query":"order coupon","k":3}'

curl -s localhost:8055/remember -H "X-Skills-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"action":"count","user_id":"customer:123"}'
```

## Global access (Cloudflare)

Quick (URL changes on restart):
```bash
cloudflared tunnel --url http://localhost:8055
```

Permanent (needs a Cloudflare account with parwa.buzz + tunnel token):
```bash
cloudflared service install <TUNNEL_TOKEN>   # tunnel pre-configured to skills.parwa.buzz → localhost:8055
```

Then in Render set:
```
SKILLS_BOX_URL=https://skills.parwa.buzz
SKILLS_BOX_KEY=<the key from .skills_key>
OSS_SKILLS_BOX=1
```
