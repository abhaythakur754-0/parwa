"""
Webhook Signature Utilities
Enterprise Integration Hub - Week 43 Builder 4
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class SignatureResult:
    """Result of signature verification"""
    valid: bool
    algorithm: str
    timestamp: Optional[int] = None
    error: Optional[str] = None


class WebhookSigner:
    """Handles webhook signing and verification"""
    
    SUPPORTED_ALGORITHMS = ["sha256", "sha384", "sha512"]
    DEFAULT_ALGORITHM = "sha256"
    TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes
    
    def __init__(
        self,
        default_algorithm: str = "sha256",
        timestamp_tolerance: int = 300
    ):
        self.default_algorithm = default_algorithm
        self.timestamp_tolerance = timestamp_tolerance
    
    def sign(
        self,
        secret: str,
        payload: Dict[str, Any],
        algorithm: Optional[str] = None,
        include_timestamp: bool = True
    ) -> str:
        """
        Sign a webhook payload.
        
        Args:
            secret: Secret key for signing
            payload: Payload to sign
            algorithm: Hash algorithm to use
            include_timestamp: Whether to include timestamp in signature
            
        Returns:
            Signature string
        """
        algorithm = algorithm or self.default_algorithm
        
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Create canonical payload
        canonical = self._canonicalize(payload)
        
        # Add timestamp if requested
        if include_timestamp:
            timestamp = int(time.time())
            canonical = f"{timestamp}.{canonical}"
        
        # Generate signature
        hash_func = getattr(hashlib, algorithm)
        signature = hmac.new(
            secret.encode(),
            canonical.encode(),
            hash_func
        ).hexdigest()
        
        if include_timestamp:
            return f"t={timestamp},v1={signature}"
        else:
            return f"{algorithm}={signature}"
    
    def verify(
        self,
        secret: str,
        payload: Dict[str, Any],
        signature_header: str,
        max_age_seconds: Optional[int] = None
    ) -> SignatureResult:
        """
        Verify a webhook signature.
        
        Args:
            secret: Secret key for verification
            payload: Received payload
            signature_header: Signature header value
            max_age_seconds: Maximum age of signature (for timestamp validation)
            
        Returns:
            SignatureResult with verification status
        """
        max_age = max_age_seconds or self.timestamp_tolerance
        
        try:
            # Parse signature header
            algorithm, signature, timestamp = self._parse_signature_header(signature_header)
            
            if algorithm not in self.SUPPORTED_ALGORITHMS:
                return SignatureResult(
                    valid=False,
                    algorithm=algorithm,
                    error=f"Unsupported algorithm: {algorithm}"
                )
            
            # Check timestamp if present
            if timestamp:
                current_time = int(time.time())
                age = current_time - timestamp
                
                if age > max_age:
                    return SignatureResult(
                        valid=False,
                        algorithm=algorithm,
                        timestamp=timestamp,
                        error=f"Signature expired: {age}s old (max {max_age}s)"
                    )
            
            # Compute expected signature
            canonical = self._canonicalize(payload)
            
            if timestamp:
                canonical = f"{timestamp}.{canonical}"
            
            hash_func = getattr(hashlib, algorithm)
            expected = hmac.new(
                secret.encode(),
                canonical.encode(),
                hash_func
            ).hexdigest()
            
            # Compare signatures
            expected_header = f"{algorithm}={expected}"
            if timestamp:
                expected_header = f"t={timestamp},v1={expected}"
            
            if hmac.compare_digest(signature_header, expected_header):
                return SignatureResult(
                    valid=True,
                    algorithm=algorithm,
                    timestamp=timestamp
                )
            else:
                return SignatureResult(
                    valid=False,
                    algorithm=algorithm,
                    timestamp=timestamp,
                    error="Signature mismatch"
                )
                
        except Exception as e:
            return SignatureResult(
                valid=False,
                algorithm="unknown",
                error=str(e)
            )
    
    def _parse_signature_header(
        self,
        header: str
    ) -> Tuple[str, str, Optional[int]]:
        """Parse signature header into components"""
        timestamp = None
        signature = ""
        algorithm = self.default_algorithm
        
        # Stripe-style: t=1234567890,v1=abc123
        if header.startswith("t="):
            parts = header.split(",")
            for part in parts:
                if part.startswith("t="):
                    timestamp = int(part[2:])
                elif part.startswith("v1="):
                    signature = part[3:]
                    algorithm = "sha256"
        
        # Standard style: sha256=abc123
        elif "=" in header and not header.startswith("t="):
            algo, sig = header.split("=", 1)
            algorithm = algo
            signature = sig
        
        else:
            # Raw signature (assume default algorithm)
            signature = header
        
        return algorithm, signature, timestamp
    
    def _canonicalize(self, payload: Dict[str, Any]) -> str:
        """Create canonical string representation of payload"""
        return json.dumps(payload, sort_keys=True, separators=(',', ':'))
    
    def create_signature_headers(
        self,
        secret: str,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Create complete signature headers for a webhook request"""
        signature = self.sign(secret, payload)
        
        headers = {
            "X-Signature": signature,
            "X-Signature-Algorithm": self.default_algorithm
        }
        
        if webhook_id:
            headers["X-Webhook-ID"] = webhook_id
        
        return headers
    
    def verify_request(
        self,
        secret: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> SignatureResult:
        """Verify a webhook request from headers"""
        signature = headers.get("X-Signature") or headers.get("X-Hub-Signature-256")
        
        if not signature:
            return SignatureResult(
                valid=False,
                algorithm="none",
                error="No signature header found"
            )
        
        return self.verify(secret, payload, signature)


class MultiSigner:
    """Support for multiple signing keys (key rotation)"""
    
    def __init__(self):
        self._signers: Dict[str, WebhookSigner] = {}
        self._primary_key: Optional[str] = None
    
    def add_key(
        self,
        key_id: str,
        secret: str,
        is_primary: bool = False
    ) -> None:
        """Add a signing key"""
        self._signers[key_id] = WebhookSigner()
        
        if is_primary or not self._primary_key:
            self._primary_key = key_id
    
    def remove_key(self, key_id: str) -> None:
        """Remove a signing key"""
        if key_id in self._signers:
            del self._signers[key_id]
        
        if self._primary_key == key_id:
            self._primary_key = next(iter(self._signers), None)
    
    def sign_with_primary(
        self,
        secret: str,
        payload: Dict[str, Any]
    ) -> str:
        """Sign with the primary key"""
        if not self._primary_key or self._primary_key not in self._signers:
            raise ValueError("No primary key configured")
        
        signer = self._signers[self._primary_key]
        return signer.sign(secret, payload)
    
    def verify_with_any(
        self,
        secret: str,
        payload: Dict[str, Any],
        signature: str
    ) -> SignatureResult:
        """Verify with any available key"""
        for signer in self._signers.values():
            result = signer.verify(secret, payload, signature)
            if result.valid:
                return result
        
        return SignatureResult(
            valid=False,
            algorithm="none",
            error="No valid key found for signature"
        )
