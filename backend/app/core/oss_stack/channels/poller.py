"""Channel pollers — email (imap-tools) + telegram (aiogram).

Skeletons, env-gated OFF by default. Each exposes `poll()` that returns
normalized message dicts so the same intake path can be reused later:

  {"channel": "email"|"telegram", "from": str, "subject": str, "text": str}

Enable with:
  OSS_CHANNEL_EMAIL=1  +  KB_EMAIL_IMAP_HOST/USER/PASS/PORT
  OSS_CHANNEL_TELEGRAM=1  +  KB_TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger("parwa.oss.channels")


def _flag(name: str) -> bool:
    return os.environ.get(name, "0").strip() in ("1", "true", "yes", "on")


def poll_email(limit: int = 20) -> List[dict]:
    """Fetch unseen inbox messages via imap-tools. [] when disabled/error."""
    if not _flag("OSS_CHANNEL_EMAIL"):
        return []
    try:
        from imap_tools import MailBox, AND  # type: ignore

        host = os.environ.get("KB_EMAIL_IMAP_HOST", "")
        user = os.environ.get("KB_EMAIL_IMAP_USER", "")
        pwd = os.environ.get("KB_EMAIL_IMAP_PASS", "")
        port = int(os.environ.get("KB_EMAIL_IMAP_PORT", "993"))
        if not (host and user and pwd):
            return []
        out: List[dict] = []
        with MailBox(host, port=port).login(user, pwd) as box:
            for msg in box.fetch(AND(seen=False), limit=limit, mark_seen=False):
                out.append(
                    {
                        "channel": "email",
                        "from": msg.from_,
                        "subject": msg.subject or "(no subject)",
                        "text": (msg.text or msg.html or "")[:8000],
                    }
                )
        return out
    except Exception as exc:
        logger.warning("oss_email_poll failed: %s", str(exc)[:200])
        return []


def poll_telegram(limit: int = 20) -> List[dict]:
    """Fetch recent bot updates via aiogram (long-poll, one shot). [] when
    disabled/error. Production should use webhooks + a router."""
    if not _flag("OSS_CHANNEL_TELEGRAM"):
        return []
    token = os.environ.get("KB_TELEGRAM_BOT_TOKEN", "")
    if not token:
        return []
    try:
        import json as _json
        import urllib.request

        url = f"https://api.telegram.org/bot{token}/getUpdates?limit={limit}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        out: List[dict] = []
        for upd in data.get("result", []):
            msg = upd.get("message") or {}
            if not msg:
                continue
            out.append(
                {
                    "channel": "telegram",
                    "from": str((msg.get("from") or {}).get("username", "")),
                    "subject": "telegram",
                    "text": (msg.get("text") or "")[:8000],
                }
            )
        return out
    except Exception as exc:
        logger.warning("oss_telegram_poll failed: %s", str(exc)[:200])
        return []
