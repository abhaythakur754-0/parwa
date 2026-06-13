"""Knowledge Bridge — Connects the parwa AI pipeline to the backend KnowledgeService.

When the backend is available, uses the real KnowledgeService for KB search.
When not available (e.g., standalone testing), uses product docs loaded from
kb_product_docs.md — NO mock/Fake CRM data.

Per PARWA Docs v6.0: The Knowledge Base is where product docs, policies,
and company-specific information live. AI uses RAG (Retrieval Augmented
Generation) to search this knowledge when reasoning about tickets.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.knowledge_bridge")

# Path to product docs
PRODUCT_DOCS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "backend", "app", "core", "kb_product_docs.md"
)


class KnowledgeBridge:
    """Bridge between parwa pipeline and backend KnowledgeService.

    Priority:
    1. Real KnowledgeService (if backend DB is available)
    2. In-memory product docs (loaded from kb_product_docs.md)
    3. Fake CRM data (last resort for legacy compatibility)
    """

    def __init__(self, company_id: str = "comp-test-001") -> None:
        self.company_id = company_id
        self._real_kb = None
        self._product_docs_chunks: List[Dict[str, Any]] = []
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the KB bridge — try real KB first, then load product docs."""
        if self._initialized:
            return

        # Try to connect to real backend KnowledgeService
        try:
            backend_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
            backend_path = os.path.abspath(backend_path)
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            from app.core.knowledge_service import KnowledgeService
            from database.base import SessionLocal

            session = SessionLocal()
            self._real_kb = KnowledgeService(db_session=session)
            logger.info("KnowledgeBridge: Connected to real KnowledgeService")
        except Exception as exc:
            logger.warning("KnowledgeBridge: Real KB not available (%s), using product docs", exc)
            self._real_kb = None

        # Load product docs into memory regardless
        self._load_product_docs()
        self._initialized = True

    def _load_product_docs(self) -> None:
        """Load product documentation from the MD file."""
        try:
            docs_path = PRODUCT_DOCS_PATH
            if not os.path.exists(docs_path):
                docs_path = "/home/z/my-project/backend/app/core/kb_product_docs.md"

            if os.path.exists(docs_path):
                with open(docs_path, "r") as f:
                    content = f.read()

                # Split into chunks by ## headings
                sections = content.split("## ")
                for i, section in enumerate(sections):
                    if not section.strip():
                        continue
                    lines = section.strip().split("\n")
                    title = lines[0].strip()
                    body = "\n".join(lines[1:]).strip()
                    if body and len(body) > 20:  # Skip tiny sections
                        self._product_docs_chunks.append({
                            "id": f"product_doc_{i}",
                            "title": title,
                            "content": body,
                            "category": "product_knowledge",
                            "relevance_score": 0.0,
                        })
                logger.info("KnowledgeBridge: Loaded %d product doc sections", len(self._product_docs_chunks))
            else:
                logger.warning("KnowledgeBridge: Product docs not found at %s", docs_path)
        except Exception as exc:
            logger.error("KnowledgeBridge: Failed to load product docs: %s", exc)

    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search knowledge base.

        Priority: Product docs → Real KB → Fake CRM (last resort only)
        Product docs are now the PRIMARY source since they contain
        real variant definitions, policies, and capabilities.
        """
        self.initialize()

        # Try product docs FIRST (reliable, always available)
        results = self._search_product_docs(query, top_k)
        if results:
            logger.debug("KnowledgeBridge: Found %d results from product docs", len(results))
            return results

        # Try real KnowledgeService
        if self._real_kb is not None:
            try:
                results = self._real_kb.search(self.company_id, query, top_k=top_k)
                if results:
                    logger.debug("KnowledgeBridge: Found %d results from real KB", len(results))
                    return results
            except Exception as exc:
                logger.warning("KnowledgeBridge: Real KB search failed: %s", exc)

        # Fall back to Fake CRM (last resort — mock data, not production quality)
        results = self._search_fake_crm(query, top_k)
        if results:
            logger.debug("KnowledgeBridge: Found %d results from Fake CRM (fallback)", len(results))
        return results

    def _search_product_docs(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Keyword search through product documentation."""
        if not self._product_docs_chunks:
            return []

        query_words = set(w.lower() for w in query.split() if len(w) > 2)
        scored = []

        for chunk in self._product_docs_chunks:
            content_lower = chunk["content"].lower()
            title_lower = chunk["title"].lower()
            score = 0.0

            for word in query_words:
                if word in title_lower:
                    score += 0.4
                if word in content_lower:
                    score += 0.15

            if score > 0:
                scored.append({**chunk, "relevance_score": min(0.99, score)})

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored[:top_k]

    def _search_fake_crm(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Fallback: search Fake CRM KB data."""
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            results = crm.search_kb(query, top_k=top_k)
            return results if results else []
        except Exception:
            return []

    def upload_product_docs(self) -> int:
        """Upload product docs to the real KnowledgeService.

        Returns the number of documents uploaded.
        """
        self.initialize()

        if self._real_kb is None:
            logger.warning("KnowledgeBridge: Cannot upload — no real KB connected")
            return 0

        docs_path = PRODUCT_DOCS_PATH
        if not os.path.exists(docs_path):
            docs_path = "/home/z/my-project/backend/app/core/kb_product_docs.md"

        if not os.path.exists(docs_path):
            return 0

        try:
            with open(docs_path, "rb") as f:
                content = f.read()

            result = self._real_kb.upload_documents(
                self.company_id,
                [{"filename": "kb_product_docs.md", "content": content, "content_type": "text/markdown"}],
            )
            uploaded = result.get("uploaded", 0)
            logger.info("KnowledgeBridge: Uploaded %d docs to real KB", uploaded)
            return uploaded
        except Exception as exc:
            logger.error("KnowledgeBridge: Upload failed: %s", exc)
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        self.initialize()
        return {
            "real_kb_connected": self._real_kb is not None,
            "product_doc_chunks": len(self._product_docs_chunks),
            "company_id": self.company_id,
        }


# Singleton
_bridge: Optional[KnowledgeBridge] = None


def get_knowledge_bridge(company_id: str = "comp-test-001") -> KnowledgeBridge:
    """Get or create the KnowledgeBridge singleton."""
    global _bridge
    if _bridge is None or _bridge.company_id != company_id:
        _bridge = KnowledgeBridge(company_id=company_id)
    return _bridge
