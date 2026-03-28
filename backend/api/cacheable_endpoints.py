"""
Cacheable Endpoints API for PARWA Performance Optimization.

Week 26 - Builder 4: API Response Caching + Compression
Target: Registry of cacheable endpoints for API layer
"""

import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CacheableEndpointsAPI:
    """API for managing cacheable endpoints."""

    def __init__(self):
        """Initialize the API."""
        from backend.api.cacheable_endpoints import get_cacheable_endpoints
        self.registry = get_cacheable_endpoints()

    def get_endpoint_config(self, path: str, method: str = "GET") -> Optional[Dict]:
        """
        Get configuration for an endpoint.

        Args:
            path: Request path.
            method: HTTP method.

        Returns:
            Endpoint configuration dict.
        """
        endpoint = self.registry.get(path, method)
        if not endpoint:
            return None

        return {
            "path": endpoint.path,
            "ttl": endpoint.ttl,
            "cache_key_params": endpoint.cache_key_params,
            "invalidate_on": endpoint.invalidate_on,
            "tags": endpoint.tags,
            "private": endpoint.private,
        }

    def list_all_endpoints(self) -> List[Dict]:
        """
        List all cacheable endpoints.

        Returns:
            List of endpoint configurations.
        """
        endpoints = []
        for path, endpoint in self.registry.get_all_endpoints().items():
            endpoints.append({
                "path": path,
                "methods": list(endpoint.methods),
                "ttl": endpoint.ttl,
                "tags": endpoint.tags,
            })
        return endpoints


# Global API instance
_api: Optional[CacheableEndpointsAPI] = None


def get_cacheable_endpoints_api() -> CacheableEndpointsAPI:
    """Get the global API instance."""
    global _api
    if _api is None:
        _api = CacheableEndpointsAPI()
    return _api


__all__ = [
    "CacheableEndpointsAPI",
    "get_cacheable_endpoints_api",
]
