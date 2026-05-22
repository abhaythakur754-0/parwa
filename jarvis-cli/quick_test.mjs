import ZAI from 'z-ai-web-dev-sdk';

const FUNCTION_DEFINITIONS = [
  { type: "function", function: { name: "check_system_health", description: "Check system health. Use when user asks how things are going or system status.", parameters: { type: "object", properties: {}, required: [] } } },
  { type: "function", function: { name: "get_transaction_history", description: "Get transaction/billing history. Use when user asks about transaction history, billing history, past payments, or charges.", parameters: { type: "object", properties: { period: { type: "string", enum: ["last_30_days","last_90_days","this_year","all"], default: "last_30_days" } }, required: [] } } },
  { type: "function", function: { name: "upgrade_plan", description: "Upgrade subscription plan. Use when user wants to upgrade or change plan.", parameters: { type: "object", properties: { target_plan: { type: "string", enum: ["mini_parwa","parwa","parwa_high"] }, reason: { type: "string" } }, required: ["target_plan"] } } },
  { type: "function", function: { name: "cancel_subscription", description: "Cancel subscription. DESTRUCTIVE. Use when user wants to cancel.", parameters: { type: "object", properties: { reason: { type: "string" }, immediate: { type: "boolean", default: false } }, required: ["reason"] } } },
  { type: "function", function: { name: "get_ticket_stats", description: "Get ticket statistics. Use when user asks about tickets or workload.", parameters: { type: "object", properties: {}, required: [] } } },
];

const SYSTEM_PROMPT = `You are Jarvis, an AI assistant for Parwa customer support platform. Help manage support operations. Be conversational and natural. Current state: System healthy, 47 tickets today, 94% AI quality, Parwa Pro plan.`;

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function testCommand(zai, command) {
  try {
    const completion = await zai.chat.completions.create({
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: command },
      ],
      tools: FUNCTION_DEFINITIONS,
      tool_choice: "auto",
      max_tokens: 300,
      temperature: 0.7,
    });
    
    const choice = completion.choices?.[0];
    if (!choice) return { func: "none", response: "No response" };
    
    const hasToolCall = choice.message?.tool_calls?.length > 0;
    if (hasToolCall) {
      const tc = choice.message.tool_calls[0];
      return { func: tc.function.name, args: typeof tc.function.arguments === 'string' ? JSON.parse(tc.function.arguments) : tc.function.arguments, content: choice.message.content || "" };
    }
    return { func: "none", response: choice.message.content || "No content" };
  } catch (e) {
    return { func: "error", response: e.message };
  }
}

async function main() {
  const zai = await ZAI.create();
  console.log("=== JARVIS QUICK FUNCTION CALLING TEST ===\n");
  
  const tests = [
    "how's the system doing?",
    "show me my transaction history",
    "I want to upgrade my plan to parwa high",
    "cancel my subscription, it's too expensive",
    "how many tickets do we have today?",
  ];
  
  for (const cmd of tests) {
    console.log(`USER: "${cmd}"`);
    const result = await testCommand(zai, cmd);
    console.log(`JARVIS picked: ${result.func}`);
    if (result.args) console.log(`  Args: ${JSON.stringify(result.args)}`);
    if (result.response) console.log(`  Response: ${result.response.substring(0, 100)}`);
    console.log();
    await sleep(3000);
  }
}

main().catch(console.error);
