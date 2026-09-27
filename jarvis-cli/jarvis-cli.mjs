/**
 * PARWA Jarvis CLI — AI-Powered Command Line Interface
 *
 * This is how Jarvis ACTUALLY works — the user types naturally,
 * and an AI (LLM) understands what they want and picks the right
 * function to call. No pre-written pattern matching. The AI reads
 * the function definitions as "tools" and decides which one matches
 * the user's intent.
 *
 * Flow:
 *   1. User types a natural message (e.g., "show me my transaction history")
 *   2. Message + function definitions are sent to the LLM as a chat completion
 *   3. LLM picks the right function (tool) and returns a function_call
 *   4. We execute the function (mock for now)
 *   5. Result is fed back to LLM for a natural, conversational response
 *   6. Client sees a human-like response — they never know a function was called
 *
 * Usage:
 *   node jarvis-cli.mjs
 *   node jarvis-cli.mjs --test        (automated test suite)
 *   node jarvis-cli.mjs --chat        (interactive chat)
 */

import ZAI from 'z-ai-web-dev-sdk';

// ══════════════════════════════════════════════════════════════════
// FUNCTION DEFINITIONS — These are the "tools" the AI can use
// ══════════════════════════════════════════════════════════════════

const FUNCTION_DEFINITIONS = [
  // ── SYSTEM HEALTH ──
  {
    type: "function",
    function: {
      name: "check_system_health",
      description: "Check the current health of the system. Returns overall status (healthy/degraded/critical), channel health, error rate, uptime. Use when the user asks how things are going, system status, or if there are any issues.",
      parameters: { type: "object", properties: {}, required: [] }
    }
  },
  {
    type: "function",
    function: {
      name: "show_recent_errors",
      description: "Show recent system errors. Returns the last errors with type, timestamp, and affected component. Use when the user asks about errors, failures, or something going wrong.",
      parameters: {
        type: "object",
        properties: {
          count: { type: "integer", description: "Number of errors to show (default 10)", default: 10 },
          severity: { type: "string", enum: ["all", "warning", "error", "critical"], description: "Filter by severity", default: "all" }
        },
        required: []
      }
    }
  },
  // ── AI CONTROL ──
  {
    type: "function",
    function: {
      name: "pause_all_ai",
      description: "Pause all AI agent activity immediately. AI agents will stop handling tickets until resumed. Use when the user wants to stop AI, pause everything, or take manual control.",
      parameters: {
        type: "object",
        properties: { reason: { type: "string", description: "Why AI is being paused (for audit)" } },
        required: ["reason"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "resume_all_ai",
      description: "Resume AI agent activity after a pause. AI agents will start handling tickets again. Use when the user wants to turn AI back on or restart operations.",
      parameters: { type: "object", properties: {}, required: [] }
    }
  },
  {
    type: "function",
    function: {
      name: "emergency_stop",
      description: "Emergency shutdown — immediately pause ALL automated operations including AI agents, refund processing, and scheduled tasks. Use ONLY for emergencies.",
      parameters: {
        type: "object",
        properties: { reason: { type: "string", description: "Emergency reason (required)" } },
        required: ["reason"]
      }
    }
  },
  // ── TICKETS ──
  {
    type: "function",
    function: {
      name: "get_ticket_stats",
      description: "Get ticket statistics — volume, open/closed counts, average response time, resolution rate. Use when the user asks about tickets, workload, or support metrics.",
      parameters: {
        type: "object",
        properties: { time_range: { type: "string", enum: ["today", "this_week", "this_month", "all_time"], default: "today" } },
        required: []
      }
    }
  },
  {
    type: "function",
    function: {
      name: "list_recent_tickets",
      description: "List recent tickets with their status, priority, and category. Use when the user wants to see recent tickets, transaction history, check what's open, or get an overview of support activity.",
      parameters: {
        type: "object",
        properties: {
          status: { type: "string", enum: ["all", "open", "in_progress", "resolved", "closed"], default: "all" },
          limit: { type: "integer", description: "Max tickets to return (default 10)", default: 10 },
          priority: { type: "string", enum: ["all", "low", "medium", "high", "critical"], default: "all" }
        },
        required: []
      }
    }
  },
  {
    type: "function",
    function: {
      name: "escalate_urgent_tickets",
      description: "Escalate all urgent or high-priority tickets to human agents. Use when the user wants to make sure urgent issues get human attention.",
      parameters: {
        type: "object",
        properties: { priority: { type: "string", enum: ["urgent", "high", "critical"], default: "urgent" } },
        required: []
      }
    }
  },
  {
    type: "function",
    function: {
      name: "create_ticket",
      description: "Create a new support ticket. Use when the user wants to create a ticket, log a support issue, or report a problem.",
      parameters: {
        type: "object",
        properties: {
          subject: { type: "string", description: "Brief description of the issue" },
          message: { type: "string", description: "Detailed message about the issue" },
          priority: { type: "string", enum: ["low", "medium", "high", "critical"], default: "medium" },
          category: { type: "string", enum: ["tech_support", "billing", "returns_refunds", "order_tracking", "delivery_issues", "general"], default: "general" }
        },
        required: ["subject", "message"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "batch_solve_tickets",
      description: "Solve multiple tickets at once by routing them through the AI variant pipeline. Use when the user wants to batch solve, bulk resolve, or have AI handle multiple tickets.",
      parameters: {
        type: "object",
        properties: { max_tickets: { type: "integer", description: "Max tickets to solve (default 10)", default: 10 } },
        required: []
      }
    }
  },
  // ── BILLING ──
  {
    type: "function",
    function: {
      name: "get_subscription_info",
      description: "Get current subscription plan details — plan name, usage, limits, renewal date, billing status. Use when the user asks about their plan, billing, usage, subscription, or wants to upgrade.",
      parameters: { type: "object", properties: {}, required: [] }
    }
  },
  {
    type: "function",
    function: {
      name: "process_refund",
      description: "Process a refund for a customer. This is a MONETARY action. Use ONLY when the user explicitly requests a refund.",
      parameters: {
        type: "object",
        properties: {
          customer_id: { type: "string", description: "ID of the customer" },
          amount: { type: "number", description: "Refund amount" },
          reason: { type: "string", description: "Reason for refund" }
        },
        required: ["customer_id", "amount", "reason"]
      }
    }
  },
  // ── INTEGRATIONS ──
  {
    type: "function",
    function: {
      name: "list_integrations",
      description: "List all configured integrations — email, SMS, chat widget, etc. Show status and health. Use when the user asks about integrations or connected services.",
      parameters: { type: "object", properties: {}, required: [] }
    }
  },
  // ── ANALYTICS ──
  {
    type: "function",
    function: {
      name: "get_performance_metrics",
      description: "Get real-time performance metrics — response times, resolution rates, CSAT, AI accuracy, SLA compliance. Use when the user asks about performance or how well things are working.",
      parameters: {
        type: "object",
        properties: {
          metric: { type: "string", enum: ["all", "response_time", "resolution_rate", "csat", "ai_accuracy", "sla_compliance"], default: "all" }
        },
        required: []
      }
    }
  },
  // ── AGENTS ──
  {
    type: "function",
    function: {
      name: "get_agent_status",
      description: "Get the status of AI and human agents — how many are active, utilization, capacity. Use when the user asks about agents, capacity, or who's handling tickets.",
      parameters: { type: "object", properties: {}, required: [] }
    }
  },
  // ── KNOWLEDGE BASE ──
  {
    type: "function",
    function: {
      name: "search_knowledge_base",
      description: "Search the knowledge base for articles and FAQs. Use when the user wants to find information or documentation.",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
          limit: { type: "integer", description: "Max results (default 5)", default: 5 }
        },
        required: ["query"]
      }
    }
  },
  // ── FAKE REQUEST GENERATOR ──
  {
    type: "function",
    function: {
      name: "generate_fake_requests",
      description: "Generate fake customer support requests for testing. Use when the user wants to generate test data, simulate requests, or create fake tickets.",
      parameters: {
        type: "object",
        properties: {
          count: { type: "integer", description: "Number of requests (default 5)", default: 5 },
          category: { type: "string", enum: ["mixed", "tech_support", "billing", "returns_refunds", "order_tracking", "delivery_issues"], default: "mixed" }
        },
        required: []
      }
    }
  },
  // ── PLAN UPGRADE / CHANGE ──
  {
    type: "function",
    function: {
      name: "upgrade_plan",
      description: "Upgrade the current subscription plan to a higher tier. Available tiers: mini_parwa (starter), parwa (professional), parwa_high (enterprise). Use when the user wants to upgrade, change plan, move to a better plan, or get more features.",
      parameters: {
        type: "object",
        properties: {
          target_plan: { type: "string", enum: ["mini_parwa", "parwa", "parwa_high"], description: "The plan to upgrade to" },
          reason: { type: "string", description: "Why the upgrade is being requested (optional)" }
        },
        required: ["target_plan"]
      }
    }
  },
  // ── TRANSACTION HISTORY ──
  {
    type: "function",
    function: {
      name: "get_transaction_history",
      description: "Get the transaction/billing history — payments, refunds, credits, and charges. Shows amount, date, status, and description. Use when the user asks about transaction history, billing history, payment history, charges, invoices, or past payments.",
      parameters: {
        type: "object",
        properties: {
          period: { type: "string", enum: ["last_30_days", "last_90_days", "this_year", "all"], description: "Time period (default 'last_30_days')", default: "last_30_days" },
          transaction_type: { type: "string", enum: ["all", "payments", "refunds", "credits", "charges"], description: "Filter by type (default 'all')", default: "all" }
        },
        required: []
      }
    }
  },
  // ── CANCEL SUBSCRIPTION ──
  {
    type: "function",
    function: {
      name: "cancel_subscription",
      description: "Cancel the current subscription. This will schedule cancellation at the end of the billing period. Use when the user explicitly wants to cancel, end their subscription, or stop using the service. DESTRUCTIVE action.",
      parameters: {
        type: "object",
        properties: {
          reason: { type: "string", description: "Why the subscription is being cancelled" },
          immediate: { type: "boolean", description: "Cancel immediately instead of end of billing period (default false)", default: false }
        },
        required: ["reason"]
      }
    }
  },
];


// ══════════════════════════════════════════════════════════════════
// MOCK DATA — Simulated backend responses
// ══════════════════════════════════════════════════════════════════

const MOCK_TICKETS = [
  { id: "TKT-001", subject: "App keeps crashing on startup", status: "open", priority: "high", category: "tech_support", customer: "Sarah Johnson" },
  { id: "TKT-002", subject: "Charged twice for this month", status: "in_progress", priority: "high", category: "billing", customer: "Mike Chen" },
  { id: "TKT-003", subject: "Order hasn't arrived after 2 weeks", status: "open", priority: "high", category: "order_tracking", customer: "Priya Sharma" },
  { id: "TKT-004", subject: "Want to return a damaged product", status: "open", priority: "high", category: "returns_refunds", customer: "David Kim" },
  { id: "TKT-005", subject: "Dashboard loading very slowly", status: "resolved", priority: "medium", category: "tech_support", customer: "Emma Wilson" },
  { id: "TKT-006", subject: "Need to update payment method", status: "open", priority: "medium", category: "billing", customer: "Carlos Rodriguez" },
  { id: "TKT-007", subject: "Wrong item delivered, need exchange", status: "in_progress", priority: "high", category: "delivery_issues", customer: "Aisha Patel" },
  { id: "TKT-008", subject: "Terrible customer service experience", status: "open", priority: "high", category: "complaint", customer: "Tom Anderson" },
  { id: "TKT-009", subject: "Request for WhatsApp integration", status: "open", priority: "medium", category: "feature_request", customer: "Lisa Wang" },
  { id: "TKT-010", subject: "Package delivered to wrong address", status: "open", priority: "critical", category: "delivery_issues", customer: "James Brown" },
];

const MOCK_EXECUTORS = {
  check_system_health: () => ({
    success: true,
    message: "System is healthy. You've had 47 tickets today, AI quality is at 94%, and agent utilization is 72%."
  }),
  show_recent_errors: (params) => ({
    success: true,
    message: `Found 2 recent errors: (1) RedisTimeoutError in cache — warning, 2 min ago. (2) SlackWebhookError in integration — error, 15 min ago.`
  }),
  pause_all_ai: (params) => ({
    success: true,
    message: `All AI agents are now paused. Reason: ${params?.reason || 'User requested'}. They won't handle any tickets until you tell me to resume them.`
  }),
  resume_all_ai: () => ({
    success: true,
    message: "AI agents are back online! They'll start handling tickets again."
  }),
  emergency_stop: (params) => ({
    success: true,
    message: `Emergency stop is ACTIVE. ALL automated operations are paused. Reason: ${params?.reason || 'Emergency'}. Nothing will run until you tell me to resume.`
  }),
  get_ticket_stats: () => ({
    success: true,
    message: "You've had 47 tickets today — 12 open, 8 in progress, 27 resolved. Average response time is 3.2 min with an 87% resolution rate."
  }),
  list_recent_tickets: (params) => {
    const limit = params?.limit || 10;
    const statusFilter = params?.status || "all";
    let tickets = MOCK_TICKETS.slice(0, limit);
    if (statusFilter !== "all") tickets = tickets.filter(t => t.status === statusFilter);
    const list = tickets.map(t => `  • ${t.id} | ${t.status.padEnd(13)} | ${t.priority.padEnd(8)} | ${t.category.padEnd(16)} | ${t.subject}`).join('\n');
    return { success: true, message: `Here are your recent tickets (${tickets.length} found):\n${list}` };
  },
  escalate_urgent_tickets: (params) => ({
    success: true,
    message: `Done! Escalated 3 ${(params?.priority || 'urgent')}-priority tickets to your human team. They'll get priority attention now.`
  }),
  create_ticket: (params) => ({
    success: true,
    message: `Created ticket TKT-${Math.random().toString(36).substr(2, 6).toUpperCase()} for "${params?.subject || 'Support request'}". It's been assigned to the AI variant pipeline.`
  }),
  batch_solve_tickets: (params) => ({
    success: true,
    message: `Solved 5 open tickets through the AI variant pipeline. Each customer has received an AI-generated response resolving their issue.`
  }),
  get_subscription_info: () => ({
    success: true,
    message: "You're on the Parwa Pro plan. Usage today: 68% of your quota. Subscription status: active. Your plan includes unlimited AI conversations, 5 AI agents, and priority support."
  }),
  process_refund: (params) => ({
    success: true,
    message: `Refund of $${params?.amount || 0} has been processed for customer ${params?.customer_id || 'the customer'}. Reason: ${params?.reason || 'Customer request'}.`
  }),
  list_integrations: () => ({
    success: true,
    message: "You have 3 active integrations: Email (Gmail) — healthy, SMS (Twilio) — healthy, Chat Widget — healthy. And 1 inactive: Slack — error (needs reconnection)."
  }),
  get_performance_metrics: () => ({
    success: true,
    message: "Performance is looking solid: 3.2 min avg response time, 87% resolution rate, 4.2/5 CSAT score, 94% AI accuracy, and 98% SLA compliance."
  }),
  get_agent_status: () => ({
    success: true,
    message: "You have 5 AI agents and 3 human agents active. Utilization is at 72% with 4 tickets in the queue. All agents are handling within normal capacity."
  }),
  search_knowledge_base: (params) => ({
    success: true,
    message: `Found 2 articles matching "${params?.query || 'your query'}": (1) Getting Started Guide (92% match), (2) FAQ: Billing & Payments (78% match).`
  }),
  generate_fake_requests: (params) => {
    const count = params?.count || 5;
    const names = ["Sarah Johnson", "Mike Chen", "Priya Sharma", "David Kim", "Emma Wilson"];
    const subjects = ["App crashing on startup", "Double charge on card", "Order not arrived", "Damaged product return", "Dashboard slow"];
    const list = Array.from({length: count}, (_, i) => `  • ${names[i % 5]} — ${subjects[i % 5]} [${['medium','high','critical','low','high'][i % 5]}]`).join('\n');
    return { success: true, message: `Generated ${count} fake customer requests:\n${list}` };
  },
  upgrade_plan: (params) => {
    const planNames = { mini_parwa: "Mini Parwa (Starter)", parwa: "Parwa (Professional)", parwa_high: "Parwa High (Enterprise)" };
    return { success: true, message: `Done! Your plan has been upgraded to ${planNames[params?.target_plan] || params?.target_plan}. The new plan is effective immediately — you now have access to all features.` };
  },
  get_transaction_history: (params) => {
    const txns = [
      { date: "2025-05-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-04-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-03-28", type: "refund", amount: "-$12.50", desc: "Overcharge correction" },
      { date: "2025-03-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-02-20", type: "charge", amount: "$15.00", desc: "Additional AI agent" },
      { date: "2025-02-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-01-15", type: "credit", amount: "-$25.00", desc: "Loyalty credit" },
      { date: "2025-01-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
    ];
    const list = txns.map(t => `  • ${t.date} | ${t.type.padEnd(8)} | ${t.amount.padStart(7)} | ${t.desc}`).join('\n');
    const totalPayments = txns.filter(t => t.type === 'payment').reduce((s, t) => s + 49.99, 0);
    return { success: true, message: `Here's your transaction history:\n${list}\n\nSummary: ${txns.length} transactions | Total payments: $${totalPayments.toFixed(2)} | Refunds: $12.50 | Credits: $25.00` };
  },
  cancel_subscription: (params) => {
    return { success: true, message: `Your subscription has been scheduled for cancellation at the end of the current billing period. You'll continue to have access to all features until then. If you change your mind, just tell me to reactivate it.` };
  },
};


// ══════════════════════════════════════════════════════════════════
// JARVIS CHAT ENGINE
// ══════════════════════════════════════════════════════════════════

const SYSTEM_PROMPT = `You are Jarvis, an AI assistant for Parwa — a customer support platform. You help the client manage their support operations.

The client is managing their support platform through you. They might ask you to check things, change settings, or take actions. You have tools available to do everything the platform can do. Use them when the client asks you to do something.

HOW TO TALK:
- Be conversational and natural, like a smart colleague
- Don't be robotic or overly formal
- Don't say "Command executed successfully" — say what actually happened
- If you did something, explain the result in plain language
- If you need more info, ask naturally (not like a form)
- Be concise but friendly
- Use the client's context when responding

CURRENT SYSTEM STATE:
- System health: healthy
- Tickets today: 47
- AI quality score: 94%
- Agent utilization: 72%
- Plan: Parwa Pro
- Plan usage: 68%`;

let conversationHistory = [];
let pendingConfirmation = null;

async function initZAI() {
  const zai = await ZAI.create();
  return zai;
}

async function chatWithJarvis(zai, userMessage) {
  // Add user message to history
  conversationHistory.push({ role: "user", content: userMessage });

  // Check if there's a pending confirmation
  if (pendingConfirmation) {
    const lowerMsg = userMessage.toLowerCase();
    const isConfirm = ["yes", "confirm", "go ahead", "do it", "proceed", "sure", "ok", "yep", "yeah"].some(k => lowerMsg.includes(k));
    const isReject = ["no", "cancel", "stop", "never mind", "abort", "decline"].some(k => lowerMsg.includes(k));

    if (isConfirm) {
      // Execute the pending function
      const { funcName, params } = pendingConfirmation;
      pendingConfirmation = null;
      const executor = MOCK_EXECUTORS[funcName];
      const result = executor ? executor(params) : { success: false, message: `Unknown function: ${funcName}` };

      // Feed result back to LLM for natural response
      const followUpMessages = [
        ...conversationHistory,
        { role: "system", content: `[Function '${funcName}' was executed. Result: ${result.message}]\n\nNow respond to the user naturally about what just happened. Don't mention the function call.` }
      ];

      try {
        const followUp = await zai.chat.completions.create({
          messages: [
            { role: "system", content: SYSTEM_PROMPT },
            ...followUpMessages
          ],
          max_tokens: 400,
          temperature: 0.7,
        });
        const response = followUp.choices?.[0]?.message?.content || result.message;
        conversationHistory.push({ role: "assistant", content: response });
        return { response, functionCalled: funcName, safetyStatus: "confirmed_and_executed" };
      } catch (e) {
        conversationHistory.push({ role: "assistant", content: result.message });
        return { response: result.message, functionCalled: funcName, safetyStatus: "confirmed_and_executed" };
      }
    } else if (isReject) {
      const cancelled = pendingConfirmation.funcName;
      pendingConfirmation = null;
      const msg = `No problem, I've cancelled that. The ${cancelled} action won't proceed.`;
      conversationHistory.push({ role: "assistant", content: msg });
      return { response: msg, functionCalled: cancelled, safetyStatus: "cancelled" };
    } else {
      // Unclear — ask again
      const msg = "I just want to confirm — should I go ahead with that? Just say 'yes' or 'no'.";
      conversationHistory.push({ role: "assistant", content: msg });
      return { response: msg, functionCalled: null, safetyStatus: "pending_confirmation" };
    }
  }

  // Call LLM with function definitions as tools (with retry for rate limits)
  try {
    let completion;
    let retries = 3;
    while (retries > 0) {
      try {
        completion = await zai.chat.completions.create({
          messages: [
            { role: "system", content: SYSTEM_PROMPT },
            ...conversationHistory,
          ],
          tools: FUNCTION_DEFINITIONS,
          tool_choice: "auto",
          max_tokens: 600,
          temperature: 0.7,
        });
        break; // Success — break out of retry loop
      } catch (retryErr) {
        if (retryErr.message?.includes("429") && retries > 1) {
          console.log(`    ⏳ Rate limited, retrying in 5s... (${retries} retries left)`);
          await sleep(5000);
          retries--;
        } else {
          throw retryErr;
        }
      }
    }

    const choice = completion.choices?.[0];
    if (!choice) {
      const fallback = "I'm having trouble processing that. Could you try again?";
      conversationHistory.push({ role: "assistant", content: fallback });
      return { response: fallback, functionCalled: null };
    }

    const msg = choice.message;
    const hasToolCall = msg.tool_calls && msg.tool_calls.length > 0;

    if (hasToolCall) {
      const toolCall = msg.tool_calls[0];
      const funcName = toolCall.function.name;
      let funcArgs = {};
      try {
        funcArgs = typeof toolCall.function.arguments === 'string'
          ? JSON.parse(toolCall.function.arguments)
          : toolCall.function.arguments || {};
      } catch (e) { funcArgs = {}; }

      // Check safety level for this function
      const safetyLevels = {
        check_system_health: "none",
        show_recent_errors: "none",
        pause_all_ai: "confirmation_required",
        resume_all_ai: "confirmation_required",
        emergency_stop: "confirmation_required",
        get_ticket_stats: "none",
        list_recent_tickets: "none",
        escalate_urgent_tickets: "confirmation_required",
        create_ticket: "none",
        batch_solve_tickets: "confirmation_required",
        get_subscription_info: "none",
        process_refund: "approval_required",
        list_integrations: "none",
        get_performance_metrics: "none",
        get_agent_status: "none",
        search_knowledge_base: "none",
        generate_fake_requests: "confirmation_required",
        upgrade_plan: "approval_required",
        get_transaction_history: "none",
        cancel_subscription: "approval_required",
      };

      const safetyLevel = safetyLevels[funcName] || "none";

      // If no confirmation needed, execute immediately
      if (safetyLevel === "none") {
        const executor = MOCK_EXECUTORS[funcName];
        const result = executor ? executor(funcArgs) : { success: false, message: `I don't know how to do '${funcName}' yet.` };

        // Feed result back to LLM for natural response (with retry)
        try {
          let followUp;
          let fRetries = 3;
          while (fRetries > 0) {
            try {
              followUp = await zai.chat.completions.create({
                messages: [
                  { role: "system", content: SYSTEM_PROMPT },
                  ...conversationHistory,
                  { role: "assistant", content: msg.content || `I'll ${funcName} for you.` },
                  { role: "system", content: `[Function '${funcName}' was executed. Result: ${result.message}]\n\nNow respond to the user naturally about what just happened. Don't mention the function call name.` }
                ],
                max_tokens: 400,
                temperature: 0.7,
              });
              break;
            } catch (fErr) {
              if (fErr.message?.includes("429") && fRetries > 1) {
                console.log(`    ⏳ Follow-up rate limited, retrying in 5s...`);
                await sleep(5000);
                fRetries--;
              } else {
                throw fErr;
              }
            }
          }
          const response = followUp.choices?.[0]?.message?.content || result.message;
          conversationHistory.push({ role: "assistant", content: response });
          return { response, functionCalled: funcName, safetyStatus: "approved" };
        } catch (e) {
          conversationHistory.push({ role: "assistant", content: result.message });
          return { response: result.message, functionCalled: funcName, safetyStatus: "approved" };
        }
      } else {
        // Needs confirmation — store pending and ask the user
        pendingConfirmation = { funcName, params: funcArgs };

        const confirmationMessages = {
          pause_all_ai: `I'll pause all AI agents for you. They'll stop handling tickets until you tell me to resume. Shall I go ahead?`,
          resume_all_ai: `I'll resume all AI agents so they start handling tickets again. Should I proceed?`,
          emergency_stop: `This will immediately stop ALL automated operations — AI agents, refunds, everything pauses. Are you sure?`,
          escalate_urgent_tickets: `I'll escalate all urgent tickets to your human team right away. Should I go ahead?`,
          batch_solve_tickets: `I'll solve the open tickets through the AI variant pipeline. Each one will get an AI-generated response. Want me to proceed?`,
          generate_fake_requests: `I'll generate ${funcArgs?.count || 5} fake customer requests and create tickets from them. Want me to go ahead?`,
          process_refund: `This will issue a refund. This is a monetary action and can't be easily reversed. Please type 'confirm' if you want me to proceed.`,
          upgrade_plan: `This will upgrade your plan to ${funcArgs?.target_plan || 'the selected tier'}. This is a billing change that will affect your subscription. Please type 'confirm' if you want me to proceed.`,
          cancel_subscription: `This will cancel your subscription. You'll lose access to all features. Please type 'confirm' if you want me to proceed.`,
        };

        const confirmMsg = confirmationMessages[funcName] || `I'd like to run '${funcName}'. Can I go ahead?`;
        conversationHistory.push({ role: "assistant", content: confirmMsg });
        return { response: confirmMsg, functionCalled: funcName, safetyStatus: safetyLevel };
      }
    } else {
      // No function call — just a conversational response
      const response = msg.content || "I'm here to help! What would you like to do?";
      conversationHistory.push({ role: "assistant", content: response });
      return { response, functionCalled: null };
    }
  } catch (error) {
    console.error("  ❌ LLM Error:", error.message);
    const fallback = "I'm having trouble right now. Could you try again or rephrase?";
    conversationHistory.push({ role: "assistant", content: fallback });
    return { response: fallback, functionCalled: null, error: error.message };
  }
}


// ══════════════════════════════════════════════════════════════════
// AUTOMATED TEST SUITE
// ══════════════════════════════════════════════════════════════════

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function runTestSuite(zai) {
  console.log();
  console.log("═".repeat(70));
  console.log("  🤖 JARVIS AI-POWERED TEST SUITE");
  console.log("═".repeat(70));
  console.log();
  console.log("  Using REAL AI (z-ai-web-dev-sdk) to understand commands!");
  console.log("  The AI reads your natural language and picks the right function.");
  console.log();

  // Each test starts with a fresh conversation to avoid state leaking
  const testCases = [
    // Group 1: Simple commands (no confirmation needed)
    { message: "show me my transaction history", expected: "get_transaction_history", reset: true },
    { message: "what's my subscription? I want to upgrade my plan", expected: "get_subscription_info", reset: true },
    { message: "how's the system doing?", expected: "check_system_health", reset: true },
    { message: "what are my integrations?", expected: "list_integrations", reset: true },
    { message: "show me recent errors", expected: "show_recent_errors", reset: true },
    { message: "what's the performance like?", expected: "get_performance_metrics", reset: true },
    { message: "how many agents are working right now?", expected: "get_agent_status", reset: true },
    { message: "give me the ticket stats for today", expected: "get_ticket_stats", reset: true },
    // Group 2: Confirmation flow tests (each is a 2-step conversation)
    { message: "pause all AI agents right now", expected: "pause_all_ai", reset: true },
    { message: "yes go ahead", expected: "confirm_pause", reset: false },  // Same conversation
    // Group 3: More single commands
    { message: "batch solve all open tickets", expected: "batch_solve_tickets", reset: true },
    { message: "create a ticket for a customer whose order is late", expected: "create_ticket", reset: true },
    { message: "generate 5 fake requests for testing", expected: "generate_fake_requests", reset: true },
    { message: "escalate urgent tickets", expected: "escalate_urgent_tickets", reset: true },
    // Group 4: New functions — upgrade, transaction history, cancel
    { message: "upgrade my plan to parwa high", expected: "upgrade_plan", reset: true },
    { message: "show me my billing history", expected: "get_transaction_history", reset: true },
    { message: "I want to cancel my subscription because it's too expensive", expected: "cancel_subscription", reset: true },
  ];

  const results = [];

  for (let i = 0; i < testCases.length; i++) {
    const { message, expected, reset } = testCases[i];

    // Reset conversation if needed to avoid state leaking
    if (reset) {
      conversationHistory = [];
      pendingConfirmation = null;
    }

    // Rate limit — wait 5 seconds between tests to avoid 429
    if (i > 0) {
      await sleep(5000);
    }

    console.log(`  Test ${String(i + 1).padStart(2)}/${testCases.length}: "${message}"`);

    const result = await chatWithJarvis(zai, message);

    const funcCalled = result.functionCalled || "none";
    const safety = result.safetyStatus || "N/A";
    const response = result.response || "";

    // Check if function matches expected
    let matched = false;
    if (expected.startsWith("confirm_") && (safety === "confirmed_and_executed" || safety === "cancelled")) {
      matched = true;
    } else if (funcCalled === expected) {
      matched = true;
    }

    const status = matched ? "✅" : "⚠️";
    console.log(`    ${status} Function: ${funcCalled} | Safety: ${safety}`);
    console.log(`    Response: ${response.substring(0, 150)}${response.length > 150 ? '...' : ''}`);
    console.log();

    results.push({ test: i + 1, message, expected, actual: funcCalled, matched, safety, response: response.substring(0, 100) });
  }

  // Summary
  const passed = results.filter(r => r.matched).length;
  console.log("═".repeat(70));
  console.log(`  RESULTS: ${passed}/${results.length} tests matched expected functions`);
  console.log("═".repeat(70));
  console.log();

  for (const r of results) {
    const s = r.matched ? "✅" : "⚠️";
    console.log(`  ${s} Test ${r.test}: "${r.message.substring(0, 45)}" → got '${r.actual}', expected '${r.expected}'`);
  }
  console.log();
}


// ══════════════════════════════════════════════════════════════════
// INTERACTIVE CHAT
// ══════════════════════════════════════════════════════════════════

async function interactiveChat(zai) {
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  console.log();
  console.log("═".repeat(70));
  console.log("  🤖 JARVIS — AI-Powered Command Line");
  console.log("═".repeat(70));
  console.log();
  console.log("  Type naturally — the AI understands what you want!");
  console.log("  Try:");
  console.log('    • "show me my transaction history"');
  console.log('    • "upgrade my plan" or "what\'s my subscription?"');
  console.log('    • "pause all AI"');
  console.log('    • "show me recent tickets"');
  console.log('    • "how\'s the system doing?"');
  console.log('    • "escalate urgent tickets"');
  console.log('    • "generate 5 fake requests"');
  console.log('    • "batch solve open tickets"');
  console.log();
  console.log("  Commands: 'quit' to exit, 'clear' to reset");
  console.log("═".repeat(70));
  console.log();

  const prompt = () => {
    rl.question("  👤 You: ", async (input) => {
      const trimmed = input.trim();
      if (!trimmed) { prompt(); return; }
      if (trimmed.toLowerCase() === "quit") { console.log("  👋 Bye!"); rl.close(); return; }
      if (trimmed.toLowerCase() === "clear") {
        conversationHistory = [];
        pendingConfirmation = null;
        console.log("  🔄 Conversation cleared.\n");
        prompt(); return;
      }

      const result = await chatWithJarvis(zai, trimmed);
      const funcCalled = result.functionCalled;
      const safety = result.safetyStatus || "N/A";

      console.log();
      console.log(`  🤖 Jarvis: ${result.response}`);
      if (funcCalled) {
        console.log(`     ─── [Function: ${funcCalled} | Safety: ${safety}]`);
      }
      console.log();
      prompt();
    });
  };

  prompt();
}


// ══════════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════════

async function main() {
  console.log("  Initializing Jarvis AI engine...");
  const zai = await initZAI();
  console.log("  ✅ AI engine ready!\n");

  const mode = process.argv[2];
  if (mode === "--test") {
    await runTestSuite(zai);
  } else {
    await interactiveChat(zai);
  }
}

main().catch(err => {
  console.error("Fatal error:", err);
  process.exit(1);
});
