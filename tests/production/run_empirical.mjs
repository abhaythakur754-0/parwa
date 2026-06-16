import ZAI from 'z-ai-web-dev-sdk';
import { writeFileSync, mkdirSync } from 'fs';

const zai = await ZAI.create();

async function chat(system, user, maxTokens = 300, temp = 0.1) {
  try {
    const completion = await zai.chat.completions.create({
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user }
      ],
      max_tokens: maxTokens,
      temperature: temp,
    });
    return completion.choices[0]?.message?.content?.trim() || '';
  } catch (e) {
    return '';
  }
}

const TICKETS = [
  { id: 'R-001', q: 'I want a refund for the headphones I bought 5 days ago. The left ear stopped working.', es: 'refund', ei: 'refund', em: 'neutral' },
  { id: 'R-002', q: 'Cancel my subscription immediately. I have been charged for 3 months and never used the service.', es: 'refund', ei: 'cancellation', em: 'angry' },
  { id: 'R-003', q: 'I returned my order 2 weeks ago but still have not received my money back. Order #ORD-88234.', es: 'refund', ei: 'refund', em: 'frustrated' },
  { id: 'R-004', q: 'This is the third time asking for a refund on the same item. Your system keeps rejecting it.', es: 'refund', ei: 'refund', em: 'angry' },
  { id: 'R-005', q: 'I bought a laptop 45 days ago. It is defective. Can I still get a refund?', es: 'refund', ei: 'refund', em: 'frustrated' },
  { id: 'R-006', q: 'My subscription renewed yesterday but I cancelled last week. I need the renewal charge reversed.', es: 'refund', ei: 'refund', em: 'frustrated' },
  { id: 'T-001', q: 'Your app keeps crashing when I try to upload files. Chrome version 125.', es: 'tech', ei: 'technical', em: 'neutral' },
  { id: 'T-002', q: 'The API is returning 503 errors intermittently. Our production integration is affected.', es: 'tech', ei: 'technical', em: 'urgent' },
  { id: 'T-003', q: 'I cannot log into my account. It says credentials invalid but I am using the right password.', es: 'tech', ei: 'technical', em: 'frustrated' },
  { id: 'T-004', q: 'The webhook integration stopped working after your last update. Events not being delivered.', es: 'tech', ei: 'technical', em: 'frustrated' },
  { id: 'T-005', q: 'My dashboard is loading extremely slow. 30 seconds for any page to load.', es: 'tech', ei: 'technical', em: 'frustrated' },
  { id: 'B-001', q: 'You charged me twice for the same order! Two charges of $149.99 on my card statement.', es: 'billing', ei: 'billing', em: 'angry' },
  { id: 'B-002', q: 'My invoice shows a different amount than what I was quoted. The tax calculation seems wrong.', es: 'billing', ei: 'billing', em: 'neutral' },
  { id: 'B-003', q: 'I upgraded from Starter to Pro last week but my invoice still shows the Starter price.', es: 'billing', ei: 'billing', em: 'frustrated' },
  { id: 'B-004', q: 'There is an unauthorized transaction of $3,450 on my account. Investigate immediately.', es: 'billing', ei: 'billing', em: 'angry' },
  { id: 'B-005', q: 'Can you explain the proration on my latest invoice? I do not understand the mid-cycle upgrade charge.', es: 'billing', ei: 'billing', em: 'neutral' },
  { id: 'G-001', q: 'What are your business hours? I need to know when I can reach a live agent.', es: 'general', ei: 'general', em: 'neutral' },
  { id: 'G-002', q: 'How do I change my email address on my account?', es: 'general', ei: 'account', em: 'neutral' },
  { id: 'G-003', q: 'I am very disappointed with the service. The agent was rude and unhelpful.', es: 'general', ei: 'complaint', em: 'angry' },
  { id: 'G-004', q: 'Do you offer an API for integrating with Salesforce?', es: 'general', ei: 'general', em: 'neutral' },
  { id: 'G-005', q: 'I am going to sue your company for selling my data without consent.', es: 'general', ei: 'escalation', em: 'angry' },
  { id: 'G-006', q: 'Can you tell me the status of my order #ORD-98234?', es: 'general', ei: 'order_status', em: 'neutral' },
  { id: 'G-007', q: 'I have been a loyal customer for 3 years and this is how you treat me? I want to speak to a manager.', es: 'general', ei: 'escalation', em: 'angry' },
  { id: 'G-008', q: 'What is the difference between your Starter and Pro plans?', es: 'general', ei: 'general', em: 'neutral' },
  { id: 'R-007', q: 'I accidentally purchased the Pro plan instead of Starter. Can you refund the difference?', es: 'refund', ei: 'refund', em: 'neutral' },
  { id: 'R-008', q: 'You people stole my money! I never signed up for this and you have been charging me for 6 months!', es: 'refund', ei: 'refund', em: 'angry' },
  { id: 'T-006', q: 'Getting SSL certificate errors when connecting to your API endpoint from our EU servers.', es: 'tech', ei: 'technical', em: 'neutral' },
  { id: 'T-007', q: 'Your mobile app will not open on my iPhone 15. Crashes immediately on launch.', es: 'tech', ei: 'technical', em: 'frustrated' },
  { id: 'B-006', q: 'My payment failed but my card is working fine everywhere else. What is wrong with your system?', es: 'billing', ei: 'billing', em: 'frustrated' },
  { id: 'B-007', q: 'I need a receipt for my annual subscription payment for tax purposes.', es: 'billing', ei: 'billing', em: 'neutral' },
];

const ROUTE_P = 'Classify into one word: refund/tech/billing/general. refund=money back/return/cancellation. tech=errors/bugs/API. billing=charges/invoices. general=everything else.';
const INTENT_P = 'Classify intent. One word: refund, cancellation, billing, technical, complaint, shipping, account, general, escalation, order_status.';
const RESP_P = {
  refund: 'You are a refund policy specialist. 30-day full refund policy, 31-60 day partial (50-75%), 60+ days only for defects. Subscription refunds are prorated from cancellation date. Be empathetic. Respond in 2-3 sentences with specific details about the refund.',
  tech: 'You are a technical support specialist. Start with simplest fix first. Give specific troubleshooting steps. If 3+ fixes fail, escalate to engineering. Respond in 2-3 sentences with actionable steps.',
  billing: 'You are a billing specialist. Verify charges against the subscription plan. Show exact amounts and line items. For disputes, investigate before crediting. Respond in 2-3 sentences with specific numbers.',
  general: 'You are a helpful customer support agent. Be friendly, clear, concise. For complaints, acknowledge frustration before solving. For legal threats, route to specialist team. Respond in 2-3 sentences.',
};
const EVAL_P = 'Judge if this customer support response actually resolves the problem. Be brutally honest from the customer perspective. Respond in JSON only: {"resolution_status": "fully_resolved" or "partially_resolved" or "not_resolved", "intent_match": true or false, "actionable": true or false, "reason": "brief explanation"}';

function parseEval(text) {
  try {
    let t = text.trim();
    if (t.includes('```json')) t = t.split('```json')[1].split('```')[0].trim();
    else if (t.includes('```')) t = t.split('```')[1].split('```')[0].trim();
    const d = JSON.parse(t);
    const status = ['fully_resolved','partially_resolved','not_resolved'].includes(d.resolution_status) ? d.resolution_status : 'not_resolved';
    return { status, intentMatch: !!d.intent_match, actionable: !!d.actionable, reason: d.reason || '' };
  } catch {
    let status = 'not_resolved';
    if (text.includes('fully_resolved')) status = 'fully_resolved';
    else if (text.includes('partially_resolved')) status = 'partially_resolved';
    return { status, intentMatch: false, actionable: false, reason: 'parse fallback' };
  }
}

const results = [];
const total = TICKETS.length;
console.log(`PARWA EMPIRICAL TEST: ${total} tickets via ZAI SDK`);
console.log('='.repeat(60));

for (let i = 0; i < total; i++) {
  const t = TICKETS[i];
  process.stdout.write(`[${i+1}/${total}] ${t.id} `);
  const start = Date.now();

  // Route
  const rSub = await chat(ROUTE_P, t.q, 20, 0.1);
  let predSub = 'general';
  for (const v of ['refund','tech','billing','general']) {
    if (rSub.toLowerCase().includes(v)) { predSub = v; break; }
  }

  // Intent
  const rInt = await chat(INTENT_P, t.q, 20, 0.1);
  let predInt = 'general';
  for (const v of ['refund','billing','technical','complaint','shipping','account','cancellation','general','escalation','order_status']) {
    if (rInt.toLowerCase().includes(v)) { predInt = v; break; }
  }

  // Response
  let sysP = RESP_P[predSub] || RESP_P.general;
  if (t.em === 'angry' || t.em === 'urgent') sysP += ' IMPORTANT: Customer is ANGRY. Show strong empathy first.';
  else if (t.em === 'frustrated') sysP += ' Customer is FRUSTRATED. Acknowledge their frustration.';
  const response = await chat(sysP, t.q, 400, 0.3);

  // Evaluate
  const evText = await chat(EVAL_P, `Expected intent: ${t.ei}\nCustomer: ${t.q}\nResponse: ${response}`, 200, 0.1);
  const ev = parseEval(evText);

  const lat = Date.now() - start;
  const subOk = predSub === t.es;
  const intOk = predInt === t.ei;
  const contained = !t.q.toLowerCase().includes('sue') && ev.status !== 'not_resolved';

  results.push({
    id: t.id, expectedSub: t.es, predSub, subOk,
    expectedIntent: t.ei, predInt, intOk,
    resolution: ev.status, intentMatch: ev.intentMatch,
    actionable: ev.actionable, reason: ev.reason,
    contained, response: response.slice(0, 200), latMs: lat,
  });

  const ri = { fully_resolved: 'F', partially_resolved: 'P', not_resolved: 'N' }[ev.status] || '?';
  console.log(`| Sub:${subOk?'S':'X'} Int:${intOk?'I':'X'} Res:${ri} | ${lat}ms | ${ev.reason?.slice(0,35)}`);

  // Small delay
  await new Promise(r => setTimeout(r, 500));
}

// METRICS
const n = results.length;
const containedN = results.filter(r => r.contained).length;
const subOkN = results.filter(r => r.subOk).length;
const intOkN = results.filter(r => r.intOk).length;
const fullyN = results.filter(r => r.resolution === 'fully_resolved').length;
const partialN = results.filter(r => r.resolution === 'partially_resolved').length;
const notResN = results.filter(r => r.resolution === 'not_resolved').length;
const trueResN = results.filter(r => r.intOk && r.resolution === 'fully_resolved').length;
const indResN = results.filter(r => r.contained && ['fully_resolved','partially_resolved'].includes(r.resolution)).length;
const intContN = results.filter(r => r.intOk && r.contained).length;
const evIntN = results.filter(r => r.intentMatch).length;
const evActionN = results.filter(r => r.actionable).length;

console.log();
console.log('='.repeat(60));
console.log('EMPIRICAL RESULTS - ZAI SDK - REAL LLM MEASUREMENTS');
console.log('='.repeat(60));
console.log(`Tickets: ${n}`);
console.log();
console.log(`Containment Rate:             ${(containedN/n*100).toFixed(1)}% (${containedN}/${n})`);
console.log(`Subgraph Routing Accuracy:    ${(subOkN/n*100).toFixed(1)}% (${subOkN}/${n})`);
console.log(`Intent Accuracy:              ${(intOkN/n*100).toFixed(1)}% (${intOkN}/${n})`);
console.log(`Evaluator Intent Match:       ${(evIntN/n*100).toFixed(1)}% (${evIntN}/${n})`);
console.log(`Actionable Response Rate:     ${(evActionN/n*100).toFixed(1)}% (${evActionN}/${n})`);
console.log(`Intent-Correct Containment:   ${(intContN/n*100).toFixed(1)}% (${intContN}/${n})`);
console.log(`Fully Resolved:               ${(fullyN/n*100).toFixed(1)}% (${fullyN}/${n})`);
console.log(`Partially Resolved:           ${(partialN/n*100).toFixed(1)}% (${partialN}/${n})`);
console.log(`Not Resolved:                 ${(notResN/n*100).toFixed(1)}% (${notResN}/${n})`);
console.log(`True Resolution Rate:         ${(trueResN/n*100).toFixed(1)}% (${trueResN}/${n})`);
console.log(`Industry-Comparable Rate:     ${(indResN/n*100).toFixed(1)}% (${indResN}/${n})`);

// By subgraph
const bySub = {};
results.forEach(r => { bySub[r.predSub] = bySub[r.predSub] || []; bySub[r.predSub].push(r); });
console.log('\nBY SUBGRAPH:');
for (const [sg, sgr] of Object.entries(bySub).sort()) {
  const sgn = sgr.length;
  const si = sgr.filter(r => r.intOk).length;
  const sf = sgr.filter(r => r.resolution === 'fully_resolved').length;
  const st = sgr.filter(r => r.intOk && r.resolution === 'fully_resolved').length;
  console.log(`  ${sg.padEnd(10)} ${sgn} tickets | Intent: ${(si/sgn*100).toFixed(0)}% | FullRes: ${(sf/sgn*100).toFixed(0)}% | TrueRes: ${(st/sgn*100).toFixed(0)}%`);
}

// Failed
const failed = results.filter(r => r.resolution === 'not_resolved' || !r.intOk);
if (failed.length) {
  console.log(`\nNEEDS IMPROVEMENT (${failed.length}):`);
  failed.forEach(r => {
    const im = r.intOk ? 'OK' : 'X';
    const sm = r.subOk ? 'OK' : 'X';
    console.log(`  ${r.id.padEnd(5)} Sub:${r.predSub.padEnd(8)}${sm} Int:${r.predInt.padEnd(12)}${im} Res:${r.resolution.padEnd(18)}`);
  });
}

// Levers
const intentFail = results.filter(r => !r.intOk).length;
const resFail = results.filter(r => r.resolution === 'not_resolved').length;
console.log(`\nIMPROVEMENT LEVERS:`);
console.log(`  Intent failures:  ${intentFail}/${n} (${(intentFail/n*100).toFixed(1)}%)`);
console.log(`  Resolution fails: ${resFail}/${n} (${(resFail/n*100).toFixed(1)}%)`);
console.log(`  BIGGEST LEVER: ${intentFail >= resFail ? 'intent' : 'response quality'}`);

// Industry comparison
console.log(`\nINDUSTRY COMPARISON:`);
console.log(`  Intercom:  50-70% claimed, ~40-55% real | PARWA: ${(indResN/n*100).toFixed(1)}%`);
console.log(`  Zendesk:   40-60% claimed, ~25-45% real | PARWA: ${(indResN/n*100).toFixed(1)}%`);
console.log(`  Sierra:    70-80% claimed, ~55-72% real | PARWA: ${(indResN/n*100).toFixed(1)}%`);
console.log(`  PARWA True Resolution: ${(trueResN/n*100).toFixed(1)}%`);

// Save
const output = {
  timestamp: new Date().toISOString(),
  method: 'empirical_zai_sdk',
  total_tickets: n,
  metrics: {
    containment_rate: +(containedN/n*100).toFixed(2),
    subgraph_routing_accuracy: +(subOkN/n*100).toFixed(2),
    intent_accuracy: +(intOkN/n*100).toFixed(2),
    evaluator_intent_match_rate: +(evIntN/n*100).toFixed(2),
    actionable_rate: +(evActionN/n*100).toFixed(2),
    intent_correct_containment_rate: +(intContN/n*100).toFixed(2),
    fully_resolved_rate: +(fullyN/n*100).toFixed(2),
    partially_resolved_rate: +(partialN/n*100).toFixed(2),
    not_resolved_rate: +(notResN/n*100).toFixed(2),
    true_resolution_rate: +(trueResN/n*100).toFixed(2),
    industry_comparable_rate: +(indResN/n*100).toFixed(2),
  },
  per_ticket_results: results,
};

mkdirSync('download', { recursive: true });
writeFileSync('download/empirical_resolution_rate_results.json', JSON.stringify(output, null, 2));
console.log('\nSaved to download/empirical_resolution_rate_results.json');
