"""Webhook Signer - HMAC Signature Generation"""
from typing import Dict, Optional, Any
import hashlib
import hmac
import json
import time
import logging

logger = logging.getLogger(__name__)

class WebhookSigner:
    def __init__(self, algorithm: str = "sha256"):
        self.algorithm = algorithm
        self._prefix = "whsec"

    def sign(self, payload: Any, secret: str, timestamp: Optional[int] = None) -> str:
        ts = timestamp or int(time.time())
        payload_str = json.dumps(payload, separators=(',', ':')) if not isinstance(payload, str) else payload
        signed_payload = f"{ts}.{payload_str}"
        signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return f"t={ts},v1={signature}"

    def verify(self, payload: Any, secret: str, signature_header: str, tolerance_seconds: int = 300) -> bool:
        try:
            parts = dict(part.split('=', 1) for part in signature_header.split(','))
            timestamp = int(parts.get('t', 0))
            expected_sig = parts.get('v1', '')

            current_time = int(time.time())
            if abs(current_time - timestamp) > tolerance_seconds:
                logger.warning("Webhook signature timestamp expired")
                return False

            payload_str = json.dumps(payload, separators=(',', ':')) if not isinstance(payload, str) else payload
            signed_payload = f"{timestamp}.{payload_str}"
            computed_sig = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()

            return hmac.compare_digest(expected_sig, computed_sig)
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    def compute_signature(self, payload: str, secret: str) -> str:
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def create_signed_payload(self, event_type: str, data: Dict[str, Any], secret: str) -> Dict[str, Any]:
        timestamp = int(time.time())
        payload = {"event": event_type, "data": data, "timestamp": timestamp}
        signature = self.sign(payload, secret, timestamp)
        payload["signature"] = signature
        return payload
