"""
PARWA Channels API - Channel Configuration Endpoints (Day 30)

Implements F-052: Omnichannel configuration API.
"""

from __future__ import annotations

from typing import Any, Dict

from app.api.deps import get_current_user, get_db, require_roles
from app.exceptions import NotFoundError, ValidationError
from app.services.channel_service import ChannelService
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/channels",
    tags=["channels"],
    dependencies=[Depends(require_roles("owner", "admin"))],
)


@router.get(
    "",
    summary="List available channels",
)
async def list_channels(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """List all available system channels."""
    company_id = current_user.get("company_id")

    service = ChannelService(db, company_id)

    return service.get_available_channels()


@router.get(
    "/config",
    summary="Get company channel configuration",
)
async def get_channel_config(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Get company's channel configuration."""
    company_id = current_user.get("company_id")

    service = ChannelService(db, company_id)

    return service.get_company_channel_config()


@router.put(
    "/config/{channel_type}",
    summary="Update channel configuration",
)
async def update_channel_config(
    channel_type: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Update configuration for a specific channel."""
    company_id = current_user.get("company_id")

    body = await request.json()

    service = ChannelService(db, company_id)

    try:
        config = service.update_channel_config(
            channel_type=channel_type,
            is_enabled=body.get("is_enabled"),
            config_json=body.get("config"),
            auto_create_ticket=body.get("auto_create_ticket"),
            char_limit=body.get("char_limit"),
            allowed_file_types=body.get("allowed_file_types"),
            max_file_size=body.get("max_file_size"),
        )

        return {
            "channel_type": config.channel_type,
            "is_enabled": config.is_enabled,
            "config": body.get("config", {}),
            "auto_create_ticket": config.auto_create_ticket,
            "char_limit": config.char_limit,
            "allowed_file_types": body.get("allowed_file_types", []),
            "max_file_size": config.max_file_size,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/config/{channel_type}/test",
    summary="Test channel connectivity",
)
async def test_channel(
    channel_type: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Test connectivity for a channel configuration."""
    company_id = current_user.get("company_id")

    body = await request.json() if await request.body() else {}
    test_config = body.get("test_config")

    service = ChannelService(db, company_id)

    return service.test_channel_connectivity(channel_type, test_config)


@router.post(
    "/format-message",
    summary="Format message for channel",
)
async def format_message(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Format a message for a specific channel."""
    company_id = current_user.get("company_id")

    body = await request.json()
    content = body.get("content", "")
    channel_type = body.get("channel_type", "email")
    truncate = body.get("truncate", True)

    service = ChannelService(db, company_id)

    formatted = service.format_message_for_channel(
        content=content,
        channel_type=channel_type,
        truncate=truncate,
    )

    return {
        "original_length": len(content),
        "formatted_length": len(formatted),
        "channel_type": channel_type,
        "content": formatted,
    }


@router.post(
    "/validate-file",
    summary="Validate file for channel",
)
async def validate_file(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """Validate a file for a specific channel."""
    company_id = current_user.get("company_id")

    body = await request.json()
    filename = body.get("filename", "")
    file_size = body.get("file_size", 0)
    channel_type = body.get("channel_type", "email")

    service = ChannelService(db, company_id)

    is_valid, error = service.validate_file_for_channel(
        filename=filename,
        file_size=file_size,
        channel_type=channel_type,
    )

    return {
        "is_valid": is_valid,
        "error": error,
        "filename": filename,
        "channel_type": channel_type,
    }


@router.get(
    "/variant-retry",
    summary="Check variant retry tickets",
)
async def check_variant_retry(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """PS13: Check for tickets needing variant retry or human fallback."""
    company_id = current_user.get("company_id")

    service = ChannelService(db, company_id)

    return service.check_variant_retry_tickets()


@router.post(
    "/variant-retry/{ticket_id}",
    summary="Process variant retry",
)
async def process_variant_retry(
    ticket_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """PS13: Process a variant retry attempt."""
    company_id = current_user.get("company_id")

    body = await request.json()
    success = body.get("success", False)

    service = ChannelService(db, company_id)

    try:
        return service.process_variant_retry(ticket_id, success)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/escalate/{ticket_id}",
    summary="Escalate to human",
)
async def escalate_to_human(
    ticket_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
) -> Any:
    """PS13: Escalate queued ticket to human agent."""
    company_id = current_user.get("company_id")

    body = await request.json() if await request.body() else {}
    reason = body.get("reason", "variant_unavailable")

    service = ChannelService(db, company_id)

    try:
        return service.escalate_to_human(ticket_id, reason)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
