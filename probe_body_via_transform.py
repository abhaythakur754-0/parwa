"""Probe I: the full computed-body pattern.
transform produces the body JSON string -> request body references it.
UPDATE targets a fake email = zero rows matched = no data mutation.
"""
import httpx, json

BASE = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai"
KEY = "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
PG = "postgres://superglue:superglue@127.0.0.1:5432/demo_db"

tool = {
    "id": "probe_body_via_transform",
    "name": "Probe body via transform",
    "instruction": "probe",
    "inputSchema": {"type": "object", "properties": {}},
    "steps": [
        {
            "id": "step1",
            "instruction": "produce the UPDATE body JSON string (marker-style JS lives here)",
            "config": {
                "type": "transform",
                "transformCode": "(sourceData) => JSON.stringify({query: \"UPDATE crm_contacts SET stage = 'won' WHERE email = 'nobody@probe.test'\"})",
            },
        },
        {
            "id": "step2",
            "instruction": "run the update using the produced body",
            "config": {
                "type": "request", "method": "POST", "systemId": "sandbox_postgres", "url": PG,
                "body": "<<(sourceData) => sourceData.step1.data>>",
            },
        },
    ],
}
cr = httpx.post(f"{BASE}/sgapi/v1/tools", headers=H, json=tool, timeout=30)
rr = httpx.post(f"{BASE}/sgapi/v1/tools/probe_body_via_transform/run", headers=H, json={"inputs": {}}, timeout=60)
res = rr.json() if rr.status_code in (200, 202) else {}
print("create:", cr.status_code, "run:", rr.status_code, "status:", res.get("status"))
print("data:", str(res.get("data"))[:200])
for sr in res.get("stepResults") or []:
    if not sr.get("success"):
        print("step err:", str(sr.get("error"))[:200])
httpx.delete(f"{BASE}/sgapi/v1/tools/probe_body_via_transform", headers=H, timeout=30)
