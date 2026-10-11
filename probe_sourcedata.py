"""Probe H: dump the full sourceData shape via outputTransform."""
import httpx, json

BASE = "https://preview-chat-98e04084-5e3a-4783-865f-1b226d21cc01.space-z.ai"
KEY = "sg_fbde45884a601f06d4d10a6d9300eb546223c2784ca66f0b"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
PG = "postgres://superglue:superglue@127.0.0.1:5432/demo_db"

tool = {
    "id": "probe_sourcedata_shape",
    "name": "Probe sourceData shape",
    "instruction": "probe",
    "inputSchema": {"type": "object", "properties": {}},
    "steps": [
        {
            "id": "step1",
            "instruction": "transform returning an object",
            "config": {"type": "transform", "transformCode": "(sourceData) => ({hello: 'world', n: 7})"},
        },
        {
            "id": "step2",
            "instruction": "static query",
            "config": {"type": "request", "method": "POST", "systemId": "sandbox_postgres", "url": PG,
                        "body": "{\"query\": \"SELECT 46 as answer\"}"},
        },
    ],
    "outputTransform": "(sourceData) => JSON.stringify({keys: Object.keys(sourceData), step1: sourceData.step1, step2: sourceData.step2})",
}
cr = httpx.post(f"{BASE}/sgapi/v1/tools", headers=H, json=tool, timeout=30)
rr = httpx.post(f"{BASE}/sgapi/v1/tools/probe_sourcedata_shape/run", headers=H, json={"inputs": {}}, timeout=60)
res = rr.json() if rr.status_code in (200, 202) else {}
print("create:", cr.status_code, "run:", rr.status_code, "status:", res.get("status"))
print("data:", res.get("data"))
for sr in res.get("stepResults") or []:
    if not sr.get("success"):
        print("step err:", str(sr.get("error"))[:200])
httpx.delete(f"{BASE}/sgapi/v1/tools/probe_sourcedata_shape", headers=H, timeout=30)
