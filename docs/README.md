# PARWA Documentation

> Production-ready documentation for the PARWA AI Customer Support Platform

---

## Folder Structure

```
docs/
├── README.md                    # This file
├── architecture/                # System architecture documents
│   ├── MASTER_DOCUMENT.md       # Complete product documentation
│   ├── FRONTEND_DOCUMENTATION.md # Frontend architecture
│   ├── BACKEND_DOCUMENTATION.md  # Backend architecture
│   ├── INFRASTRUCTURE_DOCUMENTATION.md # Infrastructure setup
│   ├── CONNECTION_MAP.md        # Feature connections & dependencies
│   └── LLM_TIERED_ROUTING_SYSTEM.md # AI model routing
├── specifications/              # Feature & technique specifications
│   ├── CONTEXT_BIBLE.md         # Complete project context
│   ├── AI_TECHNIQUE_FRAMEWORK.md # 3-tier AI reasoning techniques
│   ├── BUILDING_CODES.md        # 12 reusable rule sets
│   ├── UI_ADDITIONAL_FEATURES.md # UI feature specifications
│   └── FEATURE_SPECS_BATCH1-10.md # Detailed feature blueprints
├── roadmaps/                    # Development roadmaps
│   ├── MAIN_ROADMAP.md          # Primary development roadmap
│   ├── BUILD_ROADMAP.md         # Build phases & milestones
│   ├── PHASE3_AI_ENGINE_ROADMAP.md # AI engine development
│   ├── JARVIS_ROADMAP.md        # Jarvis command center
│   ├── WEEK3_ROADMAP.md         # Week 3 sprint plan
│   ├── WEEK4_ROADMAP.md         # Week 4 sprint plan
│   └── WEEK5_PAYMENT_ROADMAP.md  # Payment integration plan
├── features/                    # Feature-specific documentation
│   ├── JARVIS_SPECIFICATION.md  # Jarvis command center spec
│   └── ONBOARDING_SPEC.md       # Onboarding flow spec
├── planning/                    # Planning & project management
│   ├── BUILD_AGENT_PROMPT.md    # Agent build instructions
│   ├── PROJECT_STATE.md         # Current project state
│   ├── PROJECT_STATUS.md        # Project status tracking
│   ├── IMPLEMENTATION_PLAN_ONBOARDING.md # Onboarding implementation
│   ├── ONBOARDING_SPRINT.md     # Sprint planning
│   ├── ONBOARDING_SPRINT_CHECKPOINT.md # Sprint checkpoints
│   ├── WEEK6_ONBOARDING_PLAN.md # Week 6 plan
│   ├── INFRASTRUCTURE_GAPS_TRACKER.md # Gap tracking
│   ├── DOCKER_DEPLOY_PROMPT.md  # Deployment guide
│   └── AGENT_COMMS.md           # Team communication log
└── archive/                     # Archived/historical documents
    ├── Day27_Production_Gaps_Analysis.md
    ├── PARWA_UI_Additional_Features (1).md
    ├── GAP_FIX_ROADMAP.md
    ├── WEEK4_SUMMARY.md
    └── testing_assistant.jsx
```

---

## Key Documents

### Start Here
1. **`specifications/CONTEXT_BIBLE.md`** - Complete project context. Read this first.
2. **`architecture/MASTER_DOCUMENT.md`** - Full product documentation
3. **`specifications/BUILDING_CODES.md`** - 12 foundational rules for all features

### For Development
- **`specifications/FEATURE_SPECS_BATCH1-10.md`** - Detailed blueprints for 139 features
- **`specifications/AI_TECHNIQUE_FRAMEWORK.md`** - 14 AI reasoning techniques
- **`architecture/CONNECTION_MAP.md`** - How features connect & depend on each other

### For Planning
- **`roadmaps/MAIN_ROADMAP.md`** - Primary development roadmap
- **`planning/PROJECT_STATE.md`** - Current project state
- **`planning/INFRASTRUCTURE_GAPS_TRACKER.md`** - Gap tracking

---

## Product Overview

**PARWA** is an AI-powered customer support platform with 500+ features (180+ AI features).

### Three Variants
| Variant | Price | Description |
|---------|-------|-------------|
| Mini PARWA | $999/mo | FAQs, ticket intake, up to 2 concurrent calls |
| PARWA | $2,499/mo | Resolves 70-80% autonomously, refund verification |
| PARWA High | $3,999/mo | Complex cases, strategic insights, up to 5 calls |

### Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** Next.js + Tailwind CSS
- **Database:** PostgreSQL + pgvector
- **Cache/Queue:** Redis + Celery
- **Real-time:** Socket.io
- **Billing:** Paddle
- **Email:** Brevo
- **SMS/Voice:** Twilio
- **AI:** LiteLLM/OpenRouter + DSPy + LangGraph

---

## Build Teams (6 Teams)

1. **Team 1: Platform & Infrastructure** - Foundation (Week 1-4)
2. **Team 2: Core Engine** - Tickets & Approval (Week 5-8)
3. **Team 3: AI/ML** - The Brain (Week 9-12)
4. **Team 4: Channels & Integrations** (Week 9-12)
5. **Team 5: Billing & Growth** (Week 3-4+)
6. **Team 6: Analytics, Jarvis & Training** (Week 13+)

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | April 2026 | Initial production-ready structure |

---

**For questions or updates, contact the PARWA development team.**
