"""E2E: PARWA generate_tool_for_agent() -> Superglue LLM -> save -> run -> delete.

Measures wall-clock per phase and captures the generator's diagnostic logs
(retry reasons, raw-content head/tail on parse failures).
"""
import asyncio
import logging
import sys
import time

sys.path.insert(0, "/home/z/parwa/backend")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logging.getLogger("parwa.superglue_tool_generator").setLevel(logging.DEBUG)

from app.core.superglue_client import execute_tool  # noqa: E402
from app.core.superglue_tool_generator import (  # noqa: E402
    check_tool_status,
    disable_tool,
    generate_tool_for_agent,
)


AGENT = {
    "agent_name": "CRM Stage Updater",
    "agent_instructions": (
        "You update CRM deal stages for customers. Tenant integration: "
        "sandbox_postgres — a Postgres demo DB. Request steps must use "
        "systemId 'sandbox_postgres', url "
        "'postgres://superglue:superglue@127.0.0.1:5432/demo_db', and put "
        "the SQL in body as {\"query\": \"SELECT ...\"}. Table: "
        "crm_contacts(id, name, email, company, stage, value_usd). "
        "Stages: new, qualified, proposal, won, lost."
    ),
    "agent_capabilities": "crm_updates, contact_stage_changes",
    "sample_ticket": (
        "Hi, I'm Noah from Delta (noah@delta.ai). We just closed — "
        "please mark our deal as 'won' in your CRM."
    ),
    "tenant_integrations": {
        "sandbox_postgres": {"type": "postgres", "database": "demo_db"},
    },
    "trial_run_inputs": {"customerEmail": "noah@delta.ai", "newStage": "won"},
}


async def main() -> None:
    t0 = time.time()
    gen = await generate_tool_for_agent(**AGENT)
    t_gen = time.time() - t0

    print("\n================ GENERATE RESULT ================")
    print(f"success        : {gen.get('success')}")
    print(f"tool_id        : {gen.get('tool_id')}")
    print(f"generated_by   : {gen.get('generated_by')}")
    print(f"after_retry    : {gen.get('generated_after_retry')}")
    print(f"error          : {gen.get('error')}")
    print(f"WALL CLOCK gen : {t_gen:.1f}s")
    if gen.get("tool_definition"):
        import json
        print("steps          :", json.dumps(gen["tool_definition"].get("steps", []), indent=1)[:1500])
    if not gen.get("success"):
        sys.exit(2)

    tool_id = gen["tool_id"]

    # verify it is registered
    t1 = time.time()
    chk = await check_tool_status(tool_id)
    print(f"\ncheck_tool_status: {chk.get('status')} ({time.time()-t1:.1f}s)")

    # RUN the generated tool with real inputs
    t2 = time.time()
    run = await execute_tool(tool_id, {"customerEmail": "noah@delta.ai", "newStage": "won"})
    t_run = time.time() - t2
    print("\n================ RUN RESULT =====================")
    print(f"run success    : {run.get('success')}")
    print(f"run error      : {run.get('error')}")
    print(f"WALL CLOCK run : {t_run:.1f}s")
    print("run data       :", str(run.get("data"))[:600])
    print("step_results   :", run.get("step_results"))

    # cleanup — leave the workspace exactly as we found it
    t3 = time.time()
    removed = await disable_tool(tool_id)
    print(f"\ncleanup delete : {removed} ({time.time()-t3:.1f}s)")
    print(f"\nTOTAL E2E      : {time.time()-t0:.1f}s")


asyncio.run(main())
