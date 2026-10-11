"""Probe: which computed-body forms does the Superglue postgres engine accept?

A: body = "<<(sourceData) => '{\"query\": \"SELECT 42 as answer\"}'>>"   (template ref)
B: body = "(sourceData) => '{\"query\": \"SELECT 43 as answer\"}'"       (bare arrow fn)
C: body = static string with input ref (control — expected to work)
"""
import httpx, json

BASE = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai"
KEY = "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

PG = "postgres://superglue:superglue@127.0.0.1:5432/demo_db"

CASES = {
    "A_template_ref": "<<(sourceData) => '{\"query\": \"SELECT 42 as answer\"}'>>",
    "B_bare_arrow": "(sourceData) => '{\"query\": \"SELECT 43 as answer\"}'",
    "C_static_input": "{\"query\": \"SELECT 44 as answer\"}",
}

for name, body in CASES.items():
    tid = f"probe_body_{name.lower()}"
    tool = {
        "id": tid,
        "name": f"Probe {name}",
        "instruction": "probe",
        "inputSchema": {"type": "object", "properties": {}},
        "steps": [{
            "id": "step1",
            "instruction": "run probe query",
            "config": {"type": "request", "method": "POST", "systemId": "sandbox_postgres", "url": PG, "body": body},
        }],
    }
    cr = httpx.post(f"{BASE}/sgapi/v1/tools", headers=H, json=tool, timeout=30)
    rr = httpx.post(f"{BASE}/sgapi/v1/tools/{tid}/run", headers=H, json={"inputs": {}}, timeout=60)
    res = rr.json() if rr.status_code in (200, 202) else {}
    ok = res.get("status")
    err = ""
    for sr in res.get("stepResults") or []:
        if not sr.get("success"):
            err = str(sr.get("error"))[:160]
    data = str(res.get("data"))[:120]
    print(f"{name:16s} create={cr.status_code} run={rr.status_code} status={ok} data={data} err={err}")
    httpx.delete(f"{BASE}/sgapi/v1/tools/{tid}", headers=H, timeout=30)
