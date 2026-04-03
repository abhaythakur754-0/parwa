"""
External API Clients

This package contains clients for external services:
- paddle_client: Paddle billing/subscription API
"""

from backend.app.clients.paddle_client import PaddleClient, get_paddle_client

__all__ = ["PaddleClient", "get_paddle_client"]
