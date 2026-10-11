# ENV-VARS.md — every credential & setting in one place

Nothing here is a secret from the internet. Your box generates its own
key on first start — that key is the ONLY credential you will ever create
for the skills box. Everything else is a URL or a flag.

## 1) On YOUR box (skills box side)

Set these in `~/skills-box/skills.env` (auto-loaded by start.sh).
File does not exist yet? `nano ~/skills-box/skills.env` — create it.

| Variable | Required? | Example / default | What it does |
|---|---|---|---|
| `SKILLS_BOX_KEY` | optional | auto-generated → `.skills_key` | The ONE key for all 9 skills. Pin your own (survives reinstalls): `echo "SKILLS_BOX_KEY=$(openssl rand -hex 32)" >> ~/skills-box/skills.env` |
| `SKILLS_RAM_LIMIT_MB` | optional | `3200` | RAM guard limit for your 4GB box. Lower to `2800` if the box feels tight |
| `SKILLS_MEM_STORE` | optional | `sqlite` | Memory backend. `postgres` = your free Supabase (zero local disk) |
| `SKILLS_MEM_DB_URL` | only if postgres | `postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres` | Supabase connection string (Settings → Database) |
| `SKILLS_MEM_DB_PATH` | optional | `data/memory.db` | sqlite file location (ignored when postgres) |
| `SKILLS_MEM_MAX_PER_USER` | optional | `500` | Auto-prune memories per customer |

Port is fixed: **8055**. `/health` needs NO key. Every other endpoint
needs the header `X-Skills-Key: <your key>`.

After editing skills.env: `pkill -f start.sh; cd ~/skills-box && nohup ./start.sh > box.log 2>&1 &`

## 2) On Render (your product side)

Dashboard → your service → Environment → add, then redeploy:

| Variable | Value | Where the value comes from |
|---|---|---|
| `SKILLS_BOX_URL` | `https://xxxx.trycloudflare.com` (temp) or `https://skills.parwa.buzz` (permanent) | Printed by `cloudflared tunnel --url http://localhost:8055` (QUICKSTART step 4) or your named tunnel (step 6) |
| `SKILLS_BOX_KEY` | the exact string from `cat ~/skills-box/.skills_key` | QUICKSTART step 3 |
| `OSS_SKILLS_BOX` | `1` | Static flag — turns the box connection ON |
| `OSS_SKILLS_MEDIA` | `1` | Static flag — OCR + voice-notes on tickets (activates with the media patch) |

## 3) Credentials you may create (optional)

- **Cloudflare account** — only for the PERMANENT tunnel
  (`cloudflared tunnel login`, browser login, QUICKSTART step 6).
  The quick tunnel (step 4) needs NO account at all.
- **Supabase free account** — only if you want memory in the cloud
  instead of sqlite on the box. Copy the connection string into
  `SKILLS_MEM_DB_URL`. supabase.com → New project → Settings → Database.
- **GitHub fine-grained token** — only if you want the sandbox to push
  the skills-box code + patches into your repo (abhaythakur754-0/parwa).
  Create at github.com → Settings → Developer settings → Fine-grained
  tokens → only this repo → Contents: Read and write.

## 4) Security rules (already enforced)

- `.skills_key` is chmod 600 and gitignored — it never travels in any
  zip, backup, or repo.
- All traffic to the box is HTTPS via Cloudflare tunnel.
- Box down ≠ tickets down: Render falls back to local regex/classifier.
