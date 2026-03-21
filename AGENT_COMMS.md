# AGENT_COMMS.md — Week 9 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 9 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 9 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-21

> **Phase: Phase 3 — Variants & Integrations (Mini PARWA + Base Agents)**
>
> **⚠️ CRITICAL: Week 9 is SEQUENTIAL — NOT fully parallel!**
> - Day 1 builds `base_agent.py` which ALL other agents inherit from
> - Days 2, 3, 4 MUST wait for Day 1 to complete and push before starting
> - Day 5 MUST wait for Days 3-4 to complete (depends on Mini agents)
>
> **Week 9 Goals:**
> - Day 1: Base agent abstract + 7 base agent types (sequential within day)
> - Day 2: Base refund agent + Mini config + anti-arbitrage config
> - Day 3: Mini FAQ + Email + Chat + SMS agents
> - Day 4: Mini Voice + Ticket + Escalation + Refund agents
> - Day 5: Mini tools + workflows (10 files)
> - Day 6: Tester Agent runs full week validation
>
> **CRITICAL RULES:**
> 1. Day 1 MUST complete and push BEFORE Days 2-4 start
> 2. Within-day files CAN depend on each other — build in order listed
> 3. No Docker — use mocked sessions in tests
> 4. Build → Unit Test passes → THEN push (ONE push per file)
> 5. Type hints on ALL functions, docstrings on ALL classes/functions
> 6. **REFUND GATE IS SACRED** — Stripe/Paddle must NEVER be called without pending_approval
> 7. Mini FAQ must route to Light tier
> 8. Escalation must trigger human handoff

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Base Agent Abstract + Core Base Agents
═══════════════════════════════════════════════════════════════════════════════

**⚠️ YOU MUST COMPLETE AND PUSH BEFORE BUILDERS 2-4 CAN START**

### Field 1: Files to Build (in order)
1. `variants/__init__.py`
2. `variants/base_agents/__init__.py`
3. `variants/base_agents/base_agent.py`
4. `variants/base_agents/base_faq_agent.py`
5. `variants/base_agents/base_email_agent.py`
6. `variants/base_agents/base_chat_agent.py`
7. `variants/base_agents/base_sms_agent.py`
8. `variants/base_agents/base_voice_agent.py`
9. `variants/base_agents/base_ticket_agent.py`
10. `variants/base_agents/base_escalation_agent.py`
11. `tests/unit/test_base_agents.py`

### Field 2: What is each file?
1. `variants/__init__.py` — Module init for variants package
2. `variants/base_agents/__init__.py` — Module init for base agents
3. `variants/base_agents/base_agent.py` — Abstract base class for all PARWA agents
4. `variants/base_agents/base_faq_agent.py` — Base class for FAQ-handling agents
5. `variants/base_agents/base_email_agent.py` — Base class for email-processing agents
6. `variants/base_agents/base_chat_agent.py` — Base class for chat agents
7. `variants/base_agents/base_sms_agent.py` — Base class for SMS agents
8. `variants/base_agents/base_voice_agent.py` — Base class for voice/call agents
9. `variants/base_agents/base_ticket_agent.py` — Base class for ticket management agents
10. `variants/base_agents/base_escalation_agent.py` — Base class for escalation agents
11. `tests/unit/test_base_agents.py` — Unit tests for all base agents

### Field 3: Responsibilities

**variants/base_agents/base_agent.py:**
- `BaseAgent` abstract class with:
  - `__init__(self, agent_id: str, config: dict, company_id: UUID)` — Initialize agent
  - `async process(self, input_data: dict) -> AgentResponse` — Abstract method to process input
  - `async health_check(self) -> dict` — Return agent health status
  - `get_confidence(self, result: dict) -> float` — Calculate confidence score
  - `should_escalate(self, confidence: float, context: dict) -> bool` — Determine if escalation needed
  - `log_action(self, action: str, details: dict) -> None` — Log agent actions
  - `validate_input(self, input_data: dict, schema: dict) -> bool` — Validate input against schema
  - `get_tier(self) -> str` — Return "light", "medium", or "heavy"
  - `get_variant(self) -> str` — Return "mini", "parwa", or "parwa_high"

**variants/base_agents/base_faq_agent.py:**
- `BaseFAQAgent(BaseAgent)` with:
  - `async search_faq(self, query: str) -> list[dict]` — Search FAQ database
  - `async get_faq_answer(self, faq_id: str) -> dict` — Get specific FAQ answer
  - `async process(self, input_data: dict) -> AgentResponse` — Process FAQ query

**variants/base_agents/base_email_agent.py:**
- `BaseEmailAgent(BaseAgent)` with:
  - `async parse_email(self, email_content: str) -> dict` — Parse email content
  - `async extract_intent(self, parsed_email: dict) -> str` — Extract user intent
  - `async process(self, input_data: dict) -> AgentResponse` — Process email

**variants/base_agents/base_chat_agent.py:**
- `BaseChatAgent(BaseAgent)` with:
  - `async handle_message(self, message: str, context: dict) -> dict` — Handle chat message
  - `async get_conversation_context(self, session_id: str) -> dict` — Get conversation context
  - `async process(self, input_data: dict) -> AgentResponse` — Process chat input

**variants/base_agents/base_sms_agent.py:**
- `BaseSMSAgent(BaseAgent)` with:
  - `async parse_sms(self, sms_content: str) -> dict` — Parse SMS content
  - `async send_response(self, to: str, message: str) -> dict` — Send SMS response
  - `async process(self, input_data: dict) -> AgentResponse` — Process SMS

**variants/base_agents/base_voice_agent.py:**
- `BaseVoiceAgent(BaseAgent)` with:
  - `async transcribe(self, audio_url: str) -> str` — Transcribe voice to text
  - `async synthesize(self, text: str) -> str` — Synthesize text to voice
  - `async process(self, input_data: dict) -> AgentResponse` — Process voice input

**variants/base_agents/base_ticket_agent.py:**
- `BaseTicketAgent(BaseAgent)` with:
  - `async create_ticket(self, data: dict) -> dict` — Create support ticket
  - `async update_ticket(self, ticket_id: str, updates: dict) -> dict` — Update ticket
  - `async process(self, input_data: dict) -> AgentResponse` — Process ticket request

**variants/base_agents/base_escalation_agent.py:**
- `BaseEscalationAgent(BaseAgent)` with:
  - `async check_escalation_needed(self, context: dict) -> bool` — Check if escalation needed
  - `async escalate(self, ticket_id: str, reason: str, context: dict) -> dict` — Escalate to human
  - `async process(self, input_data: dict) -> AgentResponse` — Process escalation check

### Field 4: Depends On
- `shared/confidence/scorer.py` (Wk6)
- `shared/confidence/thresholds.py` (Wk6)
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/logger.py` (Wk1)
- `shared/core_functions/security.py` (Wk3)

### Field 5: Expected Output
- `base_agent.py` initializes correctly with all abstract methods
- All base agent types inherit from `BaseAgent` correctly
- `get_tier()` returns appropriate tier for each agent type
- `get_variant()` returns appropriate variant
- `should_escalate()` correctly determines escalation based on confidence

### Field 6: Unit Test Files
- `tests/unit/test_base_agents.py`
  - Test: BaseAgent initializes with correct agent_id and company_id
  - Test: BaseAgent.health_check returns valid status
  - Test: BaseFAQAgent inherits from BaseAgent
  - Test: BaseEmailAgent inherits from BaseAgent
  - Test: BaseChatAgent inherits from BaseAgent
  - Test: BaseSMSAgent inherits from BaseAgent
  - Test: BaseVoiceAgent inherits from BaseAgent
  - Test: BaseTicketAgent inherits from BaseAgent
  - Test: BaseEscalationAgent inherits from BaseAgent
  - Test: get_confidence returns float between 0 and 1
  - Test: should_escalate returns True when confidence < threshold

### Field 7: BDD Scenario
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Agent processes FAQ query
- `docs/bdd_scenarios/parwa_bdd.md` — Scenario: Agent escalates to human

### Field 8: Error Handling
- `ValueError` — Return {"status": "error", "message": "Invalid input"}
- `ConnectionError` — Return {"status": "error", "message": "Service unavailable"}
- `TimeoutError` — Return {"status": "error", "message": "Request timeout"}
- All exceptions logged with context

### Field 9: Security Requirements
- Validate all input parameters before processing
- Company isolation — agents must only access company-scoped data
- No hardcoded credentials
- Audit log all agent actions

### Field 10: Integration Points
- `shared/confidence/scorer.py` — Confidence calculation
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/logger.py` — Logging
- `shared/core_functions/security.py` — Security utilities

### Field 11: Code Quality
- Type hints on ALL functions and methods
- Docstrings on all classes and public methods (Google style)
- PEP 8 compliant
- Max 40 lines per function
- Run `black` and `flake8` before commit

### Field 12: GitHub CI Requirements
- pytest must pass on all test files
- flake8 must pass with no errors
- black --check must pass
- CI must be green before reporting DONE

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 11 files built and pushed to GitHub
- All unit tests pass (`pytest tests/unit/test_base_agents.py -v`)
- GitHub CI shows GREEN for all commits
- Each file has its own commit with descriptive message

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Base Refund Agent + Mini Config
═══════════════════════════════════════════════════════════════════════════════

**⚠️ WAIT FOR BUILDER 1 TO PUSH base_agent.py BEFORE STARTING**

### Field 1: Files to Build (in order)
1. `variants/base_agents/base_refund_agent.py`
2. `variants/mini/__init__.py`
3. `variants/mini/config.py`
4. `variants/mini/anti_arbitrage_config.py`
5. `tests/unit/test_base_refund_agent.py`
6. `tests/unit/test_mini_config.py`

### Field 2: What is each file?
1. `variants/base_agents/base_refund_agent.py` — Base class for refund-handling agents with approval gate
2. `variants/mini/__init__.py` — Module init for Mini PARWA variant
3. `variants/mini/config.py` — Configuration for Mini PARWA variant
4. `variants/mini/anti_arbitrage_config.py` — Anti-arbitrage pricing configuration for Mini
5. `tests/unit/test_base_refund_agent.py` — Unit tests for base refund agent
6. `tests/unit/test_mini_config.py` — Unit tests for Mini config

### Field 3: Responsibilities

**variants/base_agents/base_refund_agent.py:**
- `BaseRefundAgent(BaseAgent)` with:
  - `async verify_refund_eligibility(self, order_id: str) -> dict` — Check if refund eligible
  - `async create_pending_approval(self, refund_data: dict) -> dict` — **CRITICAL: Creates pending_approval record, does NOT call Stripe/Paddle**
  - `async check_approval_status(self, approval_id: str) -> str` — Check approval status
  - `async process(self, input_data: dict) -> AgentResponse` — Process refund request
  - `get_refund_recommendation(self, refund_data: dict) -> str` — Return "APPROVE", "REVIEW", or "DENY"

**variants/mini/config.py:**
- `MiniConfig` class with:
  - `max_concurrent_calls: int = 2` — Mini supports max 2 concurrent calls
  - `supported_channels: list[str] = ["faq", "email", "chat", "sms"]` — Supported channels
  - `escalation_threshold: float = 0.70` — Escalate when confidence < 70%
  - `refund_limit: float = 50.0` — Max refund amount Mini can recommend
  - `get_variant_name() -> str` — Returns "Mini PARWA"

**variants/mini/anti_arbitrage_config.py:**
- `AntiArbitrageConfig` class with:
  - `mini_hourly_rate: float` — Mini PARWA hourly cost
  - `manager_hourly_rate: float` — Human manager hourly cost
  - `calculate_manager_time(self, complexity: float) -> float` — Calculate time saved
  - `calculate_roi(self, queries_handled: int, manager_time_saved: float) -> float` — Calculate ROI
  - `validate_pricing(self, subscription_tier: str) -> bool` — Validate pricing is anti-arbitrage

### Field 4: Depends On
- `variants/base_agents/base_agent.py` (Wk9 D1) — **MUST WAIT FOR BUILDER 1**
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/pricing_optimizer.py` (Wk1)
- `shared/compliance/jurisdiction.py` (Wk7)

### Field 5: Expected Output
- `base_refund_agent.py` creates pending_approval records, NEVER calls Stripe/Paddle directly
- `MiniConfig` loads with correct limits (2 concurrent calls, $50 refund limit)
- `AntiArbitrageConfig` calculates ROI correctly
- Refund recommendation returns APPROVE/REVIEW/DENY

### Field 6: Unit Test Files
- `tests/unit/test_base_refund_agent.py`
  - Test: BaseRefundAgent creates pending_approval record
  - Test: **CRITICAL: Stripe/Paddle NOT called directly**
  - Test: get_refund_recommendation returns APPROVE for valid refund
  - Test: get_refund_recommendation returns DENY for fraud indicators
  - Test: get_refund_recommendation returns REVIEW for edge cases
- `tests/unit/test_mini_config.py`
  - Test: MiniConfig loads with correct defaults
  - Test: max_concurrent_calls = 2
  - Test: escalation_threshold = 0.70
  - Test: refund_limit = 50.0

### Field 7: BDD Scenario
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Refund request creates pending approval
- `docs/bdd_scenarios/parwa_bdd.md` — Scenario: Refund gate enforced

### Field 8: Error Handling
- `RefundError` — Log and return {"status": "error", "message": "Refund processing failed"}
- `ApprovalError` — Log and return {"status": "error", "message": "Approval creation failed"}
- **NEVER** allow refund to proceed without approval

### Field 9: Security Requirements
- **CRITICAL:** Refund gate — Stripe/Paddle must NEVER be called without pending_approval
- All refund attempts must be logged for audit
- Anti-fraud checks before creating approval

### Field 10: Integration Points
- `variants/base_agents/base_agent.py` — Inheritance
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/pricing_optimizer.py` — Pricing calculations

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- All unit tests pass
- **CRITICAL: Refund gate test passes (Stripe NOT called)**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Mini FAQ + Email + Chat + SMS Agents
═══════════════════════════════════════════════════════════════════════════════

**⚠️ WAIT FOR BUILDER 1 TO PUSH base_agent.py BEFORE STARTING**

### Field 1: Files to Build (in order)
1. `variants/mini/agents/__init__.py`
2. `variants/mini/agents/faq_agent.py`
3. `variants/mini/agents/email_agent.py`
4. `variants/mini/agents/chat_agent.py`
5. `variants/mini/agents/sms_agent.py`
6. `tests/unit/test_mini_agents.py`

### Field 2: What is each file?
1. `variants/mini/agents/__init__.py` — Module init for Mini agents
2. `variants/mini/agents/faq_agent.py` — Mini PARWA FAQ agent (routes to Light tier)
3. `variants/mini/agents/email_agent.py` — Mini PARWA email agent
4. `variants/mini/agents/chat_agent.py` — Mini PARWA chat agent
5. `variants/mini/agents/sms_agent.py` — Mini PARWA SMS agent
6. `tests/unit/test_mini_agents.py` — Unit tests for Mini agents

### Field 3: Responsibilities

**variants/mini/agents/faq_agent.py:**
- `MiniFAQAgent(BaseFAQAgent)` with:
  - `get_tier() -> str` — Returns "light" (Mini always uses Light tier)
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Process FAQ, escalate if complex
  - `should_escalate(self, confidence: float, context: dict) -> bool` — Escalate if confidence < 70%

**variants/mini/agents/email_agent.py:**
- `MiniEmailAgent(BaseEmailAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Process email, escalate if needed

**variants/mini/agents/chat_agent.py:**
- `MiniChatAgent(BaseChatAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Process chat message

**variants/mini/agents/sms_agent.py:**
- `MiniSMSAgent(BaseSMSAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Process SMS

### Field 4: Depends On
- `variants/base_agents/base_faq_agent.py` (Wk9 D1)
- `variants/base_agents/base_email_agent.py` (Wk9 D1)
- `variants/base_agents/base_chat_agent.py` (Wk9 D1)
- `variants/base_agents/base_sms_agent.py` (Wk9 D1)
- `variants/mini/config.py` (Wk9 D2)

### Field 5: Expected Output
- All Mini agents inherit from correct base agents
- `get_tier()` returns "light" for all Mini agents
- `get_variant()` returns "mini"
- Agents escalate when confidence < 70%

### Field 6: Unit Test Files
- `tests/unit/test_mini_agents.py`
  - Test: MiniFAQAgent.get_tier() returns "light"
  - Test: MiniFAQAgent.get_variant() returns "mini"
  - Test: MiniFAQAgent routes simple FAQ to Light tier
  - Test: MiniFAQAgent escalates complex queries
  - Test: MiniEmailAgent processes email correctly
  - Test: MiniChatAgent handles chat message
  - Test: MiniSMSAgent processes SMS
  - Test: All Mini agents escalate when confidence < 70%

### Field 7: BDD Scenario
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: FAQ query handled by Mini
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Complex query escalated

### Field 8: Error Handling
- Standard error handling with logging
- All errors return AgentResponse with status="error"
- Escalate on unrecoverable errors

### Field 9: Security Requirements
- Input validation on all agent inputs
- Company isolation enforced
- No PII in logs

### Field 10: Integration Points
- Base agents from Day 1
- Mini config from Day 2
- Smart Router (Wk5) for tier routing

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- All unit tests pass
- GitHub CI GREEN
- Mini agents route to Light tier

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Mini Voice + Ticket + Escalation + Refund Agents
═══════════════════════════════════════════════════════════════════════════════

**⚠️ WAIT FOR BUILDER 1 TO PUSH base_agent.py BEFORE STARTING**

### Field 1: Files to Build (in order)
1. `variants/mini/agents/voice_agent.py`
2. `variants/mini/agents/ticket_agent.py`
3. `variants/mini/agents/escalation_agent.py`
4. `variants/mini/agents/refund_agent.py`
5. `tests/unit/test_mini_agents.py` (update with new tests)

### Field 2: What is each file?
1. `variants/mini/agents/voice_agent.py` — Mini PARWA voice agent (max 2 concurrent calls)
2. `variants/mini/agents/ticket_agent.py` — Mini PARWA ticket agent
3. `variants/mini/agents/escalation_agent.py` — Mini PARWA escalation agent (triggers human handoff)
4. `variants/mini/agents/refund_agent.py` — Mini PARWA refund agent ($50 limit, creates pending_approval)
5. `tests/unit/test_mini_agents.py` — Unit tests updated for new agents

### Field 3: Responsibilities

**variants/mini/agents/voice_agent.py:**
- `MiniVoiceAgent(BaseVoiceAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `max_concurrent_calls: int = 2` — Mini supports max 2 calls
  - `async process(self, input_data: dict) -> AgentResponse` — Process voice call
  - `can_accept_call(self) -> bool` — Check if can accept new call

**variants/mini/agents/ticket_agent.py:**
- `MiniTicketAgent(BaseTicketAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Create ticket
  - `async create_ticket(self, data: dict) -> dict` — Create support ticket

**variants/mini/agents/escalation_agent.py:**
- `MiniEscalationAgent(BaseEscalationAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `async process(self, input_data: dict) -> AgentResponse` — Check and trigger escalation
  - `async escalate(self, ticket_id: str, reason: str, context: dict) -> dict` — **Triggers human handoff**
  - `get_escalation_channel(self, context: dict) -> str` — Determine escalation channel

**variants/mini/agents/refund_agent.py:**
- `MiniRefundAgent(BaseRefundAgent)` with:
  - `get_tier() -> str` — Returns "light"
  - `get_variant() -> str` — Returns "mini"
  - `refund_limit: float = 50.0` — Max refund Mini can recommend
  - `async process(self, input_data: dict) -> AgentResponse` — Process refund request
  - `async create_pending_approval(self, refund_data: dict) -> dict` — **Creates pending_approval, NEVER calls Stripe/Paddle**
  - `validate_refund_amount(self, amount: float) -> bool` — Check if within $50 limit

### Field 4: Depends On
- `variants/base_agents/base_voice_agent.py` (Wk9 D1)
- `variants/base_agents/base_ticket_agent.py` (Wk9 D1)
- `variants/base_agents/base_escalation_agent.py` (Wk9 D1)
- `variants/base_agents/base_refund_agent.py` (Wk9 D2)
- `variants/mini/config.py` (Wk9 D2)

### Field 5: Expected Output
- Voice agent respects 2 concurrent call limit
- Ticket agent creates tickets correctly
- Escalation agent triggers human handoff
- Refund agent creates pending_approval for amounts <= $50
- Refund agent escalates amounts > $50

### Field 6: Unit Test Files
- `tests/unit/test_mini_agents.py` (update)
  - Test: MiniVoiceAgent can_accept_call respects limit
  - Test: MiniTicketAgent creates ticket
  - Test: MiniEscalationAgent triggers human handoff
  - Test: MiniRefundAgent creates pending_approval for $30 refund
  - Test: MiniRefundAgent escalates $100 refund (over $50 limit)
  - Test: **CRITICAL: MiniRefundAgent never calls Stripe/Paddle**

### Field 7: BDD Scenario
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Voice call handled
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Escalation triggers human handoff
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Refund under $50 approved
- `docs/bdd_scenarios/mini_parwa_bdd.md` — Scenario: Refund over $50 escalated

### Field 8: Error Handling
- Standard error handling with logging
- Voice call errors: log and return error response
- Escalation errors: log and retry via alternative channel
- Refund errors: log and create pending_approval for manual review

### Field 9: Security Requirements
- **CRITICAL:** Refund gate enforced — no direct Stripe/Paddle calls
- Voice call limit enforced (2 max)
- Audit log all escalations
- Audit log all refund requests

### Field 10: Integration Points
- Base agents from Days 1-2
- Mini config from Day 2
- Twilio client (Wk7) for voice
- Ticket system (Wk4) for tickets

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 5 files built and pushed
- All unit tests pass
- **CRITICAL: Refund gate test passes**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Mini Tools + Workflows
═══════════════════════════════════════════════════════════════════════════════

**⚠️ WAIT FOR BUILDERS 3-4 TO COMPLETE BEFORE STARTING**

### Field 1: Files to Build (in order)
1. `variants/mini/tools/__init__.py`
2. `variants/mini/tools/faq_search.py`
3. `variants/mini/tools/order_lookup.py`
4. `variants/mini/tools/ticket_create.py`
5. `variants/mini/tools/notification.py`
6. `variants/mini/tools/refund_verification_tools.py`
7. `variants/mini/workflows/__init__.py`
8. `variants/mini/workflows/inquiry.py`
9. `variants/mini/workflows/ticket_creation.py`
10. `variants/mini/workflows/escalation.py`
11. `variants/mini/workflows/order_status.py`
12. `variants/mini/workflows/refund_verification.py`
13. `tests/unit/test_mini_workflows.py`

### Field 2: What is each file?
1. `variants/mini/tools/__init__.py` — Module init for Mini tools
2. `variants/mini/tools/faq_search.py` — FAQ search tool
3. `variants/mini/tools/order_lookup.py` — Order lookup tool (Shopify)
4. `variants/mini/tools/ticket_create.py` — Ticket creation tool
5. `variants/mini/tools/notification.py` — Notification tool (Twilio)
6. `variants/mini/tools/refund_verification_tools.py` — Refund verification (creates pending_approval)
7. `variants/mini/workflows/__init__.py` — Module init for workflows
8. `variants/mini/workflows/inquiry.py` — Inquiry handling workflow
9. `variants/mini/workflows/ticket_creation.py` — Ticket creation workflow
10. `variants/mini/workflows/escalation.py` — Escalation workflow
11. `variants/mini/workflows/order_status.py` — Order status workflow
12. `variants/mini/workflows/refund_verification.py` — Refund verification workflow
13. `tests/unit/test_mini_workflows.py` — Unit tests for workflows

### Field 3: Responsibilities

**variants/mini/tools/faq_search.py:**
- `FAQSearchTool` with:
  - `async search(self, query: str, limit: int = 5) -> list[dict]` — Search FAQs
  - `async get_by_id(self, faq_id: str) -> dict` — Get FAQ by ID

**variants/mini/tools/order_lookup.py:**
- `OrderLookupTool` with:
  - `async lookup(self, order_id: str) -> dict` — Lookup order by ID
  - `async lookup_by_customer(self, customer_id: str) -> list[dict]` — Get customer orders

**variants/mini/tools/ticket_create.py:**
- `TicketCreateTool` with:
  - `async create(self, subject: str, description: str, priority: str) -> dict` — Create ticket

**variants/mini/tools/notification.py:**
- `NotificationTool` with:
  - `async send_sms(self, to: str, message: str) -> dict` — Send SMS notification
  - `async send_email(self, to: str, subject: str, body: str) -> dict` — Send email notification

**variants/mini/tools/refund_verification_tools.py:**
- `RefundVerificationTool` with:
  - `async verify_eligibility(self, order_id: str) -> dict` — Check refund eligibility
  - `async create_approval_request(self, refund_data: dict) -> dict` — **Creates pending_approval, NEVER processes refund**
  - `get_recommendation(self, refund_data: dict) -> str` — Return APPROVE/REVIEW/DENY

**variants/mini/workflows/inquiry.py:**
- `InquiryWorkflow` with:
  - `async execute(self, inquiry_data: dict) -> dict` — Handle customer inquiry
  - Steps: Classify → Search FAQ → Respond or Escalate

**variants/mini/workflows/ticket_creation.py:**
- `TicketCreationWorkflow` with:
  - `async execute(self, ticket_data: dict) -> dict` — Create ticket workflow
  - Steps: Validate → Create → Notify

**variants/mini/workflows/escalation.py:**
- `EscalationWorkflow` with:
  - `async execute(self, context: dict) -> dict` — Escalation workflow
  - Steps: Log escalation → Notify human → Update ticket

**variants/mini/workflows/order_status.py:**
- `OrderStatusWorkflow` with:
  - `async execute(self, order_id: str) -> dict` — Get order status
  - Steps: Lookup order → Format response → Return

**variants/mini/workflows/refund_verification.py:**
- `RefundVerificationWorkflow` with:
  - `async execute(self, refund_data: dict) -> dict` — Refund verification workflow
  - Steps: Verify eligibility → Check amount limit → Create pending_approval → Return recommendation

### Field 4: Depends On
- Mini agents from Days 3-4
- `shared/integrations/shopify_client.py` (Wk7)
- `shared/integrations/twilio_client.py` (Wk7)
- `shared/integrations/email_client.py` (Wk7)

### Field 5: Expected Output
- All tools work with mocked external services
- All workflows complete their steps
- Refund workflow creates pending_approval, never processes refund
- Escalation workflow triggers human handoff

### Field 6: Unit Test Files
- `tests/unit/test_mini_workflows.py`
  - Test: InquiryWorkflow handles FAQ inquiry
  - Test: InquiryWorkflow escalates complex inquiry
  - Test: TicketCreationWorkflow creates ticket
  - Test: EscalationWorkflow triggers human handoff
  - Test: OrderStatusWorkflow returns order status
  - Test: RefundVerificationWorkflow creates pending_approval
  - Test: **CRITICAL: RefundVerificationWorkflow never calls Stripe/Paddle**

### Field 7: BDD Scenario
- `docs/bdd_scenarios/mini_parwa_bdd.md` — All Mini PARWA scenarios

### Field 8: Error Handling
- Standard error handling with logging
- Workflow failures log and return error status
- Refund failures create pending_approval for manual review

### Field 9: Security Requirements
- **CRITICAL:** No direct refund processing
- All external calls use proper clients
- Audit log all workflow actions

### Field 10: Integration Points
- Mini agents (Days 3-4)
- Shopify client (Wk7)
- Twilio client (Wk7)
- Email client (Wk7)

### Field 11: Code Quality
- Type hints on ALL functions
- Docstrings required
- PEP 8 compliant
- Max 40 lines per function

### Field 12: GitHub CI Requirements
- pytest pass
- flake8 pass
- black --check pass
- CI green

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 13 files built and pushed
- All unit tests pass
- **CRITICAL: Refund workflow never calls Stripe/Paddle**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 9 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Command
```bash
pytest tests/integration/test_week9_mini_variant.py -v
pytest tests/unit/test_base_agents.py -v
pytest tests/unit/test_base_refund_agent.py -v
pytest tests/unit/test_mini_config.py -v
pytest tests/unit/test_mini_agents.py -v
pytest tests/unit/test_mini_workflows.py -v
```

### Critical Tests to Verify
1. Mini PARWA: FAQ query routes to Light tier
2. Mini PARWA: refund request creates pending_approval — Stripe/Paddle NOT called
3. Mini PARWA: escalation triggers human handoff
4. All 8 base agents initialise without errors
5. Refund gate: CRITICAL — Stripe/Paddle must not be called without approval
6. Mini anti-arbitrage: 2x Mini cost shows manager time correctly
7. Voice agent: max 2 concurrent calls enforced

### Week 9 PASS Criteria
- Mini PARWA variant fully functional
- Refund gate verified: Stripe/Paddle NOT called without approval
- All base agents working
- All unit tests pass
- GitHub CI pipeline green

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ⏳ PENDING | Base agents (11 files) | - | NO |
| Builder 2 | Day 2 | ⏳ WAITING D1 | Refund + Config (6 files) | - | NO |
| Builder 3 | Day 3 | ⏳ WAITING D1 | Mini agents (6 files) | - | NO |
| Builder 4 | Day 4 | ⏳ WAITING D1 | Mini agents (5 files) | - | NO |
| Builder 5 | Day 5 | ⏳ WAITING D3-D4 | Tools + Workflows (13 files) | - | NO |
| Tester | Day 6 | ⏳ WAITING ALL | Full validation | - | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. **Week 9 is SEQUENTIAL** — Day 1 MUST complete before Days 2-4 start
2. Within-day dependencies OK — build files in order listed
3. No Docker — mock everything in tests
4. One push per file — only after tests pass
5. Type hints + docstrings required on all functions
6. **REFUND GATE IS SACRED** — Stripe/Paddle must NEVER be called without pending_approval
7. Mini FAQ routes to Light tier
8. Mini refund limit: $50 (escalate higher amounts)
9. Mini voice: max 2 concurrent calls
10. Mini escalates when confidence < 70%

---

═══════════════════════════════════════════════════════════════════════════════
## EXECUTION ORDER
═══════════════════════════════════════════════════════════════════════════════

```
Week 9 Sequential Execution:

Day 1: Builder 1 → Build base_agent.py + 7 base agents → PUSH
         ↓
Days 2-4: Builders 2, 3, 4 → Pull Day 1 → Build in PARALLEL → PUSH
         ↓
Day 5: Builder 5 → Pull Days 3-4 → Build tools + workflows → PUSH
         ↓
Day 6: Tester → Full validation → Report PASS/FAIL
```

**Builder 1: You may start NOW.**

**Builders 2-4: WAIT for Builder 1 to report DONE and push.**

**Builder 5: WAIT for Builders 3-4 to report DONE.**

---

═══════════════════════════════════════════════════════════════════════════════
## MINI PARWA LIMITS SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Feature | Mini PARWA Limit |
|---------|------------------|
| Concurrent Calls | 2 max |
| Supported Channels | FAQ, Email, Chat, SMS |
| Refund Limit | $50 (escalate higher) |
| Escalation Threshold | Confidence < 70% |
| AI Tier | Light only |
| Refund Processing | Creates pending_approval only |
