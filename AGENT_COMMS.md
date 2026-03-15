# AGENT_COMMS.md — Week 4 Day 4
# Last updated: 2026-03-30
# Current status: WEEK 4 DAY 4 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 4 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-30

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 COMPLETE ✅ — Auth API, License API, Auth Core, License Manager. 138 tests.
> Day 2 COMPLETE ✅ — Support API, Dashboard API, Billing API, Compliance API. 106 tests.
> Day 3 COMPLETE ✅ — Support Service, Analytics Service, Billing Service, Onboarding Service. 136 tests.
> **Total: 580+ tests passing.**
>
> Day 4: Building remaining APIs and Services — Jarvis, Analytics, Integrations, Notifications.
> All 4 files are INDEPENDENT — build in PARALLEL.
>
> **CRITICAL RULES:**
> 1. You CANNOT use Docker locally — write tests with MOCKED databases
> 2. Build → Unit Test passes → THEN push (ONE push only)
> 3. NEVER push before test passes
> 4. Type hints on ALL functions, docstrings on ALL classes/functions

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/api/jarvis.py`

**Purpose:** Jarvis API routes — AI assistant command and control endpoints.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/app/database.py` — Database session
- `backend/core/auth.py` — Authentication core
- `backend/models/user.py` — User model
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/logger.py` — Logger

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Jarvis/AI Assistant scenarios

**Step 4: Create the API File**

Create `backend/api/jarvis.py` with:

```python
"""
PARWA Jarvis API Routes.

Provides AI assistant command and control endpoints.
"""
from datetime import datetime
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.user import User
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import decode_access_token

# Initialize router and logger
router = APIRouter(prefix="/jarvis", tags=["Jarvis"])
logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()


# --- Pydantic Schemas ---

class JarvisCommandRequest(BaseModel):
    """Request schema for Jarvis command."""
    command: str = Field(..., min_length=1, max_length=1000, description="Command to execute")
    context: Optional[dict] = Field(None, description="Additional context for command")


class JarvisResponse(BaseModel):
    """Response schema for Jarvis command."""
    command_id: uuid.UUID
    status: str
    message: str
    result: Optional[dict] = None
    created_at: datetime


class JarvisStatusResponse(BaseModel):
    """Response schema for Jarvis status."""
    status: str
    version: str
    uptime_seconds: int
    active_commands: int


class PendingApprovalsResponse(BaseModel):
    """Response schema for pending approvals."""
    approvals: List[dict]
    total: int


# --- Helper Functions ---

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate current user from JWT token."""
    token = credentials.credentials
    
    try:
        payload = decode_access_token(token, settings.secret_key.get_secret_value())
    except ValueError as e:
        logger.warning({"event": "token_decode_failed", "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    return user


# --- API Endpoints ---

@router.post(
    "/command",
    response_model=JarvisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Jarvis command",
    description="Send a command to Jarvis AI assistant for processing."
)
async def execute_command(
    request: JarvisCommandRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Execute a Jarvis command.
    
    Args:
        request: Command request with command string and optional context.
        current_user: The authenticated user.
        db: Async database session.
        
    Returns:
        JarvisResponse with command status and result.
    """
    # TODO: Implement actual command processing
    command_id = uuid.uuid4()
    
    logger.info({
        "event": "jarvis_command_executed",
        "command_id": str(command_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
        "command": request.command[:100],  # Log first 100 chars
    })
    
    return JarvisResponse(
        command_id=command_id,
        status="accepted",
        message="Command accepted for processing",
        result=None,
        created_at=datetime.utcnow(),
    )


@router.get(
    "/status",
    response_model=JarvisStatusResponse,
    summary="Get Jarvis status",
    description="Get current status of Jarvis AI assistant."
)
async def get_jarvis_status(
    current_user: User = Depends(get_current_user)
) -> JarvisStatusResponse:
    """
    Get Jarvis status.
    
    Returns:
        JarvisStatusResponse with current status.
    """
    return JarvisStatusResponse(
        status="operational",
        version="1.0.0",
        uptime_seconds=86400,  # Placeholder
        active_commands=0,
    )


@router.get(
    "/pending-approvals",
    response_model=PendingApprovalsResponse,
    summary="Get pending approvals",
    description="Get list of actions pending human approval."
)
async def get_pending_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PendingApprovalsResponse:
    """
    Get pending approvals for the company.
    
    Returns:
        PendingApprovalsResponse with list of pending actions.
    """
    # TODO: Query pending approvals from database
    return PendingApprovalsResponse(
        approvals=[],
        total=0,
    )


@router.post(
    "/pending-approvals/{approval_id}/approve",
    response_model=JarvisResponse,
    summary="Approve pending action",
    description="Approve a pending action that requires human approval."
)
async def approve_pending_action(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Approve a pending action.
    
    Args:
        approval_id: UUID of the pending approval.
        current_user: The authenticated user.
        db: Async database session.
        
    Returns:
        JarvisResponse with approval status.
    """
    logger.info({
        "event": "jarvis_approval_approved",
        "approval_id": str(approval_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
    })
    
    return JarvisResponse(
        command_id=approval_id,
        status="approved",
        message="Action approved successfully",
        result={"approved_by": str(current_user.id)},
        created_at=datetime.utcnow(),
    )


@router.post(
    "/pending-approvals/{approval_id}/reject",
    response_model=JarvisResponse,
    summary="Reject pending action",
    description="Reject a pending action that requires human approval."
)
async def reject_pending_action(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JarvisResponse:
    """
    Reject a pending action.
    
    Args:
        approval_id: UUID of the pending approval.
        current_user: The authenticated user.
        db: Async database session.
        
    Returns:
        JarvisResponse with rejection status.
    """
    logger.info({
        "event": "jarvis_approval_rejected",
        "approval_id": str(approval_id),
        "user_id": str(current_user.id),
        "company_id": str(current_user.company_id),
    })
    
    return JarvisResponse(
        command_id=approval_id,
        status="rejected",
        message="Action rejected",
        result={"rejected_by": str(current_user.id)},
        created_at=datetime.utcnow(),
    )
```

**Step 5: Create the Test File**

Create `tests/unit/test_jarvis.py`:

```python
"""
Unit tests for Jarvis API.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set environment variables before imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "agent@example.com"
    user.company_id = uuid.uuid4()
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = True
    return user


def create_test_app():
    """Create a FastAPI test app with jarvis router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.jarvis import router
    app.include_router(router)

    return app


class TestJarvisEndpoints:
    """Tests for Jarvis API endpoints."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.jarvis import router
        assert router.prefix == "/jarvis"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.jarvis import router
        assert "Jarvis" in router.tags

    def test_command_request_schema(self):
        """Test JarvisCommandRequest schema validation."""
        from backend.api.jarvis import JarvisCommandRequest
        from pydantic import ValidationError

        # Valid request
        valid = JarvisCommandRequest(command="Analyze customer sentiment")
        assert valid.command == "Analyze customer sentiment"

        # Missing command
        with pytest.raises(ValidationError):
            JarvisCommandRequest()

        # Empty command
        with pytest.raises(ValidationError):
            JarvisCommandRequest(command="")

    def test_command_request_with_context(self):
        """Test JarvisCommandRequest with context."""
        from backend.api.jarvis import JarvisCommandRequest

        request = JarvisCommandRequest(
            command="Process refund",
            context={"ticket_id": str(uuid.uuid4()), "amount": 99.99}
        )
        assert request.context is not None

    def test_jarvis_response_schema(self):
        """Test JarvisResponse schema."""
        from backend.api.jarvis import JarvisResponse

        response = JarvisResponse(
            command_id=uuid.uuid4(),
            status="accepted",
            message="Command accepted",
            created_at=datetime.now(timezone.utc)
        )
        assert response.status == "accepted"

    def test_status_response_schema(self):
        """Test JarvisStatusResponse schema."""
        from backend.api.jarvis import JarvisStatusResponse

        response = JarvisStatusResponse(
            status="operational",
            version="1.0.0",
            uptime_seconds=86400,
            active_commands=5
        )
        assert response.status == "operational"
        assert response.version == "1.0.0"


class TestEndpointsWithoutAuth:
    """Tests for endpoints without authentication."""

    def test_execute_command_requires_auth(self):
        """Test that execute command requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/jarvis/command",
                json={"command": "test"}
            )

        assert response.status_code in [401, 403]

    def test_get_status_requires_auth(self):
        """Test that get status requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/jarvis/status")

        assert response.status_code in [401, 403]

    def test_get_pending_approvals_requires_auth(self):
        """Test that get pending approvals requires authentication."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.get("/jarvis/pending-approvals")

        assert response.status_code in [401, 403]

    def test_approve_requires_auth(self):
        """Test that approve requires authentication."""
        app = create_test_app()
        approval_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(f"/jarvis/pending-approvals/{approval_id}/approve")

        assert response.status_code in [401, 403, 422]

    def test_reject_requires_auth(self):
        """Test that reject requires authentication."""
        app = create_test_app()
        approval_id = uuid.uuid4()

        with TestClient(app) as client:
            response = client.post(f"/jarvis/pending-approvals/{approval_id}/reject")

        assert response.status_code in [401, 403, 422]


class TestInvalidUUIDHandling:
    """Tests for invalid UUID handling."""

    def test_approve_invalid_uuid(self):
        """Test approve with invalid UUID."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post("/jarvis/pending-approvals/not-a-uuid/approve")

        assert response.status_code in [401, 403, 422]

    def test_reject_invalid_uuid(self):
        """Test reject with invalid UUID."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post("/jarvis/pending-approvals/not-a-uuid/reject")

        assert response.status_code in [401, 403, 422]
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_jarvis.py -v
```

**Step 7: Fix Until Pass**
Stay in fix loop until ALL tests pass.

**Step 8: Push When Pass**
```bash
git add backend/api/jarvis.py tests/unit/test_jarvis.py
git commit -m "Week 4 Day 4: Builder 1 - Jarvis API with command endpoints"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/api/analytics.py`

**Purpose:** Analytics API routes — metrics and reporting endpoints.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/services/analytics_service.py` — Analytics service (Day 3)
- `backend/app/database.py` — Database session
- `backend/core/auth.py` — Authentication core
- `backend/models/user.py` — User model

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Analytics/Dashboard scenarios

**Step 4: Create the API File**

Create `backend/api/analytics.py` with analytics endpoints that use the AnalyticsService from Day 3:

- `GET /analytics/stats` — Get company statistics
- `GET /analytics/metrics/tickets` — Get ticket metrics
- `GET /analytics/metrics/response-time` — Get response time metrics
- `GET /analytics/metrics/agent-performance` — Get agent performance
- `GET /analytics/activity-feed` — Get activity feed
- `GET /analytics/sla-compliance` — Get SLA compliance

**Step 5: Create the Test File**

Create `tests/unit/test_analytics_api.py` with unit tests for all endpoints.

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_analytics_api.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/api/analytics.py tests/unit/test_analytics_api.py
git commit -m "Week 4 Day 4: Builder 2 - Analytics API with metrics endpoints"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/api/integrations.py`

**Purpose:** Integrations API routes — third-party service integration endpoints.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/app/database.py` — Database session
- `backend/core/auth.py` — Authentication core
- `backend/models/user.py` — User model
- `backend/models/company.py` — Company model
- `shared/core_functions/config.py` — Configuration

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Integrations scenarios

**Step 4: Create the API File**

Create `backend/api/integrations.py` with integration endpoints:

- `GET /integrations` — List available integrations
- `GET /integrations/{integration_type}/status` — Get integration status
- `POST /integrations/{integration_type}/connect` — Connect integration
- `DELETE /integrations/{integration_type}/disconnect` — Disconnect integration
- `GET /integrations/{integration_type}/settings` — Get integration settings
- `PUT /integrations/{integration_type}/settings` — Update integration settings

Supported integration types: `shopify`, `stripe`, `twilio`, `zendesk`, `email`

**Step 5: Create the Test File**

Create `tests/unit/test_integrations_api.py` with unit tests.

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_integrations_api.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/api/integrations.py tests/unit/test_integrations_api.py
git commit -m "Week 4 Day 4: Builder 3 - Integrations API with third-party endpoints"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/notification_service.py`

**Purpose:** Notification service — handles email, SMS, and push notifications.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/user.py` — User model
- `backend/models/company.py` — Company model
- `backend/app/database.py` — Database session
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/logger.py` — Logger

**Step 3: Read BDD Scenario**
- File: `docs/bdd_scenarios/parwa_bdd.md`
- Section: Notifications scenarios

**Step 4: Create the Service File**

Create `backend/services/notification_service.py` with:

```python
"""
Notification Service Layer.

Handles email, SMS, and push notifications.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.user import User
from backend.models.company import Company
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationService:
    """
    Service class for notification business logic.
    
    Provides email, SMS, push, and in-app notifications.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize notification service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send an email notification.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            priority: Notification priority
            
        Returns:
            Dict with notification details
        """
        # TODO: Integrate with Brevo/SendGrid
        logger.info({
            "event": "email_sent",
            "company_id": str(self.company_id),
            "to": to[:50],  # Log partial email for privacy
            "subject": subject,
        })
        
        return {
            "channel": NotificationChannel.EMAIL.value,
            "to": to,
            "subject": subject,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
    
    async def send_sms(
        self,
        to: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Send an SMS notification.
        
        Args:
            to: Recipient phone number
            message: SMS message content
            priority: Notification priority
            
        Returns:
            Dict with notification details
        """
        # TODO: Integrate with Twilio
        logger.info({
            "event": "sms_sent",
            "company_id": str(self.company_id),
            "to": to[:15],  # Log partial number for privacy
        })
        
        return {
            "channel": NotificationChannel.SMS.value,
            "to": to,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
    
    async def send_push(
        self,
        user_id: UUID,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a push notification.
        
        Args:
            user_id: Target user UUID
            title: Notification title
            body: Notification body
            data: Optional additional data
            
        Returns:
            Dict with notification details
        """
        logger.info({
            "event": "push_sent",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "title": title,
        })
        
        return {
            "channel": NotificationChannel.PUSH.value,
            "user_id": str(user_id),
            "title": title,
            "status": "sent",
            "sent_at": datetime.utcnow().isoformat(),
        }
    
    async def send_in_app(
        self,
        user_id: UUID,
        title: str,
        message: str,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an in-app notification.
        
        Args:
            user_id: Target user UUID
            title: Notification title
            message: Notification message
            action_url: Optional URL for action
            
        Returns:
            Dict with notification details
        """
        logger.info({
            "event": "in_app_notification_sent",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "title": title,
        })
        
        return {
            "channel": NotificationChannel.IN_APP.value,
            "user_id": str(user_id),
            "title": title,
            "message": message,
            "action_url": action_url,
            "status": "delivered",
            "created_at": datetime.utcnow().isoformat(),
        }
    
    async def send_notification(
        self,
        channel: NotificationChannel,
        to: Optional[str] = None,
        user_id: Optional[UUID] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        title: Optional[str] = None,
        message: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send notification through specified channel.
        
        Args:
            channel: Notification channel
            to: Recipient (email/phone)
            user_id: Target user UUID
            subject: Subject (for email)
            body: Body content
            title: Title (for push/in-app)
            message: Message content
            priority: Notification priority
            **kwargs: Additional channel-specific parameters
            
        Returns:
            Dict with notification details
        """
        if channel == NotificationChannel.EMAIL:
            return await self.send_email(
                to=to,
                subject=subject or "Notification",
                body=body or message or "",
                priority=priority,
                **kwargs
            )
        elif channel == NotificationChannel.SMS:
            return await self.send_sms(
                to=to,
                message=body or message or "",
                priority=priority
            )
        elif channel == NotificationChannel.PUSH:
            return await self.send_push(
                user_id=user_id,
                title=title or "Notification",
                body=body or message or "",
                **kwargs
            )
        elif channel == NotificationChannel.IN_APP:
            return await self.send_in_app(
                user_id=user_id,
                title=title or "Notification",
                message=body or message or "",
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported channel: {channel}")
    
    async def get_notification_history(
        self,
        user_id: Optional[UUID] = None,
        channel: Optional[NotificationChannel] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get notification history.
        
        Args:
            user_id: Filter by user
            channel: Filter by channel
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of notification records
        """
        # TODO: Query from database
        return []
```

**Step 5: Create the Test File**

Create `tests/unit/test_notification_service.py`:

```python
"""
Unit tests for Notification Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.notification_service import (
    NotificationService,
    NotificationChannel,
    NotificationPriority,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def notification_service(mock_db):
    """Notification service instance with mocked DB."""
    company_id = uuid.uuid4()
    return NotificationService(mock_db, company_id)


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = NotificationService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id


class TestNotificationChannelEnum:
    """Tests for NotificationChannel enum."""
    
    def test_channel_values(self):
        """Test channel enum values."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.SMS.value == "sms"
        assert NotificationChannel.PUSH.value == "push"
        assert NotificationChannel.IN_APP.value == "in_app"


class TestNotificationPriorityEnum:
    """Tests for NotificationPriority enum."""
    
    def test_priority_values(self):
        """Test priority enum values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.URGENT.value == "urgent"


class TestSendEmail:
    """Tests for send_email method."""
    
    @pytest.mark.asyncio
    async def test_send_email_returns_dict(self, notification_service):
        """Test that send_email returns proper dict."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert result["channel"] == "email"
        assert result["to"] == "test@example.com"
        assert result["status"] == "sent"
    
    @pytest.mark.asyncio
    async def test_send_email_with_html(self, notification_service):
        """Test send_email with HTML body."""
        result = await notification_service.send_email(
            to="test@example.com",
            subject="Test",
            body="Plain text",
            html_body="<p>HTML</p>"
        )
        
        assert result["status"] == "sent"


class TestSendSms:
    """Tests for send_sms method."""
    
    @pytest.mark.asyncio
    async def test_send_sms_returns_dict(self, notification_service):
        """Test that send_sms returns proper dict."""
        result = await notification_service.send_sms(
            to="+1234567890",
            message="Test message"
        )
        
        assert result["channel"] == "sms"
        assert result["to"] == "+1234567890"
        assert result["status"] == "sent"


class TestSendPush:
    """Tests for send_push method."""
    
    @pytest.mark.asyncio
    async def test_send_push_returns_dict(self, notification_service):
        """Test that send_push returns proper dict."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_push(
            user_id=user_id,
            title="Test Title",
            body="Test body"
        )
        
        assert result["channel"] == "push"
        assert result["user_id"] == str(user_id)
        assert result["status"] == "sent"


class TestSendInApp:
    """Tests for send_in_app method."""
    
    @pytest.mark.asyncio
    async def test_send_in_app_returns_dict(self, notification_service):
        """Test that send_in_app returns proper dict."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_in_app(
            user_id=user_id,
            title="Test Title",
            message="Test message"
        )
        
        assert result["channel"] == "in_app"
        assert result["user_id"] == str(user_id)
        assert result["status"] == "delivered"


class TestSendNotification:
    """Tests for send_notification unified method."""
    
    @pytest.mark.asyncio
    async def test_send_notification_email(self, notification_service):
        """Test unified send_notification for email."""
        result = await notification_service.send_notification(
            channel=NotificationChannel.EMAIL,
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        
        assert result["channel"] == "email"
    
    @pytest.mark.asyncio
    async def test_send_notification_sms(self, notification_service):
        """Test unified send_notification for SMS."""
        result = await notification_service.send_notification(
            channel=NotificationChannel.SMS,
            to="+1234567890",
            message="Test"
        )
        
        assert result["channel"] == "sms"
    
    @pytest.mark.asyncio
    async def test_send_notification_push(self, notification_service):
        """Test unified send_notification for push."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_notification(
            channel=NotificationChannel.PUSH,
            user_id=user_id,
            title="Test",
            body="Body"
        )
        
        assert result["channel"] == "push"
    
    @pytest.mark.asyncio
    async def test_send_notification_in_app(self, notification_service):
        """Test unified send_notification for in-app."""
        user_id = uuid.uuid4()
        
        result = await notification_service.send_notification(
            channel=NotificationChannel.IN_APP,
            user_id=user_id,
            title="Test",
            message="Message"
        )
        
        assert result["channel"] == "in_app"


class TestGetNotificationHistory:
    """Tests for get_notification_history method."""
    
    @pytest.mark.asyncio
    async def test_get_history_returns_list(self, notification_service):
        """Test that get_notification_history returns list."""
        result = await notification_service.get_notification_history()
        
        assert isinstance(result, list)
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_notification_service.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/services/notification_service.py tests/unit/test_notification_service.py
git commit -m "Week 4 Day 4: Builder 4 - Notification service with multi-channel support"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/api/jarvis.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_jarvis.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 2 → STATUS
**File:** `backend/api/analytics.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_analytics_api.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 3 → STATUS
**File:** `backend/api/integrations.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_integrations_api.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

## BUILDER 4 → STATUS
**File:** `backend/services/notification_service.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_notification_service.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** NONE
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

[Manager will provide guidance here if builders report STUCK]

---

═══════════════════════════════════════════════════════════════════════════════
## ASSISTANCE AGENT → RESPONSE
═══════════════════════════════════════════════════════════════════════════════

[Assistance Agent will provide help here when activated]
