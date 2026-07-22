"""
Tickets services — organized domain folder.

Contains 24 service modules.
Re-exports from the flat services/ directory for backward compatibility.
"""

from app.services.ticket_service import *  # noqa: F401,F403
from app.services.ticket_lifecycle_service import *  # noqa: F401,F403
from app.services.ticket_state_machine import *  # noqa: F401,F403
from app.services.ticket_analytics_service import *  # noqa: F401,F403
from app.services.ticket_search_service import *  # noqa: F401,F403
from app.services.ticket_merge_service import *  # noqa: F401,F403
from app.services.stale_ticket_service import *  # noqa: F401,F403
from app.services.classification_service import *  # noqa: F401,F403
from app.services.spam_detection_service import *  # noqa: F401,F403
from app.services.assignment_service import *  # noqa: F401,F403
from app.services.agent_assignment_service import *  # noqa: F401,F403
from app.services.priority_service import *  # noqa: F401,F403
from app.services.category_service import *  # noqa: F401,F403
from app.services.tag_service import *  # noqa: F401,F403
from app.services.sla_service import *  # noqa: F401,F403
from app.services.trigger_service import *  # noqa: F401,F403
from app.services.internal_note_service import *  # noqa: F401,F403
from app.services.message_service import *  # noqa: F401,F403
from app.services.attachment_service import *  # noqa: F401,F403
from app.services.custom_field_service import *  # noqa: F401,F403
from app.services.collision_service import *  # noqa: F401,F403
from app.services.bulk_action_service import *  # noqa: F401,F403
from app.services.task_decomposition_service import *  # noqa: F401,F403
from app.services.ooo_detection_service import *  # noqa: F401,F403

