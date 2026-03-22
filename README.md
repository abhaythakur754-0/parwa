# PARWA
### Complete AI Workforce System for Customer Care

> **PARWA** is not a chatbot. It is a complete AI team that assists your support staff, learns your business logic, and earns autonomy under full human control — all while running at near-zero inference cost via OpenRouter's free-tier models.

---

## What PARWA Does

| Capability | How |
|---|---|
| Handles 60–90% of support tickets | Chat, Email, Social, SMS, Voice |
| Never makes irreversible decisions alone | Every refund/change requires human approval |
| Gets smarter every week | Agent Lightning — continuous fine-tuning from manager corrections |
| Costs ~$0 for AI inference | Smart Router uses free-tier LLMs via OpenRouter |
| Full audit trail | Every action logged with SHA-256 hash chain |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    JARVIS (Control OS)                  │
│          Natural language interface for managers        │
└─────────────────┬───────────────────────────────────────┘
                  │
     ┌────────────▼────────────┐
     │      Smart Router       │  Light → Medium → Heavy LLMs
     │   (Complexity Scorer)   │  via OpenRouter Free Tier
     └────────────┬────────────┘
                  │
     ┌────────────▼────────────┐
     │    GSD State Engine     │  ~200 tokens vs 10,000+ (98% cost savings)
     │   (LangGraph + DSPy)    │  Zero hallucination, infinite chats
     └────────────┬────────────┘
                  │
     ┌────────────▼────────────┐
     │    TRIVYA Techniques    │  CLARA, CRP, Chain-of-Thought, ReAct, etc.
     │    Knowledge Base (RAG) │  Qdrant vector store, HyDE, Multi-Query
     └────────────┬────────────┘
                  │
     ┌────────────▼────────────┐
     │   Agent Lightning       │  50-mistake threshold → auto fine-tune
     │   (Unsloth + Colab)     │  Weekly training loop, model versioning
     └─────────────────────────┘
```

---

## Quick Start (3 Commands)

```bash
# 1. Clone and set up environment
cp .env.example .env
# Fill in your API keys in .env

# 2. Start everything
make dev

# 3. Verify it's running
curl http://localhost:8000/health
# → {"status": "ok", "db": "connected", "redis": "connected"}
```

**Frontend:** [http://localhost:3000](http://localhost:3000)
**Backend API:** [http://localhost:8000](http://localhost:8000)
**API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Make Commands

| Command | What It Does |
|---|---|
| `make dev` | Start all 5 services (DB, Redis, Backend, Worker, Frontend) |
| `make down` | Stop all containers |
| `make test` | Run unit tests |
| `make test-integration` | Run Day 6 weekly integration test |
| `make test-coverage` | Unit tests with coverage report (target >80%) |
| `make migrate` | Run database migrations |
| `make seed` | Seed database with sample data |
| `make lint` | Ruff + mypy checks |
| `make format` | Black + isort auto-format |
| `make reset` | ⚠️ Destroy all containers + data (dev only) |
| `make help` | Show all commands |

---

## Product Variants

| Variant | Price | Key Features |
|---|---|---|
| **Mini PARWA** | $1,000/mo | FAQ deflection, 2 voice slots, data collection |
| **PARWA** | $2,500/mo | Full recommendations, Agent Lightning, peer review |
| **PARWA High** | $4,000/mo | Quality Coach, strategic BI, video, churn prediction |

---

## Environment Variables

See [`.env.example`](.env.example) for the full reference — all variables are grouped and documented.

**Minimum required to start:**
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `OPENROUTER_API_KEY` — Free at [openrouter.ai](https://openrouter.ai)
- `JWT_SECRET_KEY` — Any 32+ character random string
- `SECRET_KEY` — Any 32+ character random string

---

## Testing

```bash
make test                 # Unit tests (run on every commit via CI)
make test-integration     # Integration tests (run Day 6 every week)
make test-e2e             # End-to-end journeys (run after each phase)
make test-security        # RLS + HMAC + rate limiting tests
```

See [`product/testing.md`](product/testing.md) for the complete testing guide.

---

## Project Structure

```
parwa/
├── shared/           → Core functions, GSD engine, Smart Router, KB, TRIVYA
├── backend/          → FastAPI app, API routes, models, services, workers
├── frontend/         → Next.js dashboard (Jarvis UI)
├── mobile/           → React Native app (Week 47+)
├── database/         → Schema, migrations (Alembic), seed data
├── infra/            → Docker, Kubernetes, Terraform, CI/CD scripts
├── tests/            → Unit, integration, e2e, performance, security
├── docs/             → Architecture decisions, BDD scenarios, runbooks
├── legal/            → Privacy policy, ToS, DPA, TCPA guide
├── compliance/       → SOC 2, GDPR evidence collection
├── feature_flags/    → Per-variant capability control (JSON)
└── scripts/          → Utility scripts
```

---

## Agent Team Structure

| Agent | Role |
|---|---|
| **Manager Agent** (Antigravity) | Plans, assigns, monitors, fixes — 60 weeks |
| **Builder Agents** (×4) | Build one file per day, test until green, push once |
| **Tester Agent** | Verifies every file, runs Day 6 integration tests |
| **Assistance Agent** | Daily user-facing summary, schedule status |

---

## Build Roadmap

- **Phase 1 (Weeks 1–4):** Foundation & Infrastructure
- **Phase 2 (Weeks 5–10):** Core AI Engine
- **Phase 3 (Weeks 11–16):** PARWA Variants
- **Phase 4 (Weeks 17–22):** Billing & Business Logic
- **Phase 5 (Weeks 23–30):** Agent Lightning
- **Phase 6 (Weeks 31–40):** Industry Specialization
- **Phase 7 (Weeks 41–60):** Enterprise & Scale

See [`product/PARWA_Parallel_Agent_Roadmap_v7.md`](product/PARWA_Parallel_Agent_Roadmap_v7.md) for the full 60-week plan.

---

*Built with the Parallel Agent System — 4 builders working simultaneously, zero same-day dependencies.*
