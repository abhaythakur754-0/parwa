"""
PARWA MFA Schemas (F-015, F-016, F-017)

Pydantic models for MFA setup, verification, backup codes,
and session management.
"""

import re

from pydantic import BaseModel, Field, field_validator

# ── F-015: MFA Setup ──────────────────────────────────────────────

TOTP_CODE_REGEX = re.compile(r"^\d{6}$")


class MFASetupInitiateRequest(BaseModel):
    """Request to initiate MFA setup (empty body)."""


class MFASetupVerifyRequest(BaseModel):
    """Request to verify MFA setup with TOTP code."""

    code: str = Field(min_length=6, max_length=6)
    temp_secret: str = Field(min_length=1, max_length=255)

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not TOTP_CODE_REGEX.match(v):
            raise ValueError("MFA code must be exactly 6 digits")
        return v


class MFALoginVerifyRequest(BaseModel):
    """Request to verify MFA during login."""

    code: str = Field(min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not TOTP_CODE_REGEX.match(v):
            raise ValueError("MFA code must be exactly 6 digits")
        return v


class MFASetupResponse(BaseModel):
    """Response with QR code and backup codes."""

    qr_code_data_url: str
    secret_key: str
    backup_codes: list[str]
    message: str = "Scan QR code with your authenticator app"


class MFAVerifyResponse(BaseModel):
    """Response after MFA verification."""

    status: str = "enabled"
    mfa_enabled: bool = True
    message: str = "MFA enabled successfully"


# ── F-016: Backup Codes ────────────────────────────────────────────


class BackupCodeUseRequest(BaseModel):
    """Request to use a backup code during login."""

    code: str = Field(min_length=1, max_length=32)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class BackupCodeRegenerateRequest(BaseModel):
    """Request to regenerate backup codes (requires TOTP)."""

    mfa_code: str = Field(min_length=6, max_length=6)

    @field_validator("mfa_code")
    @classmethod
    def code_must_be_digits(cls, v: str) -> str:
        if not TOTP_CODE_REGEX.match(v):
            raise ValueError("MFA code must be exactly 6 digits")
        return v


class BackupCodesResponse(BaseModel):
    """Response with regenerated backup codes."""

    backup_codes: list[str]
    message: str = "New backup codes generated. Store them securely."


class BackupCodeVerifyResponse(BaseModel):
    """Response after using a backup code."""

    status: str = "verified"
    remaining: int = 0
    message: str = "Backup code accepted"


# ── F-017: Session Management ─────────────────────────────────────


class SessionResponse(BaseModel):
    """A single session."""

    id: str
    device_info: str = ""
    ip_address: str = ""
    last_active: str = ""
    is_current: bool = False


class SessionListResponse(BaseModel):
    """List of active sessions."""

    sessions: list[SessionResponse]


class SessionRevokeResponse(BaseModel):
    """Response after revoking a session."""

    status: str = "revoked"
    message: str = "Session revoked successfully"


class RevokeOthersResponse(BaseModel):
    """Response after revoking all other sessions."""

    status: str = "all_other_sessions_revoked"
    count: int = 0
    message: str = "All other sessions revoked"
