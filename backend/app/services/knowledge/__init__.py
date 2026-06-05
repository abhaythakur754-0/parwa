"""
PARWA Knowledge Ingest Service Package

Provides the KnowledgeIngestService for full-pipeline knowledge base
ingestion with progress tracking, file content processing, and URL
auto-ingest.

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — never crashes.
"""

from app.services.knowledge.ingest import KnowledgeIngestService

__all__ = ["KnowledgeIngestService"]
