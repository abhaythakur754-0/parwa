"""
Shared fixtures for the AI QA + Ghostwriter test suites.

In-memory SQLite per test (house pattern, same as
test_jarvis_awareness_integration.py): real ORM models, real queries,
FK enforcement off so no users/companies rows are needed.
Only the tables under test are created — keeps the harness light.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# litellm is heavy and is MOCKED in every test here — shim it so the
# suites stay hermetic (no LLM package, no keys, no network).
try:
    import litellm  # noqa: F401
except ImportError:  # pragma: no cover - depends on environment
    sys.modules.setdefault("litellm", MagicMock())

from database.base import Base
from database.models.jarvis import JarvisMessage
from database.models.qa_score import QAReportCard
from database.models.ghostwriter import GhostwriterDraft
from database.models.onboarding import DocumentChunk, KnowledgeDocument


@pytest.fixture()
def in_memory_db():
    """Fresh SQLite in-memory DB per test with exactly the tables needed."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    tables = [
        JarvisMessage.__table__,
        QAReportCard.__table__,
        GhostwriterDraft.__table__,
        KnowledgeDocument.__table__,
        DocumentChunk.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()

    yield lambda: db

    db.close()
    engine.dispose()
