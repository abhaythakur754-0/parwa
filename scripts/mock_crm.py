"""
Mock CRM receiver for LOCAL testing of the HumanReplacement flow.

Listens on :9099, records every JSON POST (the escalation / response
pushes Parwa sends to a tenant's generic CRM webhook) to a JSONL file,
and answers 200 {"ok": true} — mirroring what a real CRM endpoint does.

Usage:
    python3 scripts/mock_crm.py            # foreground
    LOG=/home/z/my-project/.mock_crm_log.jsonl
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = os.environ.get("LOG", "/home/z/my-project/.mock_crm_log.jsonl")
PORT = int(os.environ.get("PORT", "9099"))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            body = {"_raw": raw.decode("utf-8", "replace")[:2000]}
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": self.path,
            "body": body,
        }
        with open(LOG, "a") as fh:
            fh.write(json.dumps(entry) + "\n")
        print(f"[mock-crm] POST {self.path} event={body.get('event', '?')} "
              f"ticket_id={body.get('ticket_id', '?')}", flush=True)
        payload = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence default request logging
        return


if __name__ == "__main__":
    open(LOG, "w").close()  # truncate log each run
    print(f"[mock-crm] listening on :{PORT}, log={LOG}", flush=True)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
