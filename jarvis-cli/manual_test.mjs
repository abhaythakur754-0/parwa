import ZAI from 'z-ai-web-dev-sdk';

// Full function definitions for all 20 functions
const FUNCTION_DEFINITIONS = [
  // System
  { type: "function", function: { name: "check_system_health", description: "Check system health, status, uptime, error rate. Use when user asks how things are going.", parameters: { type: "object", properties: {}, required: [] } } },
  { type: "function", function: { name: "show_recent_errors", description: "Show recent system errors with type and severity. Use when user asks about errors or failures.", parameters: { type: "object", properties: { severity: { type: "string", enum: ["all","warning","error","critical"], default: "all" } }, required: [] } } },
  // AI Control
  { type: "function", function: { name: "pause_all_ai", description: "Pause all AI agents. Use when user wants to stop AI or take manual control.", parameters: { type: "object", properties: { reason: { type: "string", description: "Why AI is being paused" } }, required: ["reason"] } } },
  { type: "function", function: { name: "resume_all_ai", description: "Resume AI agents after a pause. Use when user wants to turn AI back on.", parameters: { type: "object", properties: {}, required: [] } } },
  { type: "function", function: { name: "emergency_stop", description: "Emergency shutdown — pause ALL automated operations. Use ONLY for emergencies.", parameters: { type: "object", properties: { reason: { type: "string", description: "Emergency reason" } }, required: ["reason"] } } },
  // Tickets
  { type: "function", function: { name: "get_ticket_stats", description: "Get ticket statistics — volume, open/closed counts, response time, resolution rate. Use when user asks about tickets or workload.", parameters: { type: "object", properties: { time_range: { type: "string", enum: ["today","this_week","this_month","all_time"], default: "today" } }, required: [] } } },
  { type: "function", function: { name: "list_recent_tickets", description: "List recent tickets with status, priority, category. Use when user wants to see recent tickets or transaction history of support cases.", parameters: { type: "object", properties: { status: { type: "string", enum: ["all","open","in_progress","resolved","closed"], default: "all" }, limit: { type: "integer", default: 10 } }, required: [] } } },
  { type: "function", function: { name: "create_ticket", description: "Create a new support ticket. Use when user wants to log a support issue or report a problem.", parameters: { type: "object", properties: { subject: { type: "string" }, message: { type: "string" }, priority: { type: "string", enum: ["low","medium","high","critical"], default: "medium" }, category: { type: "string", enum: ["tech_support","billing","returns_refunds","order_tracking","delivery_issues","general"], default: "general" } }, required: ["subject","message"] } } },
  { type: "function", function: { name: "batch_solve_tickets", description: "Solve multiple tickets via AI variant pipeline. Use when user wants to bulk resolve tickets.", parameters: { type: "object", properties: { max_tickets: { type: "integer", default: 10 } }, required: [] } } },
  { type: "function", function: { name: "escalate_urgent_tickets", description: "Escalate urgent tickets to human agents. Use when user wants urgent issues to get human attention.", parameters: { type: "object", properties: { priority: { type: "string", enum: ["urgent","high","critical"], default: "urgent" } }, required: [] } } },
  // Billing
  { type: "function", function: { name: "get_subscription_info", description: "Get subscription plan details — plan name, usage, limits, renewal date. Use when user asks about their plan or subscription.", parameters: { type: "object", properties: {}, required: [] } } },
  { type: "function", function: { name: "upgrade_plan", description: "Upgrade subscription to a higher tier. Tiers: mini_parwa (starter), parwa (professional), parwa_high (enterprise). Use when user wants to upgrade or change plan.", parameters: { type: "object", properties: { target_plan: { type: "string", enum: ["mini_parwa","parwa","parwa_high"] }, reason: { type: "string" } }, required: ["target_plan"] } } },
  { type: "function", function: { name: "cancel_subscription", description: "Cancel the subscription. DESTRUCTIVE action. Use when user explicitly wants to cancel or end subscription.", parameters: { type: "object", properties: { reason: { type: "string" }, immediate: { type: "boolean", default: false } }, required: ["reason"] } } },
  { type: "function", function: { name: "get_transaction_history", description: "Get transaction/billing history — payments, refunds, credits, charges. Use when user asks about transaction history, billing history, past payments, or charges.", parameters: { type: "object", properties: { period: { type: "string", enum: ["last_30_days","last_90_days","this_year","all"], default: "last_30_days" }, transaction_type: { type: "string", enum: ["all","payments","refunds","credits","charges"], default: "all" } }, required: [] } } },
  { type: "function", function: { name: "process_refund", description: "Process a refund for a customer. MONETARY action. Use ONLY when user explicitly requests a refund.", parameters: { type: "object", properties: { customer_id: { type: "string" }, amount: { type: "number" }, reason: { type: "string" } }, required: ["customer_id","amount","reason"] } } },
  // Analytics
  { type: "function", function: { name: "get_performance_metrics", description: "Get performance metrics — response times, resolution rates, CSAT, AI accuracy, SLA compliance. Use when user asks about performance.", parameters: { type: "object", properties: {}, required: [] } } },
  // Agents
  { type: "function", function: { name: "get_agent_status", description: "Get AI and human agent status — active count, utilization, capacity. Use when user asks about agents or capacity.", parameters: { type: "object", properties: {}, required: [] } } },
  // Integrations
  { type: "function", function: { name: "list_integrations", description: "List all configured integrations — email, SMS, chat widget, etc. Use when user asks about integrations.", parameters: { type: "object", properties: {}, required: [] } } },
  // Knowledge
  { type: "function", function: { name: "search_knowledge_base", description: "Search knowledge base for articles and FAQs. Use when user wants to find information.", parameters: { type: "object", properties: { query: { type: "string" } }, required: ["query"] } } },
  // Fake Requests
  { type: "function", function: { name: "generate_fake_requests", description: "Generate fake customer support requests for testing. Use when user wants test data or demo.", parameters: { type: "object", properties: { count: { type: "integer", default: 5 }, category: { type: "string", enum: ["mixed","tech_support","billing","returns_refunds","order_tracking","delivery_issues"], default: "mixed" } }, required: [] } } },
];

const MOCK_EXECUTORS = {
  check_system_health: () => ({ success: true, message: "System is healthy. 47 tickets today, AI quality 94%, agent utilization 72%." }),
  show_recent_errors: () => ({ success: true, message: "Found 2 recent errors: (1) RedisTimeoutError in cache — warning, 2 min ago. (2) SlackWebhookError in integration — error, 15 min ago." }),
  pause_all_ai: (p) => ({ success: true, message: `All AI agents are now paused. Reason: ${p?.reason || 'User requested'}. They won't handle tickets until you resume.` }),
  resume_all_ai: () => ({ success: true, message: "AI agents are back online! They'll start handling tickets again." }),
  emergency_stop: (p) => ({ success: true, message: `Emergency stop ACTIVE. ALL operations paused. Reason: ${p?.reason || 'Emergency'}. Nothing runs until you resume.` }),
  get_ticket_stats: () => ({ success: true, message: "47 tickets today — 12 open, 8 in progress, 27 resolved. Avg response: 3.2 min, 87% resolution rate." }),
  list_recent_tickets: () => ({ success: true, message: "10 recent tickets:\n  TKT-001 | open      | high     | tech_support     | App keeps crashing\n  TKT-002 | in_prog  | high     | billing           | Charged twice\n  TKT-003 | open      | high     | order_tracking    | Order not arrived" }),
  create_ticket: (p) => ({ success: true, message: `Created ticket TKT-${Math.random().toString(36).substr(2,6).toUpperCase()} for "${p?.subject || 'Support request'}". Assigned to variant pipeline.` }),
  batch_solve_tickets: () => ({ success: true, message: "Solved 5 open tickets through the AI variant pipeline. Each customer received an AI-generated response." }),
  escalate_urgent_tickets: () => ({ success: true, message: "Escalated 3 urgent tickets to your human team. They'll get priority attention." }),
  get_subscription_info: () => ({ success: true, message: "You're on Parwa Pro plan. Usage today: 68%. Status: active. Includes unlimited AI conversations, 5 AI agents, priority support." }),
  upgrade_plan: (p) => {
    const names = { mini_parwa: "Mini Parwa (Starter)", parwa: "Parwa (Professional)", parwa_high: "Parwa High (Enterprise)" };
    return { success: true, message: `Done! Upgraded to ${names[p?.target_plan] || p?.target_plan}. Effective immediately — you now have access to all features.` };
  },
  cancel_subscription: () => ({ success: true, message: "Subscription scheduled for cancellation at end of billing period. You'll keep access until then. Let me know if you change your mind." }),
  get_transaction_history: () => {
    const txns = [
      { date: "2025-05-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-04-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
      { date: "2025-03-28", type: "refund", amount: "-$12.50", desc: "Overcharge correction" },
      { date: "2025-03-01", type: "payment", amount: "$49.99", desc: "Parwa Pro - Monthly" },
    ];
    const list = txns.map(t => `  ${t.date} | ${t.type.padEnd(8)} | ${t.amount.padStart(7)} | ${t.desc}`).join('\n');
    return { success: true, message: `Transaction history:\n${list}\n\nSummary: 4 transactions | Payments: $149.97 | Refunds: $12.50` };
  },
  process_refund: (p) => ({ success: true, message: `Refund of $${p?.amount || 0} processed for customer ${p?.customer_id || 'the customer'}. Reason: ${p?.reason || 'Customer request'}.` }),
  get_performance_metrics: () => ({ success: true, message: "Performance: 3.2 min avg response, 87% resolution, 4.2/5 CSAT, 94% AI accuracy, 98% SLA compliance." }),
  get_agent_status: () => ({ success: true, message: "5 AI agents, 3 human agents active. Utilization 72%, 4 tickets in queue." }),
  list_integrations: () => ({ success: true, message: "3 active integrations: Email (Gmail) — healthy, SMS (Twilio) — healthy, Chat Widget — healthy. 1 inactive: Slack — error." }),
  search_knowledge_base: (p) => ({ success: true, message: `Found 2 articles for "${p?.query}": (1) Getting Started Guide (92%), (2) FAQ: Billing & Payments (78%).` }),
  generate_fake_requests: (p) => ({ success: true, message: `Generated ${p?.count || 5} fake customer requests as open tickets for testing.` }),
};

const COMMAND_PROMPT = `You are Jarvis, an AI assistant for Parwa — a customer support platform. You help the client manage their support operations. The client is managing their support platform through you. They might ask you to check things, change settings, or take actions. You have tools available to do everything the platform can do.

HOW TO TALK:
- Be conversational and natural, like a smart colleague
- Don't be robotic or overly formal
- Don't say "Command executed successfully" — say what actually happened
- If you did something, explain the result in plain language
- If you need more info, ask naturally
- Be concise but friendly

CURRENT SYSTEM STATE:
- System health: healthy
- Tickets today: 47
- AI quality score: 94%
- Agent utilization: 72%
- Plan: Parwa Pro
- Plan usage: 68%`;

const AGENTIC_PROMPT = `You are Jarvis, an AI assistant helping a CUSTOMER of one of Parwa's clients. The customer is reaching out for support. Be helpful, friendly, and solve their problem. Use tools when needed to look up information or take action. You represent the brand — be warm and professional.

CURRENT CONTEXT:
- Customer is asking about their order or issue
- You have access to tools for checking orders, answering questions, and escalating if needed`;

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

let history = [];
let pendingAction = null;

async function chat(zai, userMsg, systemPrompt) {
  history.push({ role: "user", content: userMsg });

  // Check pending safety confirmation
  if (pendingAction) {
    const lower = userMsg.toLowerCase();
    const isConfirm = ["yes","confirm","go ahead","do it","proceed","sure","ok","yep","yeah"].some(k => lower.includes(k));
    const isReject = ["no","cancel","stop","never mind","abort","decline"].some(k => lower.includes(k));

    if (isConfirm) {
      const { funcName, params } = pendingAction;
      pendingAction = null;
      const result = MOCK_EXECUTORS[funcName]?.(params) || { success: false, message: `Unknown: ${funcName}` };
      try {
        const followUp = await zai.chat.completions.create({
          messages: [{ role: "system", content: systemPrompt }, ...history,
            { role: "system", content: `[Function '${funcName}' executed. Result: ${result.message}]\n\nNow respond naturally about what happened. Don't mention the function call.` }
          ],
          max_tokens: 300, temperature: 0.7,
        });
        const resp = followUp.choices?.[0]?.message?.content || result.message;
        history.push({ role: "assistant", content: resp });
        return { response: resp, functionCalled: funcName, safety: "CONFIRMED & EXECUTED" };
      } catch(e) {
        history.push({ role: "assistant", content: result.message });
        return { response: result.message, functionCalled: funcName, safety: "CONFIRMED & EXECUTED" };
      }
    } else if (isReject) {
      const cancelled = pendingAction.funcName;
      pendingAction = null;
      const msg = `No problem, I've cancelled that. The ${cancelled} action won't proceed.`;
      history.push({ role: "assistant", content: msg });
      return { response: msg, safety: "CANCELLED" };
    }
  }

  try {
    const completion = await zai.chat.completions.create({
      messages: [{ role: "system", content: systemPrompt }, ...history],
      tools: FUNCTION_DEFINITIONS,
      tool_choice: "auto",
      max_tokens: 500,
      temperature: 0.7,
    });

    const choice = completion.choices?.[0];
    if (!choice?.message) {
      const fb = "I'm having trouble. Try again?";
      history.push({ role: "assistant", content: fb });
      return { response: fb, functionCalled: null };
    }

    const msg = choice.message;
    if (msg.tool_calls?.length > 0) {
      const tc = msg.tool_calls[0];
      const funcName = tc.function.name;
      let funcArgs = {};
      try { funcArgs = typeof tc.function.arguments === 'string' ? JSON.parse(tc.function.arguments) : tc.function.arguments || {}; } catch(e) {}

      // Safety levels
      const safetyLevels = {
        check_system_health: "none", show_recent_errors: "none", get_ticket_stats: "none",
        list_recent_tickets: "none", get_subscription_info: "none", get_transaction_history: "none",
        get_performance_metrics: "none", get_agent_status: "none", list_integrations: "none",
        search_knowledge_base: "none", create_ticket: "none",
        pause_all_ai: "confirmation", resume_all_ai: "confirmation", emergency_stop: "confirmation",
        escalate_urgent_tickets: "confirmation", batch_solve_tickets: "confirmation",
        generate_fake_requests: "confirmation",
        upgrade_plan: "approval", cancel_subscription: "approval", process_refund: "approval",
      };

      const safety = safetyLevels[funcName] || "none";

      if (safety === "none") {
        // Execute immediately
        const result = MOCK_EXECUTORS[funcName]?.(funcArgs) || { success: false, message: `Unknown: ${funcName}` };
        try {
          const followUp = await zai.chat.completions.create({
            messages: [{ role: "system", content: systemPrompt }, ...history,
              { role: "assistant", content: msg.content || `I'll ${funcName} for you.` },
              { role: "system", content: `[Function '${funcName}' executed. Result: ${result.message}]\n\nNow respond naturally. Don't mention the function call name.` }
            ],
            max_tokens: 300, temperature: 0.7,
          });
          const resp = followUp.choices?.[0]?.message?.content || result.message;
          history.push({ role: "assistant", content: resp });
          return { response: resp, functionCalled: funcName, safety: "APPROVED (auto)" };
        } catch(e) {
          history.push({ role: "assistant", content: result.message });
          return { response: result.message, functionCalled: funcName, safety: "APPROVED (auto)" };
        }
      } else {
        // Needs confirmation
        pendingAction = { funcName, params: funcArgs };
        const confirmMsgs = {
          pause_all_ai: "I'll pause all AI agents. They'll stop handling tickets until you resume. Shall I go ahead?",
          resume_all_ai: "I'll resume all AI agents. Should I proceed?",
          emergency_stop: "This will immediately stop ALL operations. Are you sure?",
          escalate_urgent_tickets: "I'll escalate urgent tickets to your human team. Should I go ahead?",
          batch_solve_tickets: "I'll solve open tickets through the AI pipeline. Want me to proceed?",
          generate_fake_requests: `I'll generate ${funcArgs?.count || 5} fake requests as test tickets. Want me to go ahead?`,
          upgrade_plan: `This will upgrade your plan to ${funcArgs?.target_plan || 'the selected tier'}. This is a billing change. Please type 'confirm' to proceed.`,
          cancel_subscription: "This will cancel your subscription. You'll lose access to features. Please type 'confirm' to proceed.",
          process_refund: `This will issue a refund. This is a monetary action. Please type 'confirm' to proceed.`,
        };
        const confirmMsg = confirmMsgs[funcName] || `I'd like to run '${funcName}'. Can I go ahead?`;
        history.push({ role: "assistant", content: confirmMsg });
        return { response: confirmMsg, functionCalled: funcName, safety: `${safety.toUpperCase()} REQUIRED` };
      }
    } else {
      const resp = msg.content || "How can I help?";
      history.push({ role: "assistant", content: resp });
      return { response: resp, functionCalled: null };
    }
  } catch(e) {
    const fb = "I'm having trouble. Could you try again?";
    history.push({ role: "assistant", content: fb });
    return { response: fb, error: e.message };
  }
}

async function main() {
  const zai = await ZAI.create();
  console.log("╔════════════════════════════════════════════════════════════════╗");
  console.log("║  JARVIS MANUAL TEST — Awareness + Command + Agentic + Safety  ║");
  console.log("╚════════════════════════════════════════════════════════════════╝\n");

  // ═══ TEST 1: AWARENESS QUERIES (Command Mode) ═══
  console.log("═══ TEST 1: AWARENESS QUERIES (Non-Agentic / Command Mode) ═══\n");
  
  const awarenessTests = [
    "how's everything going right now?",
    "show me the ticket stats for today",
    "what's the performance like?",
    "are there any errors in the system?",
    "how many agents are working right now?",
  ];

  for (const cmd of awarenessTests) {
    console.log(`👤 YOU: "${cmd}"`);
    const r = await chat(zai, cmd, COMMAND_PROMPT);
    console.log(`🤖 JARVIS: ${r.response.substring(0, 200)}${r.response.length > 200 ? '...' : ''}`);
    console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
    await sleep(3000);
  }

  // ═══ TEST 2: COMMAND MODE — Actions requiring confirmation ═══
  console.log("\n═══ TEST 2: COMMAND MODE — Safety Gate (Confirmation Required) ═══\n");
  history = []; pendingAction = null;

  console.log(`👤 YOU: "pause all AI agents, I need to check something"`);
  let r = await chat(zai, "pause all AI agents, I need to check something", COMMAND_PROMPT);
  console.log(`🤖 JARVIS: ${r.response}`);
  console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
  await sleep(3000);

  console.log(`👤 YOU: "yes go ahead"`);
  r = await chat(zai, "yes go ahead", COMMAND_PROMPT);
  console.log(`🤖 JARVIS: ${r.response}`);
  console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
  await sleep(3000);

  // ═══ TEST 3: UPGRADE PLAN (Approval Required) ═══
  console.log("\n═══ TEST 3: UPGRADE PLAN — Safety Gate (Approval Required) ═══\n");
  history = []; pendingAction = null;

  console.log(`👤 YOU: "upgrade my plan to parwa high"`);
  r = await chat(zai, "upgrade my plan to parwa high", COMMAND_PROMPT);
  console.log(`🤖 JARVIS: ${r.response}`);
  console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
  await sleep(3000);

  console.log(`👤 YOU: "confirm"`);
  r = await chat(zai, "confirm", COMMAND_PROMPT);
  console.log(`🤖 JARVIS: ${r.response}`);
  console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
  await sleep(3000);

  // ═══ TEST 4: TRANSACTION HISTORY ═══
  console.log("\n═══ TEST 4: TRANSACTION HISTORY (No Safety Gate) ═══\n");
  history = []; pendingAction = null;

  console.log(`👤 YOU: "show me my transaction history"`);
  r = await chat(zai, "show me my transaction history", COMMAND_PROMPT);
  console.log(`🤖 JARVIS: ${r.response}`);
  console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
  await sleep(3000);

  // ═══ TEST 5: AGENTIC MODE (Customer-Facing) ═══
  console.log("\n═══ TEST 5: AGENTIC MODE — Customer-Facing Conversations ═══\n");
  history = []; pendingAction = null;

  const agenticTests = [
    "Hi, I ordered a laptop 2 weeks ago and it still hasn't arrived. Order #ORD-8832",
    "Can I get a refund? The product I received is damaged.",
  ];

  for (const cmd of agenticTests) {
    console.log(`👤 CUSTOMER: "${cmd}"`);
    r = await chat(zai, cmd, AGENTIC_PROMPT);
    console.log(`🤖 JARVIS: ${r.response.substring(0, 250)}${r.response.length > 250 ? '...' : ''}`);
    console.log(`   [Function: ${r.functionCalled || 'none'} | Safety: ${r.safety || 'N/A'}]\n`);
    await sleep(3000);
  }

  console.log("\n╔════════════════════════════════════════════════════════════════╗");
  console.log("║  ALL MANUAL TESTS COMPLETE!                                    ║");
  console.log("╚════════════════════════════════════════════════════════════════╝");
}

main().catch(console.error);
