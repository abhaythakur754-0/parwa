"""PARWA Permissions — Action permission enforcement per variant.

This module enforces the variant-specific action permission matrix
defined in config.py. The PermissionExecutor is wired into action_executor
to determine whether each action should be EXECUTED, RECOMMENDED, or DENIED
based on the customer's variant tier.

Think vs Act split (from CLAUDE.md):
  - All variants THINK identically (same 22 nodes, same frameworks)
  - ACTING is permission-gated:
    - Mini PARWA: Execute basics, Recommend restricted, Deny premium
    - PARWA: Execute all standard, Deny bulk/analytics
    - PARWA High: Execute everything including bulk + analytics
"""

from parwa.permissions.executor import PermissionExecutor

__all__ = ["PermissionExecutor"]
