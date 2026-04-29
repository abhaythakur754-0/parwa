"""
Notification Preference Service - User preferences (MF05)

Handles:
- Per-user notification preferences
- Event-type preferences
- Channel preferences
- Digest settings
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.core import User
from database.models.remaining import NotificationPreference


class NotificationPreferenceService:
    """
    Service for managing user notification preferences.

    Features:
    - Per-event preferences
    - Channel selection
    - Digest mode settings
    - Bulk preference updates
    """

    # All event types with default settings
    DEFAULT_PREFERENCES = {
        "ticket_created": {
            "enabled": True,
            "channels": ["in_app"],
            "priority_threshold": "medium",
        },
        "ticket_updated": {
            "enabled": True,
            "channels": ["in_app"],
            "priority_threshold": "low",
        },
        "ticket_assigned": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "low",
        },
        "ticket_resolved": {
            "enabled": True,
            "channels": ["email"],
            "priority_threshold": "low",
        },
        "ticket_closed": {
            "enabled": True,
            "channels": ["email"],
            "priority_threshold": "low",
        },
        "ticket_reopened": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "medium",
        },
        "sla_warning": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "medium",
        },
        "sla_breached": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "low",
        },
        "ticket_escalated": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "low",
        },
        "mention": {
            "enabled": True,
            "channels": ["in_app"],
            "priority_threshold": "low",
        },
        "bulk_action_completed": {
            "enabled": True,
            "channels": ["in_app"],
            "priority_threshold": "low",
        },
        "incident_created": {
            "enabled": True,
            "channels": ["email", "in_app"],
            "priority_threshold": "medium",
        },
        "incident_resolved": {
            "enabled": True,
            "channels": ["email"],
            "priority_threshold": "low",
        },
    }

    # Valid channels
    VALID_CHANNELS = ["email", "in_app", "push"]

    # Valid digest frequencies
    VALID_DIGEST_FREQUENCIES = ["none", "daily", "weekly"]

    # Valid priority thresholds
    VALID_PRIORITY_THRESHOLDS = ["low", "medium", "high", "urgent"]

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    def get_user_preferences(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get all notification preferences for a user.

        Returns preferences for all event types, using defaults for unset ones.
        """
        # Verify user exists
        user = self.db.query(User).filter(
            User.id == user_id,
            User.company_id == self.company_id,
        ).first()

        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Get stored preferences
        stored_prefs = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == user_id,
        ).all()

        # Build preferences dict
        preferences = {}

        for event_type, defaults in self.DEFAULT_PREFERENCES.items():
            stored = next(
                (p for p in stored_prefs if p.event_type == event_type),
                None
            )

            if stored:
                preferences[event_type] = {
                    "enabled": stored.enabled,
                    "channels": json.loads(
                        stored.channels) if stored.channels else defaults["channels"],
                    "priority_threshold": stored.priority_threshold or defaults["priority_threshold"],
                }
            else:
                preferences[event_type] = defaults.copy()

        # Get digest settings
        digest_settings = self._get_digest_settings(user_id)

        return {
            "user_id": user_id,
            "preferences": preferences,
            "digest_frequency": digest_settings.get("frequency", "none"),
            "digest_time": digest_settings.get("time", "09:00"),
        }

    def update_preference(
        self,
        user_id: str,
        event_type: str,
        enabled: Optional[bool] = None,
        channels: Optional[List[str]] = None,
        priority_threshold: Optional[str] = None,
    ) -> NotificationPreference:
        """
        Update preference for a specific event type.

        Args:
            user_id: User ID
            event_type: Event type to update
            enabled: Whether notifications are enabled
            channels: List of channels to use
            priority_threshold: Minimum priority to notify

        Returns:
            Updated NotificationPreference
        """
        # Validate event type
        if event_type not in self.DEFAULT_PREFERENCES:
            raise ValidationError(f"Invalid event type: {event_type}")

        # Validate channels
        if channels is not None:
            invalid = set(channels) - set(self.VALID_CHANNELS)
            if invalid:
                raise ValidationError(f"Invalid channels: {invalid}")

        # Validate priority threshold
        if priority_threshold is not None:
            if priority_threshold not in self.VALID_PRIORITY_THRESHOLDS:
                raise ValidationError(
                    f"Invalid priority threshold. Valid: {
                        self.VALID_PRIORITY_THRESHOLDS}")

        # Get or create preference
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        ).first()

        if not preference:
            defaults = self.DEFAULT_PREFERENCES[event_type]
            preference = NotificationPreference(
                id=str(
                    uuid4()),
                company_id=self.company_id,
                user_id=user_id,
                event_type=event_type,
                enabled=enabled if enabled is not None else defaults["enabled"],
                channels=json.dumps(
                    channels or defaults["channels"]),
                priority_threshold=priority_threshold or defaults["priority_threshold"],
                created_at=datetime.now(
                    timezone.utc),
            )
            self.db.add(preference)
        else:
            if enabled is not None:
                preference.enabled = enabled
            if channels is not None:
                preference.channels = json.dumps(channels)
            if priority_threshold is not None:
                preference.priority_threshold = priority_threshold

        preference.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(preference)

        return preference

    def update_preferences_bulk(
        self,
        user_id: str,
        preferences: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update multiple preferences at once.

        Args:
            user_id: User ID
            preferences: Dict of event_type -> {enabled, channels, priority_threshold}

        Returns:
            Dict with update results
        """
        results = {
            "updated": [],
            "errors": [],
        }

        for event_type, settings in preferences.items():
            try:
                self.update_preference(
                    user_id=user_id,
                    event_type=event_type,
                    enabled=settings.get("enabled"),
                    channels=settings.get("channels"),
                    priority_threshold=settings.get("priority_threshold"),
                )
                results["updated"].append(event_type)
            except Exception as e:
                results["errors"].append({
                    "event_type": event_type,
                    "error": str(e),
                })

        return results

    def set_digest_settings(
        self,
        user_id: str,
        frequency: str,
        digest_time: str = "09:00",
    ) -> Dict[str, Any]:
        """
        Set digest mode settings.

        Args:
            user_id: User ID
            frequency: 'none', 'daily', or 'weekly'
            digest_time: Time for digest (HH:MM format)

        Returns:
            Updated settings
        """
        if frequency not in self.VALID_DIGEST_FREQUENCIES:
            raise ValidationError(
                f"Invalid frequency. Valid: {self.VALID_DIGEST_FREQUENCIES}"
            )

        # Validate time format
        try:
            hour, minute = map(int, digest_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValidationError(
                "Invalid time format. Use HH:MM (24-hour format)")

        # Store in user metadata (or a dedicated table)
        user = self.db.query(User).filter(
            User.id == user_id,
            User.company_id == self.company_id,
        ).first()

        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Store digest settings in user's metadata_json
        metadata = json.loads(user.metadata_json or "{}")
        metadata["digest_settings"] = {
            "frequency": frequency,
            "time": digest_time,
        }
        user.metadata_json = json.dumps(metadata)

        self.db.commit()

        return {
            "user_id": user_id,
            "digest_frequency": frequency,
            "digest_time": digest_time,
        }

    def disable_all_notifications(
        self,
        user_id: str,
    ) -> int:
        """
        Disable all notifications for a user.

        Returns count of preferences updated.
        """
        count = 0

        for event_type in self.DEFAULT_PREFERENCES.keys():
            try:
                self.update_preference(
                    user_id=user_id,
                    event_type=event_type,
                    enabled=False,
                )
                count += 1
            except Exception:
                pass

        return count

    def enable_all_notifications(
        self,
        user_id: str,
    ) -> int:
        """
        Enable all notifications for a user with default settings.

        Returns count of preferences updated.
        """
        count = 0

        for event_type, defaults in self.DEFAULT_PREFERENCES.items():
            try:
                self.update_preference(
                    user_id=user_id,
                    event_type=event_type,
                    enabled=defaults["enabled"],
                    channels=defaults["channels"],
                    priority_threshold=defaults["priority_threshold"],
                )
                count += 1
            except Exception:
                pass

        return count

    def should_notify(
        self,
        user_id: str,
        event_type: str,
        priority: str = "medium",
    ) -> Tuple[bool, List[str]]:
        """
        Check if a user should be notified for an event.

        Args:
            user_id: User ID
            event_type: Event type
            priority: Event priority

        Returns:
            Tuple of (should_notify, channels)
        """
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        ).first()

        if not preference:
            # Use defaults
            defaults = self.DEFAULT_PREFERENCES.get(event_type, {})
            enabled = defaults.get("enabled", True)
            channels = defaults.get("channels", ["in_app"])
            threshold = defaults.get("priority_threshold", "low")
        else:
            enabled = preference.enabled
            channels = json.loads(
                preference.channels) if preference.channels else []
            threshold = preference.priority_threshold or "low"

        if not enabled:
            return False, []

        # Check priority threshold
        priority_levels = {"low": 0, "medium": 1, "high": 2, "urgent": 3}
        if priority_levels.get(
                priority,
                0) < priority_levels.get(
                threshold,
                0):
            return False, []

        return True, channels

    def get_users_for_event(
        self,
        event_type: str,
        channel: str = "email",
    ) -> List[str]:
        """
        Get list of user IDs who want notifications for an event type.

        Used for batch notification processing.
        """
        preferences = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.event_type == event_type,
            NotificationPreference.enabled,
        ).all()

        user_ids = []
        for pref in preferences:
            channels = json.loads(pref.channels) if pref.channels else []
            if channel in channels:
                user_ids.append(pref.user_id)

        return user_ids

    def reset_to_defaults(
        self,
        user_id: str,
    ) -> int:
        """
        Reset user preferences to defaults.

        Returns count of preferences reset.
        """
        # Delete all existing preferences
        self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == user_id,
        ).delete()

        self.db.commit()

        return len(self.DEFAULT_PREFERENCES)

    def _get_digest_settings(self, user_id: str) -> Dict[str, Any]:
        """Get digest settings from user metadata."""
        user = self.db.query(User).filter(
            User.id == user_id,
            User.company_id == self.company_id,
        ).first()

        if not user or not user.metadata_json:
            return {"frequency": "none", "time": "09:00"}

        try:
            metadata = json.loads(user.metadata_json)
            return metadata.get(
                "digest_settings", {
                    "frequency": "none", "time": "09:00"})
        except (json.JSONDecodeError, TypeError):
            return {"frequency": "none", "time": "09:00"}

    def get_preference_history(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get history of preference changes for a user.

        This would typically be implemented with an audit log table.
        For now, returns empty list.
        """
        # TODO: Implement with audit log
        return []

    def copy_preferences(
        self,
        from_user_id: str,
        to_user_id: str,
    ) -> int:
        """
        Copy preferences from one user to another.

        Returns count of preferences copied.
        """
        source_prefs = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == from_user_id,
        ).all()

        count = 0
        for pref in source_prefs:
            try:
                self.update_preference(
                    user_id=to_user_id,
                    event_type=pref.event_type,
                    enabled=pref.enabled,
                    channels=json.loads(
                        pref.channels) if pref.channels else None,
                    priority_threshold=pref.priority_threshold,
                )
                count += 1
            except Exception:
                pass

        return count

    def get_company_preference_summary(
        self,
    ) -> Dict[str, Any]:
        """
        Get summary of preferences across all company users.

        Useful for admin reporting.
        """
        users = self.db.query(User).filter(
            User.company_id == self.company_id,
        ).count()

        preferences = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
        ).all()

        # Count by event type
        event_counts = {}
        for event_type in self.DEFAULT_PREFERENCES.keys():
            event_prefs = [
                p for p in preferences if p.event_type == event_type]
            enabled = sum(1 for p in event_prefs if p.enabled)
            event_counts[event_type] = {
                "total_configured": len(event_prefs),
                "enabled": enabled,
                "disabled": len(event_prefs) - enabled,
            }

        # Digest settings
        digest_counts = {"none": 0, "daily": 0, "weekly": 0}

        all_users = self.db.query(User).filter(
            User.company_id == self.company_id,
        ).all()

        for user in all_users:
            try:
                metadata = json.loads(user.metadata_json or "{}")
                freq = metadata.get(
                    "digest_settings", {}).get(
                    "frequency", "none")
                digest_counts[freq] = digest_counts.get(freq, 0) + 1
            except (json.JSONDecodeError, TypeError):
                digest_counts["none"] += 1

        return {
            "total_users": users,
            "event_type_breakdown": event_counts,
            "digest_breakdown": digest_counts,
        }
