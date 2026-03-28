"""
Database Index Module for PARWA Performance Optimization.

This module provides optimized database indexes for all core tables
to ensure P95 latency < 300ms at 500 concurrent users.

Week 26 - Builder 1: Database Index Optimization

Index Categories:
- Ticket indexes: Support ticket queries and filtering
- Client indexes: Multi-tenant isolation and client lookups
- Interaction indexes: Conversation and interaction history
- Audit indexes: Compliance and audit trail queries
"""

from pathlib import Path

# SQL file paths for index creation
INDEX_DIR = Path(__file__).parent

TICKET_INDEXES = INDEX_DIR / "ticket_indexes.sql"
CLIENT_INDEXES = INDEX_DIR / "client_indexes.sql"
INTERACTION_INDEXES = INDEX_DIR / "interaction_indexes.sql"
AUDIT_INDEXES = INDEX_DIR / "audit_indexes.sql"

# Index statistics tracking
INDEX_STATS = {
    "ticket_indexes": 6,
    "client_indexes": 5,
    "interaction_indexes": 5,
    "audit_indexes": 5,
    "total_indexes": 21,
}

# Performance targets
PERFORMANCE_TARGETS = {
    "query_time_ms": 10,  # Target: <10ms for indexed queries
    "p95_latency_ms": 300,  # Target: P95 <300ms at 500 users
    "index_hit_rate": 0.95,  # Target: 95% index hit rate
}


def get_index_files() -> dict:
    """
    Get all index SQL files with their paths.

    Returns:
        Dictionary mapping index category to file path.
    """
    return {
        "ticket": TICKET_INDEXES,
        "client": CLIENT_INDEXES,
        "interaction": INTERACTION_INDEXES,
        "audit": AUDIT_INDEXES,
    }


def validate_indexes_exist() -> bool:
    """
    Validate that all index SQL files exist.

    Returns:
        True if all index files exist, False otherwise.
    """
    for name, path in get_index_files().items():
        if not path.exists():
            return False
    return True


__all__ = [
    "INDEX_DIR",
    "TICKET_INDEXES",
    "CLIENT_INDEXES",
    "INTERACTION_INDEXES",
    "AUDIT_INDEXES",
    "INDEX_STATS",
    "PERFORMANCE_TARGETS",
    "get_index_files",
    "validate_indexes_exist",
]
