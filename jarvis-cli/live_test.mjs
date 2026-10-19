/**
 * Jarvis CLI — LIVE integration test (no LLM required).
 *
 * Boots nothing itself: point it at a running backend with a valid token:
 *   PARWA_API_URL=http://localhost:10000 \
 *   PARWA_API_TOKEN=<jwt> \
 *   node jarvis-cli/live_test.mjs
 *
 * Verifies the wired executors return REAL backend data (not mocks):
 *   health, ticket stats, recent tickets, subscription, integrations,
 *   pause/resume round-trip (on the Jarvis control plane).
 *
 * Exit 0 = all wired tools answered with real data. Exit 1 = any failure.
 */

import { REAL_EXECUTORS, isLive } from './backend-api.mjs';

const results = [];
function check(name, ok, detail = "") {
  results.push(ok);
  console.log(`   ${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}

async function main() {
  console.log("=== JARVIS CLI LIVE WIRING TEST ===");
  if (!isLive()) {
    console.error("FAIL  PARWA_API_TOKEN not set — refusing to test demo mode as 'live'");
    process.exit(1);
  }

  // 1. Health (real backend, not the hardcoded "healthy" string)
  const health = await REAL_EXECUTORS.check_system_health();
  check("check_system_health hits real backend", health.success === true, health.message?.slice(0, 90));

  // 2. Ticket stats — real numbers, no demo tag
  const stats = await REAL_EXECUTORS.get_ticket_stats();
  check("get_ticket_stats returns real counts", stats.success === true && !String(stats.message).includes("[demo"), stats.message?.slice(0, 90));

  // 3. Recent tickets list
  const list = await REAL_EXECUTORS.list_recent_tickets({ count: 5 });
  check("list_recent_tickets returns real tickets", list.success === true, list.message?.slice(0, 90));

  // 4. Subscription (billing API)
  const sub = await REAL_EXECUTORS.get_subscription_info();
  check("get_subscription_info reaches billing API", sub.success === true, sub.message?.slice(0, 90));

  // 5. Integrations
  const integ = await REAL_EXECUTORS.list_integrations();
  check("list_integrations reaches integrations API", integ.success === true, integ.message?.slice(0, 90));

  // 6. Pause → resume round-trip on the real control plane
  const paused = await REAL_EXECUTORS.pause_all_ai();
  check("pause_all_ai accepted by control plane", paused.success === true, paused.message?.slice(0, 80));
  const resumed = await REAL_EXECUTORS.resume_all_ai();
  check("resume_all_ai accepted by control plane", resumed.success === true, resumed.message?.slice(0, 80));

  const passed = results.filter(Boolean).length;
  console.log(`\nRESULT: ${passed}/${results.length} checks passed`);
  if (passed !== results.length) process.exit(1);
  console.log("JARVIS CLI LIVE WIRING: ALL CHECKS PASSED");
}

main().catch(err => { console.error("FATAL:", err); process.exit(1); });
