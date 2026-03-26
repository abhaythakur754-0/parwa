"""
Performance Tests Module.

This module contains load and performance tests for the PARWA system.
Uses Locust for load testing with configurable user counts and scenarios.

CRITICAL REQUIREMENT: P95 latency <500ms at 50 concurrent users
"""

__all__ = [
    "load_test_config",
]
