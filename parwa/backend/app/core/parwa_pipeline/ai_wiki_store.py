"""
AI Wiki Store — Phase 6

3-section per-tenant design (in-memory for now, DB-ready schema).

  Section A: Ticket Patterns — PARWA writes on resolution, reads on Node 1/3/7
  Section B: Admin Behavior  — Jarvis writes (Phase 8), PARWA reads
  Section C: Company Knowledge — Admin writes (Phase 9), PARWA reads

Variant-based access control:
  mini  = read only (all sections)
  parwa = read + learn (Section A: read patterns, PARWA writes new patterns)
  high  = read + write + learn (all sections read/write)

All operations are non-LLM (keyword search, pattern matching).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("parwa.wiki")


# ── Access Control ─────────────────────────────────────────────────


# Section A: ticket patterns
# Section B: admin behavior
# Section C: company knowledge

VARIANT_ACCESS = {
    "mini": {
        "A": "read",
        "B": "read",
        "C": "read",
    },
    "parwa": {
        "A": "read+learn",   # can read + PARWA auto-writes patterns
        "B": "read",
        "C": "read",
    },
    "high": {
        "A": "read+write+learn",
        "B": "read+write+learn",
        "C": "read+write+learn",
    },
}


def _can_access(tier: str, section: str, operation: str) -> bool:
    """Check if a variant tier can perform an operation on a section.
    
    Operations: 'read', 'write', 'learn'
    """
    access = VARIANT_ACCESS.get(tier, VARIANT_ACCESS["mini"])
    permissions = access.get(section, "read")
    
    if operation == "read":
        return True  # all tiers can read
    if operation == "write":
        return "write" in permissions
    if operation == "learn":
        return "learn" in permissions
    return False


# ── Wiki Entry ─────────────────────────────────────────────────────


class WikiEntry:
    """A single AI Wiki entry."""
    
    __slots__ = (
        "id", "tenant_id", "section", "entry_key", "title",
        "content", "version", "tags", "created_by",
        "created_at", "updated_at", "usage_count", "success_count",
    )
    
    def __init__(
        self,
        tenant_id: str,
        section: str,
        entry_key: str,
        title: str,
        content: Dict[str, Any],
        created_by: str = "parwa",
        tags: Optional[List[str]] = None,
        version: int = 1,
    ):
        self.id = str(uuid.uuid4())
        self.tenant_id = tenant_id
        self.section = section  # "A", "B", or "C"
        self.entry_key = entry_key
        self.title = title
        self.content = content  # JSONB-like dict
        self.version = version
        self.tags = tags or []
        self.created_by = created_by  # "parwa", "jarvis", "admin"
        self.created_at = time.time()
        self.updated_at = time.time()
        self.usage_count = 0  # how many times this entry was read
        self.success_count = 0  # how many times it led to successful resolution
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "section": self.section,
            "entry_key": self.entry_key,
            "title": self.title,
            "content": self.content,
            "version": self.version,
            "tags": self.tags,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
        }
    
    def to_node_format(self) -> Dict[str, Any]:
        """Format for pipeline nodes (same shape as KB docs)."""
        content_str = self._content_to_str()
        return {
            "source": f"wiki_{self.section.lower()}_{self.entry_key}",
            "content": content_str,
            "section": self.section,
            "wiki_entry_id": self.id,
            "wiki_tags": self.tags,
        }
    
    def _content_to_str(self) -> str:
        """Convert content dict to readable string for pipeline consumption."""
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, dict):
            parts = []
            for k, v in self.content.items():
                if isinstance(v, list):
                    parts.append(f"{k}: " + ", ".join(str(i) for i in v))
                else:
                    parts.append(f"{k}: {v}")
            return ". ".join(parts)
        return str(self.content)


# ── AI Wiki Store ──────────────────────────────────────────────────


class AIWikiStore:
    """In-memory AI Wiki store with 3-section design.
    
    In production: this would be backed by PostgreSQL (see roadmap schema)
    with row-level security per tenant_id.
    
    For Phase 6: in-memory with tenant isolation guaranteed by
    always filtering on tenant_id.
    """
    
    def __init__(self):
        # {tenant_id: {section: {entry_key: WikiEntry}}}
        self._store: Dict[str, Dict[str, Dict[str, WikiEntry]]] = {}
        # Track policy versions for sync check
        self._policy_versions: Dict[str, str] = {}  # {tenant_id: version_str}
    
    # ── Core CRUD ──────────────────────────────────────────────────
    
    def _ensure_tenant(self, tenant_id: str) -> Dict[str, Dict[str, WikiEntry]]:
        """Ensure tenant has all 3 sections initialized."""
        if tenant_id not in self._store:
            self._store[tenant_id] = {
                "A": {},  # Ticket Patterns
                "B": {},  # Admin Behavior
                "C": {},  # Company Knowledge
            }
        return self._store[tenant_id]
    
    def write(
        self,
        tenant_id: str,
        section: str,
        entry_key: str,
        title: str,
        content: Dict[str, Any],
        created_by: str = "parwa",
        tags: Optional[List[str]] = None,
        tier: str = "parwa",
    ) -> Optional[WikiEntry]:
        """Write (create or update) a wiki entry.
        
        Returns the entry if write was allowed, None if access denied.
        """
        if not _can_access(tier, section, "write") and not _can_access(tier, section, "learn"):
            logger.debug("Write denied for tier=%s section=%s", tier, section)
            return None
        
        tenant = self._ensure_tenant(tenant_id)
        
        # Check if entry exists (update vs create)
        if entry_key in tenant[section]:
            entry = tenant[section][entry_key]
            entry.content = content
            entry.version += 1
            entry.updated_at = time.time()
            entry.tags = tags or entry.tags
            logger.info(
                "Wiki UPDATE: tenant=%s section=%s key=%s v=%d",
                tenant_id, section, entry_key, entry.version,
            )
        else:
            entry = WikiEntry(
                tenant_id=tenant_id,
                section=section,
                entry_key=entry_key,
                title=title,
                content=content,
                created_by=created_by,
                tags=tags,
            )
            tenant[section][entry_key] = entry
            logger.info(
                "Wiki CREATE: tenant=%s section=%s key=%s",
                tenant_id, section, entry_key,
            )
        
        return entry
    
    def read(
        self,
        tenant_id: str,
        section: str,
        entry_key: Optional[str] = None,
        tier: str = "parwa",
    ) -> List[WikiEntry]:
        """Read wiki entries for a tenant/section.
        
        If entry_key provided: return that specific entry.
        Otherwise: return all entries in the section.
        """
        if not _can_access(tier, section, "read"):
            return []
        
        tenant = self._ensure_tenant(tenant_id)
        
        if entry_key:
            entry = tenant[section].get(entry_key)
            if entry:
                entry.usage_count += 1
                return [entry]
            return []
        
        # Return all entries in section, sorted by usage (most used first)
        entries = list(tenant[section].values())
        for e in entries:
            e.usage_count += 1
        entries.sort(key=lambda e: e.success_count / max(e.usage_count, 1), reverse=True)
        return entries
    
    def search(
        self,
        tenant_id: str,
        section: str,
        query: str,
        ticket_type: Optional[str] = None,
        tier: str = "parwa",
        max_results: int = 5,
    ) -> List[WikiEntry]:
        """Search wiki entries by keyword relevance (non-LLM).
        
        Scores entries by:
        1. Tag exact match with ticket_type
        2. Keyword overlap between query and entry content/title/tags
        3. Historical success rate (entries that helped before rank higher)
        
        Returns top-N entries as WikiEntry objects.
        """
        if not _can_access(tier, section, "read"):
            return []
        
        tenant = self._ensure_tenant(tenant_id)
        entries = list(tenant[section].values())
        
        if not entries:
            return []
        
        query_lower = query.lower()
        query_terms = set(w for w in query_lower.split() if len(w) > 3)
        # Add ticket type terms
        if ticket_type:
            type_terms = set(ticket_type.replace("_", " ").split())
            query_terms |= type_terms
        
        # Remove filler
        filler = {"that", "this", "have", "been", "will", "would", "could",
                  "should", "their", "there", "about", "which", "where",
                  "when", "what", "with", "from", "your", "just", "also"}
        query_terms -= filler
        
        scored = []
        for entry in entries:
            # Score 1: Tag match with ticket_type (strong signal)
            tag_score = 0.0
            if ticket_type and ticket_type in entry.tags:
                tag_score = 0.3
            
            # Score 2: Keyword overlap
            entry_text = (entry.title + " " + entry._content_to_str() + " " + " ".join(entry.tags)).lower()
            entry_words = set(entry_text.split())
            if query_terms and entry_words:
                overlap = len(query_terms & entry_words) / len(query_terms)
            else:
                overlap = 0.0
            
            # Score 3: Historical success rate (mild boost)
            success_rate = entry.success_count / max(entry.usage_count, 1)
            history_boost = success_rate * 0.1
            
            total_score = tag_score + (overlap * 0.6) + history_boost
            scored.append((total_score, entry))
        
        # Sort by score, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        
        results = [e for _, e in scored[:max_results]]
        
        # Mark usage
        for e in results:
            e.usage_count += 1
        
        if results:
            logger.debug(
                "Wiki SEARCH: tenant=%s section=%s query='%s' → %d results",
                tenant_id, section, query[:50], len(results),
            )
        
        return results
    
    def record_success(self, tenant_id: str, section: str, entry_key: str) -> None:
        """Record that a wiki entry contributed to a successful resolution.
        
        This is the learning signal — entries that help get boosted in future searches.
        """
        tenant = self._ensure_tenant(tenant_id)
        entry = tenant[section].get(entry_key)
        if entry:
            entry.success_count += 1
            logger.debug(
                "Wiki SUCCESS: key=%s total_successes=%d",
                entry_key, entry.success_count,
            )
    
    # ── Section A: Ticket Pattern Operations ───────────────────────
    
    def write_ticket_pattern(
        self,
        tenant_id: str,
        ticket_type: str,
        query: str,
        complexity: str,
        techniques_used: List[str],
        quality_score: float,
        answer_summary: str,
        tier: str = "parwa",
    ) -> Optional[WikiEntry]:
        """Write a ticket resolution pattern to Section A.
        
        Called after a ticket is successfully resolved.
        Stores: what the question was, what techniques worked, quality achieved.
        """
        # Generate a stable key from ticket_type + key query terms
        key_terms = " ".join(w for w in query.lower().split() if len(w) > 4)[:60]
        entry_key = f"{ticket_type}_{hashlib.md5(key_terms.encode()).hexdigest()[:8]}"
        
        content = {
            "query_pattern": query[:300],
            "ticket_type": ticket_type,
            "complexity": complexity,
            "techniques_that_worked": techniques_used[:10],
            "quality_achieved": round(quality_score, 4),
            "answer_summary": answer_summary[:500],
            "key_terms": list(set(w.lower() for w in query.split() if len(w) > 4))[:15],
        }
        
        tags = [ticket_type, complexity, f"quality_{quality_score:.2f}"]
        
        return self.write(
            tenant_id=tenant_id,
            section="A",
            entry_key=entry_key,
            title=f"Pattern: {ticket_type} ({complexity})",
            content=content,
            created_by="parwa",
            tags=tags,
            tier=tier,
        )
    
    def find_similar_patterns(
        self,
        tenant_id: str,
        query: str,
        ticket_type: str,
        tier: str = "parwa",
        max_results: int = 3,
    ) -> List[Dict[str, Any]]:
        """Find similar previously-resolved ticket patterns from Section A.
        
        Returns list of pattern dicts with relevance info.
        Used by: Node 1 (classification), Node 3 (knowledge), Node 8 (reflexion).
        """
        entries = self.search(
            tenant_id=tenant_id,
            section="A",
            query=query,
            ticket_type=ticket_type,
            tier=tier,
            max_results=max_results,
        )
        
        patterns = []
        for entry in entries:
            c = entry.content
            patterns.append({
                "entry_key": entry.entry_key,
                "query_pattern": c.get("query_pattern", ""),
                "ticket_type": c.get("ticket_type", ""),
                "complexity": c.get("complexity", ""),
                "techniques_that_worked": c.get("techniques_that_worked", []),
                "quality_achieved": c.get("quality_achieved", 0),
                "answer_summary": c.get("answer_summary", ""),
                "key_terms": c.get("key_terms", []),
                "historical_success_rate": entry.success_count / max(entry.usage_count, 1),
                "usage_count": entry.usage_count,
                "success_count": entry.success_count,
                "wiki_entry_id": entry.id,
            })
        
        return patterns
    
    # ── Section C: Policy Version Tracking ─────────────────────────
    
    def check_policy_sync(
        self,
        tenant_id: str,
        current_policy_version: str,
    ) -> Dict[str, Any]:
        """Check if the knowledge base policy version matches the wiki version.
        
        If versions differ, it means policies changed and cached wiki patterns
        may be stale. Returns a sync status dict.
        
        Used by: Node 3 (before knowledge fetch).
        """
        stored_version = self._policy_versions.get(tenant_id, "")
        
        if not stored_version:
            # First time — record the version
            self._policy_versions[tenant_id] = current_policy_version
            return {"synced": True, "version": current_policy_version, "previous_version": None}
        
        if stored_version == current_policy_version:
            return {"synced": True, "version": current_policy_version, "previous_version": stored_version}
        
        # Policy changed!
        old_version = stored_version
        self._policy_versions[tenant_id] = current_policy_version
        
        # Invalidate Section A patterns that may be stale
        invalidated = self._invalidate_stale_patterns(tenant_id, old_version, current_policy_version)
        
        logger.info(
            "Wiki POLICY SYNC: tenant=%s version %s → %s (%d patterns invalidated)",
            tenant_id, old_version, current_policy_version, invalidated,
        )
        
        return {
            "synced": False,
            "version": current_policy_version,
            "previous_version": old_version,
            "patterns_invalidated": invalidated,
        }
    
    def _invalidate_stale_patterns(
        self, tenant_id: str, old_version: str, new_version: str
    ) -> int:
        """Mark stale Section A patterns when policy changes.
        
        Instead of deleting, we reset their success counts so they
        rank lower in future searches until proven again.
        """
        tenant = self._ensure_tenant(tenant_id)
        invalidated = 0
        for entry in tenant["A"].values():
            # Reset success tracking — pattern needs re-validation
            entry.success_count = 0
            entry.version += 1
            entry.tags = [t for t in entry.tags if not t.startswith("quality_")]
            invalidated += 1
        return invalidated
    
    # ── Statistics ─────────────────────────────────────────────────
    
    def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get wiki statistics for a tenant."""
        tenant = self._ensure_tenant(tenant_id)
        stats = {
            "section_a_entries": len(tenant["A"]),
            "section_b_entries": len(tenant["B"]),
            "section_c_entries": len(tenant["C"]),
            "total_entries": sum(len(s) for s in tenant.values()),
            "top_patterns": [],
        }
        
        # Top 5 most successful Section A patterns
        patterns = sorted(
            tenant["A"].values(),
            key=lambda e: e.success_count / max(e.usage_count, 1),
            reverse=True,
        )[:5]
        for p in patterns:
            stats["top_patterns"].append({
                "entry_key": p.entry_key,
                "title": p.title,
                "success_rate": round(p.success_count / max(p.usage_count, 1), 3),
                "usage_count": p.usage_count,
            })
        
        return stats
    
    def clear_tenant(self, tenant_id: str) -> None:
        """Clear all wiki data for a tenant (for testing)."""
        if tenant_id in self._store:
            del self._store[tenant_id]
        if tenant_id in self._policy_versions:
            del self._policy_versions[tenant_id]


# ── Global Singleton ───────────────────────────────────────────────


_wiki_store: Optional[AIWikiStore] = None


def get_wiki_store() -> AIWikiStore:
    """Get the global AI Wiki store singleton."""
    global _wiki_store
    if _wiki_store is None:
        _wiki_store = AIWikiStore()
    return _wiki_store