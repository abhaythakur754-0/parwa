import hmac
import hashlib
import base64
from typing import Union


def verify_hmac(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verifies an HMAC-SHA256 signature for a given payload and secret.
    Supports both hex and base64 signature formats.
    
    Args:
        payload: The raw request body as bytes.
        signature: The signature string from the request header.
        secret: The shared secret used to generate the signature.
        
    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    # Create local HMAC using SHA256
    local_hmac = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    )
    
    # Check hex format
    if hmac.compare_digest(local_hmac.hexdigest(), signature):
        return True
    
    # Check base64 format
    try:
        # Some webhooks encode the binary HMAC directly in base64
        expected_b64 = base64.b64encode(local_hmac.digest()).decode("utf-8")
        if hmac.compare_digest(expected_b64, signature):
            return True
    except Exception:
        pass

    return False
