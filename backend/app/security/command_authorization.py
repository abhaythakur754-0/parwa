"""Authorization rules for side-effecting Jarvis Customer Care commands."""

from app.exceptions import AuthorizationError


ADMIN_ONLY_COMMAND_ACTIONS = frozenset(
    {
        "pause_ai",
        "resume_ai",
        "pause_refunds",
        "resume_refunds",
        "add_agents",
        "disable_last_rule",
    }
)


def require_command_role(action: str, user_role: str | None) -> None:
    """Require owner/admin for high-impact command actions.

    system is reserved for trusted internal orchestration/task callers.
    Public API entry points must pass the authenticated user's actual role.
    """
    role = (user_role or "").strip().lower()
    if action in ADMIN_ONLY_COMMAND_ACTIONS and role not in {
        "owner",
        "admin",
        "system",
    }:
        raise AuthorizationError(
            message="Only company owners or administrators can execute this command",
            details={
                "action": action,
                "required_roles": ["owner", "admin"],
            },
        )
