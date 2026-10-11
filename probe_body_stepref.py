"""Probe: can a request body reference a previous step's result directly?

D: step1 transform returns the body-JSON string; step2 body = "<<step1>>"
E: step1 transform returns the body-JSON string; step2 body = "<<(sourceData) => sourceData.step1>>"
"""
import httpx, json

BASE = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai"
KEY = "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
PG = "postgres://superglue:superglue@127.0.0.1:5432/demo_db"

CASES = {
    "D_step_ref": "<<step1>>",
    "E_arrow_step_ref": "<<(sourceData) => sourceData.step1>>",
}

for name, body in CASES.items():
    tid = f"probe_body_{name.lower()}"
    tool = {
        "id": tid,
        "name": f"Probe {name}",
        "instruction": "probe",
        "inputSchema": {"type": "object", "properties": {}},
        "steps": [
            {
                "id": "step1",
                "instruction": "build the SQL body JSON string",
                "config": {
                    "type": "transform",
                    "transformCode": "(sourceData) => JSON.stringify({query: 'SELECT 45 as answer'})",
                },
            },
            {
                "id": "step2",
                "instruction": "run the query",
                "config": {"type": "request", "method": "POST", "systemId": "sandbox_postgres", "url": PG, "body": body},
            },
        ],
    }
    cr = httpx.post(f"{BASE}/sgapi/v1/tools", headers=H, json=tool, timeout=30)
    rr = httpx.post(f"{BASE}/sgapi/v1/tools/{tid}/run", headers=H, json={"inputs": {}}, timeout=60)
    res = rr.json() if rr.status_code in (200, 202) else {}
    err = ""
    for sr in res.get("stepResults") or []:
        if not sr.get("success"):
            err = str(sr.get("error"))[:150]
    print(f"{name:18s} create={cr.status_code} run={rr.status_code} status={res.get('status')} data={str(res.get('data'))[:100]} err={err}")
    httpx.delete(f"{BASE}/sgapi/v1/tools/{tid}", headers=H, timeout=30)
