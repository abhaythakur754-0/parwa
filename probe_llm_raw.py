"""Ground-truth probe: same prompt as generator, dump FULL raw LLM response."""
import asyncio, json, sys
sys.path.insert(0, "/home/z/parwa/backend")
import httpx
from app.core.superglue_client import _get_llm_key, _get_llm_model, _get_llm_url
from app.core.superglue_tool_generator import (
    _TOOL_JSON_SPEC, _build_tool_instruction,
)

INSTRUCTION = _build_tool_instruction(
    "CRM Stage Updater",
    ("You update CRM deal stages. Tenant integration: sandbox_postgres — Postgres "
     "demo DB. Request steps use systemId 'sandbox_postgres', url "
     "'postgres://superglue:superglue@127.0.0.1:5432/demo_db', SQL in body as "
     "{\"query\": \"SELECT ...\"}. Table crm_contacts(id,name,email,company,stage,value_usd)."),
    "crm_updates, contact_stage_changes",
    "Priya from Acme (priya@acme.com) closed — mark stage 'won'.",
    {"sandbox_postgres": {"type": "postgres", "database": "demo_db"}},
)

SYSTEM = (
    "You are a Superglue tool designer. You respond with EXACTLY two "
    "fenced blocks and nothing else: (1) a ```json block with the tool "
    "JSON, where every transform is the marker @@T1@@, @@T2@@, ... ; "
    "(2) a ```js block defining each marker as a single-expression "
    "arrow function, one per line, e.g. @@T1@@ = (sourceData) => ... "
    "Never write JavaScript inside the JSON block."
)
USER = INSTRUCTION + "\n\nRespond with ONLY the tool JSON in exactly this format:\n" + _TOOL_JSON_SPEC

async def main():
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(_get_llm_url(), headers={
            "Authorization": f"Bearer {_get_llm_key()}", "Content-Type": "application/json",
        }, json={
            "model": _get_llm_model(),
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": USER}],
            "max_tokens": 2600, "temperature": 0.2,
        })
    print("status:", r.status_code)
    content = r.json()["choices"][0]["message"]["content"]
    print("RAW LEN:", len(content))
    print("=" * 70)
    print(content)
    print("=" * 70)
    # analysis
    import re
    used = set(re.findall(r'"transformCode"\s*:\s*"@@([\w-]+)@@"', content))
    used |= set(re.findall(r'"outputTransform"\s*:\s*"@@([\w-]+)@@"', content))
    blocks = re.findall(r'```(?:js|javascript)\s*([\s\S]*?)```', content)
    defined = set()
    for b in blocks:
        defined |= set(re.findall(r'@@([\w-]+)@@\s*=', b))
    print("USED markers   :", sorted(used))
    print("DEFINED markers:", sorted(defined))
    print("MISSING        :", sorted(used - defined))
    print("js blocks found:", len(blocks))

asyncio.run(main())
