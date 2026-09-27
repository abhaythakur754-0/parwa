"""
Escalation Vault — Saves pipeline state when ticket is escalated,
enabling human guidance via JARVIS and resume processing by PARWA.

Components:
  - vault_db: Dual-mode storage (InMemory + Supabase)
  - vault_manager: High-level CRUD operations
  - resume_pipeline: Resume logic with human guidance injection
"""
from app.core.escalation_vault.vault_manager import VaultManager
from app.core.escalation_vault.vault_db import get_vault_db, reset_vault_db

__all__ = ["VaultManager", "get_vault_db", "reset_vault_db"]
