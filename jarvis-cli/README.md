# Jarvis CLI — Parwa's AI Admin Console

Talk to your Parwa support operation in plain English. Jarvis (the AI brain)
picks the right tool; this CLI executes it against the **real Parwa backend**
(tickets, health, AI pause/resume, billing, integrations).

## Modes

| Mode | When | What happens |
|---|---|---|
| **LIVE** | `PARWA_API_TOKEN` is set | Tools hit your real backend — real tickets, real pause/resume (audit-logged) |
| **DEMO** | no token | Same tools, simulated data — every reply is honestly labeled `[demo]` |

## Run

```bash
cd jarvis-cli
npm install

# DEMO mode (no backend needed)
npm run chat

# LIVE mode
PARWA_API_URL=https://parwa-backend.onrender.com \
PARWA_API_TOKEN=<jwt-from-login> \
npm run chat
```

Get a token from your backend:

```bash
curl -X POST https://parwa-backend.onrender.com/api/auth/login \
  -H "Content-Type: application/json" -H "Origin: https://parwa.buzz" \
  -d '{"email":"you@company.com","password":"..."}'
```

## Env vars

| Var | Default | Purpose |
|---|---|---|
| `PARWA_API_URL` | `http://localhost:10000` | Backend base URL |
| `PARWA_API_TOKEN` | *(empty → demo mode)* | JWT bearer token |
| `PARWA_ORIGIN` | `http://localhost:3000` | Origin header sent with requests |

## What's wired to the real backend (13 tools)

`check_system_health` · `get_performance_metrics` · `get_agent_status` ·
`pause_all_ai` · `resume_all_ai` · `emergency_stop` · `get_ticket_stats` ·
`list_recent_tickets` · `escalate_urgent_tickets` · `create_ticket` ·
`get_subscription_info` · `list_integrations` · `show_recent_errors`

Still demo-only (need product decision before going live, e.g. money
actions): `process_refund`, `upgrade_plan`, `cancel_subscription`,
`get_transaction_history`, `search_knowledge_base`, `batch_solve_tickets`,
`generate_fake_requests`.

## Tests

```bash
npm run test:live   # deterministic executor→backend test (no LLM, CI-safe)
npm run test        # LLM tool-picking suite (needs SDK credentials)
npm run test:llm    # quick LLM function-calling sanity check
```

`test:live` is part of GitHub Actions CI (boots a real backend, registers a
user, and asserts every wired executor returns live data).
