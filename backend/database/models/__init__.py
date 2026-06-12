"""
PARWA Phase 3 — Models Package

Imports and re-exports every ORM model so that:

* A single ``import backend.database.models`` registers all tables
  with the SQLAlchemy ``Base.metadata`` (required before ``create_all``).
* Downstream code can reference models directly:
  ``from database.models import Company, Ticket, …``
"""

# ---------------------------------------------------------------------------
# Core — Company, User, CompanySetting
# ---------------------------------------------------------------------------
from .core import Company, CompanySetting, User

# ---------------------------------------------------------------------------
# Integration — Integration, EventBuffer
# ---------------------------------------------------------------------------
from .integration import EventBuffer, Integration

# ---------------------------------------------------------------------------
# Notification — Notification
# ---------------------------------------------------------------------------
from .notification import Notification

# ---------------------------------------------------------------------------
# Ticket — Ticket, TicketMessage
# ---------------------------------------------------------------------------
from .ticket import Ticket, TicketMessage

# ---------------------------------------------------------------------------
# Knowledge — KnowledgeDocument, FAQ
# ---------------------------------------------------------------------------
from .knowledge import FAQ, KnowledgeDocument

# ---------------------------------------------------------------------------
# Custom Connector — CustomConnector
# ---------------------------------------------------------------------------
from .custom_connector import CustomConnector

# ---------------------------------------------------------------------------
# SLA — SLARule
# ---------------------------------------------------------------------------
from .sla import SLARule

# ---------------------------------------------------------------------------
# Convenience: explicit __all__ for star-imports and static analysis
# ---------------------------------------------------------------------------

__all__ = [
    # Core
    "Company",
    "User",
    "CompanySetting",
    # Integration
    "Integration",
    "EventBuffer",
    # Notification
    "Notification",
    # Ticket
    "Ticket",
    "TicketMessage",
    # Knowledge
    "KnowledgeDocument",
    "FAQ",
    # Custom Connector
    "CustomConnector",
    # SLA
    "SLARule",
]
