"""
PARWA Knowledge Update Tool.

Tool for updating the knowledge base with new information,
including FAQ entries, documentation, and learned responses.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class KnowledgeUpdateTool:
    """
    Tool for updating the knowledge base.

    Provides functionality to add, update, and remove knowledge
    entries for PARWA's learning capabilities.

    Features:
    - Add new FAQ entries
    - Update existing entries
    - Remove outdated information
    - Track update history
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None
    ) -> None:
        """
        Initialize Knowledge Update Tool.

        Args:
            company_id: Company UUID for data isolation
        """
        self._company_id = company_id
        self._knowledge_entries: Dict[str, Dict[str, Any]] = {}
        self._update_history: List[Dict[str, Any]] = []

    async def add_entry(
        self,
        question: str,
        answer: str,
        category: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new knowledge entry.

        Args:
            question: The question or topic
            answer: The answer or content
            category: Category for organization
            metadata: Additional metadata

        Returns:
            Dict with entry_id and status
        """
        from uuid import uuid4

        entry_id = f"kb_{uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        entry = {
            "entry_id": entry_id,
            "question": question,
            "answer": answer,
            "category": category,
            "metadata": metadata or {},
            "created_at": created_at,
            "updated_at": created_at,
            "company_id": str(self._company_id) if self._company_id else None,
        }

        self._knowledge_entries[entry_id] = entry

        # Track update
        self._track_update("add", entry_id, {"category": category})

        logger.info({
            "event": "knowledge_entry_added",
            "entry_id": entry_id,
            "category": category,
            "company_id": str(self._company_id) if self._company_id else None,
        })

        return {
            "entry_id": entry_id,
            "status": "added",
            "category": category,
        }

    async def update_entry(
        self,
        entry_id: str,
        question: Optional[str] = None,
        answer: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing knowledge entry.

        Args:
            entry_id: ID of entry to update
            question: New question (optional)
            answer: New answer (optional)
            metadata: Metadata to merge (optional)

        Returns:
            Dict with status and updated entry
        """
        if entry_id not in self._knowledge_entries:
            return {
                "status": "error",
                "message": f"Entry not found: {entry_id}",
            }

        entry = self._knowledge_entries[entry_id]
        updated_at = datetime.now(timezone.utc).isoformat()

        if question:
            entry["question"] = question
        if answer:
            entry["answer"] = answer
        if metadata:
            entry["metadata"] = {**entry.get("metadata", {}), **metadata}

        entry["updated_at"] = updated_at

        # Track update
        self._track_update("update", entry_id, {})

        logger.info({
            "event": "knowledge_entry_updated",
            "entry_id": entry_id,
        })

        return {
            "entry_id": entry_id,
            "status": "updated",
            "updated_at": updated_at,
        }

    async def remove_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Remove a knowledge entry.

        Args:
            entry_id: ID of entry to remove

        Returns:
            Dict with status
        """
        if entry_id not in self._knowledge_entries:
            return {
                "status": "error",
                "message": f"Entry not found: {entry_id}",
            }

        del self._knowledge_entries[entry_id]

        # Track update
        self._track_update("remove", entry_id, {})

        logger.info({
            "event": "knowledge_entry_removed",
            "entry_id": entry_id,
        })

        return {
            "entry_id": entry_id,
            "status": "removed",
        }

    async def search_entries(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge entries.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of matching entries
        """
        query_lower = query.lower()
        results: List[Dict[str, Any]] = []

        for entry in self._knowledge_entries.values():
            # Category filter
            if category and entry.get("category") != category:
                continue

            # Search in question and answer
            question_match = query_lower in entry.get("question", "").lower()
            answer_match = query_lower in entry.get("answer", "").lower()

            if question_match or answer_match:
                results.append(entry)

        return results[:limit]

    async def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific knowledge entry.

        Args:
            entry_id: Entry ID

        Returns:
            Entry dict or None
        """
        return self._knowledge_entries.get(entry_id)

    def get_categories(self) -> List[str]:
        """Get all categories."""
        categories = set()
        for entry in self._knowledge_entries.values():
            if "category" in entry:
                categories.add(entry["category"])
        return sorted(list(categories))

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        categories: Dict[str, int] = {}
        for entry in self._knowledge_entries.values():
            cat = entry.get("category", "uncategorized")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_entries": len(self._knowledge_entries),
            "categories": categories,
            "update_count": len(self._update_history),
        }

    def _track_update(
        self,
        action: str,
        entry_id: str,
        details: Dict[str, Any]
    ) -> None:
        """Track an update for history."""
        self._update_history.append({
            "action": action,
            "entry_id": entry_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def execute(
        self,
        action: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Execute a knowledge update action.

        Args:
            action: Action to perform (add, update, remove, search, get)
            **kwargs: Action-specific arguments

        Returns:
            Result dict
        """
        if action == "add":
            return await self.add_entry(
                question=kwargs.get("question", ""),
                answer=kwargs.get("answer", ""),
                category=kwargs.get("category", "general"),
                metadata=kwargs.get("metadata"),
            )
        elif action == "update":
            return await self.update_entry(
                entry_id=kwargs.get("entry_id", ""),
                question=kwargs.get("question"),
                answer=kwargs.get("answer"),
                metadata=kwargs.get("metadata"),
            )
        elif action == "remove":
            return await self.remove_entry(kwargs.get("entry_id", ""))
        elif action == "search":
            results = await self.search_entries(
                query=kwargs.get("query", ""),
                category=kwargs.get("category"),
                limit=kwargs.get("limit", 10),
            )
            return {"results": results, "count": len(results)}
        elif action == "get":
            entry = await self.get_entry(kwargs.get("entry_id", ""))
            return {"entry": entry} if entry else {"error": "Entry not found"}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
