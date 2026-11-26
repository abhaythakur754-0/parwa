"""Tenant-controlled privacy policy for outbound voice recordings."""

def resolve_recording_enabled(
    tenant_recording_enabled: bool,
    requested_recording_enabled: bool | None,
) -> bool:
    """Allow a per-call opt-out, never a client override of tenant consent policy."""
    if requested_recording_enabled is not None and not isinstance(
        requested_recording_enabled, bool
    ):
        raise ValueError("requested_recording_enabled must be a boolean or None")

    return bool(tenant_recording_enabled) and requested_recording_enabled is not False
