"""
Feature Request Handler for SaaS Advanced Module.

Provides feature request handling including:
- Feature request submission handling
- Request categorization
- Duplicate detection
- Priority scoring
- Status tracking
- Customer communication on status
- Integration with GitHub issues
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import re

logger = logging.getLogger(__name__)


class RequestStatus(str, Enum):
    """Feature request status."""
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    DUPLICATE = "duplicate"


class RequestPriority(str, Enum):
    """Request priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequestCategory(str, Enum):
    """Request categories."""
    NEW_FEATURE = "new_feature"
    ENHANCEMENT = "enhancement"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    UX_UI = "ux_ui"
    API = "api"
    REPORTING = "reporting"
    OTHER = "other"


@dataclass
class FeatureRequest:
    """Represents a feature request."""
    id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    title: str = ""
    description: str = ""
    category: RequestCategory = RequestCategory.NEW_FEATURE
    priority: RequestPriority = RequestPriority.MEDIUM
    status: RequestStatus = RequestStatus.SUBMITTED
    submitted_by: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    votes: int = 0
    voter_ids: List[str] = field(default_factory=list)
    duplicate_of: Optional[UUID] = None
    github_issue_id: Optional[str] = None
    github_issue_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    estimated_effort: Optional[str] = None
    target_release: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "client_id": self.client_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat(),
            "votes": self.votes,
            "voter_count": len(self.voter_ids),
            "duplicate_of": str(self.duplicate_of) if self.duplicate_of else None,
            "github_issue_id": self.github_issue_id,
            "github_issue_url": self.github_issue_url,
            "tags": self.tags,
            "assigned_to": self.assigned_to,
            "estimated_effort": self.estimated_effort,
            "target_release": self.target_release,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
        }


# Priority scoring weights
PRIORITY_FACTORS = {
    "enterprise_client": 3,
    "annual_contract": 2,
    "multiple_requests_similar": 2,
    "votes_threshold_10": 1,
    "votes_threshold_50": 2,
    "votes_threshold_100": 3,
    "strategic_value": 2,
}

# Category to priority mapping
CATEGORY_PRIORITY_BOOST = {
    RequestCategory.SECURITY: 2,
    RequestCategory.PERFORMANCE: 1,
    RequestCategory.API: 1,
}


class FeatureRequestHandler:
    """
    Handles feature requests for SaaS platform.

    Features:
    - Request submission
    - Categorization
    - Duplicate detection
    - Priority scoring
    - Status tracking
    - Customer communication
    - GitHub integration
    """

    def __init__(
        self,
        client_id: str = "",
        client_tier: str = "mini",
        is_enterprise: bool = False
    ):
        """
        Initialize feature request handler.

        Args:
            client_id: Client identifier
            client_tier: Subscription tier
            is_enterprise: Whether client is enterprise
        """
        self.client_id = client_id
        self.client_tier = client_tier
        self.is_enterprise = is_enterprise

        self._requests: Dict[str, FeatureRequest] = {}
        self._request_hashes: Dict[str, str] = {}

    async def submit_request(
        self,
        title: str,
        description: str,
        category: RequestCategory = RequestCategory.NEW_FEATURE,
        submitted_by: str = "",
        tags: Optional[List[str]] = None
    ) -> FeatureRequest:
        """
        Submit a new feature request.

        Args:
            title: Request title
            description: Detailed description
            category: Request category
            submitted_by: Submitter identifier
            tags: Optional tags

        Returns:
            Created FeatureRequest
        """
        # Generate content hash for duplicate detection
        content_hash = self._generate_hash(title, description)

        # Check for duplicates
        existing_id = self._request_hashes.get(content_hash)
        if existing_id:
            existing = self._requests.get(existing_id)
            if existing:
                # Create as duplicate
                request = FeatureRequest(
                    client_id=self.client_id,
                    title=title,
                    description=description,
                    category=category,
                    status=RequestStatus.DUPLICATE,
                    duplicate_of=existing.id,
                    submitted_by=submitted_by,
                    tags=tags or [],
                )
                self._requests[str(request.id)] = request

                logger.info(
                    "Duplicate feature request detected",
                    extra={
                        "request_id": str(request.id),
                        "duplicate_of": str(existing.id),
                    }
                )

                return request

        # Calculate initial priority
        priority = await self._calculate_priority(category, title, description)

        request = FeatureRequest(
            client_id=self.client_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            submitted_by=submitted_by,
            tags=tags or [],
        )

        self._requests[str(request.id)] = request
        self._request_hashes[content_hash] = str(request.id)

        logger.info(
            "Feature request submitted",
            extra={
                "request_id": str(request.id),
                "title": title,
                "category": category.value,
            }
        )

        return request

    async def categorize_request(
        self,
        request_id: UUID,
        category: RequestCategory
    ) -> FeatureRequest:
        """
        Categorize a feature request.

        Args:
            request_id: Request to categorize
            category: New category

        Returns:
            Updated FeatureRequest
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        request.category = category

        logger.info(
            "Feature request categorized",
            extra={
                "request_id": str(request_id),
                "category": category.value,
            }
        )

        return request

    async def detect_duplicates(
        self,
        title: str,
        description: str
    ) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate requests.

        Args:
            title: Request title
            description: Request description

        Returns:
            List of potential duplicates
        """
        duplicates = []
        title_lower = title.lower()
        title_words = set(re.findall(r'\w+', title_lower))

        for request in self._requests.values():
            if request.status == RequestStatus.DUPLICATE:
                continue

            # Check title similarity
            request_words = set(re.findall(r'\w+', request.title.lower()))
            overlap = len(title_words & request_words)
            similarity = overlap / max(len(title_words), len(request_words), 1)

            if similarity > 0.5:
                duplicates.append({
                    "id": str(request.id),
                    "title": request.title,
                    "similarity": round(similarity, 2),
                    "status": request.status.value,
                    "votes": request.votes,
                })

        # Sort by similarity
        duplicates.sort(key=lambda x: x["similarity"], reverse=True)

        return duplicates[:5]

    async def score_priority(
        self,
        request_id: UUID
    ) -> Dict[str, Any]:
        """
        Score and update request priority.

        Args:
            request_id: Request to score

        Returns:
            Dict with scoring breakdown
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        score = 0
        factors = []

        # Enterprise client boost
        if self.is_enterprise:
            score += PRIORITY_FACTORS["enterprise_client"]
            factors.append("enterprise_client")

        # Vote-based scoring
        if request.votes >= 100:
            score += PRIORITY_FACTORS["votes_threshold_100"]
            factors.append("high_votes")
        elif request.votes >= 50:
            score += PRIORITY_FACTORS["votes_threshold_50"]
            factors.append("good_votes")
        elif request.votes >= 10:
            score += PRIORITY_FACTORS["votes_threshold_10"]
            factors.append("some_votes")

        # Category boost
        category_boost = CATEGORY_PRIORITY_BOOST.get(request.category, 0)
        if category_boost > 0:
            score += category_boost
            factors.append(f"category_{request.category.value}")

        # Determine priority
        if score >= 6:
            priority = RequestPriority.CRITICAL
        elif score >= 4:
            priority = RequestPriority.HIGH
        elif score >= 2:
            priority = RequestPriority.MEDIUM
        else:
            priority = RequestPriority.LOW

        request.priority = priority

        return {
            "request_id": str(request_id),
            "score": score,
            "factors": factors,
            "priority": priority.value,
        }

    async def update_status(
        self,
        request_id: UUID,
        status: RequestStatus,
        note: Optional[str] = None
    ) -> FeatureRequest:
        """
        Update request status.

        Args:
            request_id: Request to update
            status: New status
            note: Optional status note

        Returns:
            Updated FeatureRequest
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        request.status = status

        if note:
            request.notes.append({
                "text": note,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status.value,
            })

        if status == RequestStatus.COMPLETED:
            request.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Feature request status updated",
            extra={
                "request_id": str(request_id),
                "status": status.value,
            }
        )

        return request

    async def add_vote(
        self,
        request_id: UUID,
        voter_id: str
    ) -> Dict[str, Any]:
        """
        Add vote to a request.

        Args:
            request_id: Request to vote on
            voter_id: Voter identifier

        Returns:
            Dict with vote result
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if voter_id in request.voter_ids:
            return {
                "voted": False,
                "reason": "already_voted",
                "votes": request.votes,
            }

        request.voter_ids.append(voter_id)
        request.votes = len(request.voter_ids)

        logger.info(
            "Vote added to feature request",
            extra={
                "request_id": str(request_id),
                "voter_id": voter_id,
                "total_votes": request.votes,
            }
        )

        return {
            "voted": True,
            "votes": request.votes,
        }

    async def link_github_issue(
        self,
        request_id: UUID,
        issue_id: str,
        issue_url: str
    ) -> FeatureRequest:
        """
        Link a GitHub issue to the request.

        Args:
            request_id: Request to link
            issue_id: GitHub issue ID
            issue_url: GitHub issue URL

        Returns:
            Updated FeatureRequest
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        request.github_issue_id = issue_id
        request.github_issue_url = issue_url
        request.status = RequestStatus.PLANNED

        logger.info(
            "GitHub issue linked to feature request",
            extra={
                "request_id": str(request_id),
                "issue_id": issue_id,
            }
        )

        return request

    async def communicate_status(
        self,
        request_id: UUID
    ) -> Dict[str, Any]:
        """
        Prepare status communication for customer.

        Args:
            request_id: Request to communicate

        Returns:
            Dict with communication details
        """
        request = self._requests.get(str(request_id))
        if not request:
            raise ValueError(f"Request {request_id} not found")

        messages = {
            RequestStatus.SUBMITTED: "Your feature request has been submitted and is being reviewed.",
            RequestStatus.REVIEWING: "Your feature request is currently being reviewed by our product team.",
            RequestStatus.PLANNED: "Great news! Your feature request has been added to our roadmap.",
            RequestStatus.IN_PROGRESS: "Your requested feature is currently being developed.",
            RequestStatus.COMPLETED: "Your requested feature has been implemented and is now available!",
            RequestStatus.DECLINED: "Unfortunately, we won't be able to implement this feature at this time.",
            RequestStatus.DUPLICATE: "This request is a duplicate of an existing feature request.",
        }

        message = messages.get(request.status, "Your request is being processed.")

        # Add specific details
        if request.target_release:
            message += f" Target release: {request.target_release}."

        if request.duplicate_of:
            original = self._requests.get(str(request.duplicate_of))
            if original:
                message += f" See original request: {original.title}"

        return {
            "request_id": str(request_id),
            "status": request.status.value,
            "message": message,
            "github_url": request.github_issue_url,
        }

    async def get_request(self, request_id: UUID) -> Optional[FeatureRequest]:
        """
        Get a feature request by ID.

        Args:
            request_id: Request ID

        Returns:
            FeatureRequest if found
        """
        return self._requests.get(str(request_id))

    async def get_requests_by_status(
        self,
        status: RequestStatus
    ) -> List[FeatureRequest]:
        """
        Get all requests by status.

        Args:
            status: Status to filter by

        Returns:
            List of matching requests
        """
        return [
            r for r in self._requests.values()
            if r.status == status
        ]

    async def get_top_requests(self, limit: int = 10) -> List[FeatureRequest]:
        """
        Get top requests by votes.

        Args:
            limit: Maximum to return

        Returns:
            List of top requests
        """
        active = [
            r for r in self._requests.values()
            if r.status not in [RequestStatus.DECLINED, RequestStatus.DUPLICATE]
        ]

        sorted_requests = sorted(
            active,
            key=lambda r: (r.votes, r.priority.value),
            reverse=True
        )

        return sorted_requests[:limit]

    async def get_client_requests(self) -> List[FeatureRequest]:
        """
        Get all requests from current client.

        Returns:
            List of client's requests
        """
        return [
            r for r in self._requests.values()
            if r.client_id == self.client_id
        ]

    def _generate_hash(self, title: str, description: str) -> str:
        """Generate content hash for duplicate detection."""
        normalized = f"{title.lower().strip()}|{description.lower().strip()[:200]}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def _calculate_priority(
        self,
        category: RequestCategory,
        title: str,
        description: str
    ) -> RequestPriority:
        """Calculate initial priority for new request."""
        score = 0

        if self.is_enterprise:
            score += 2

        category_boost = CATEGORY_PRIORITY_BOOST.get(category, 0)
        score += category_boost

        # Check for urgency keywords
        urgency_keywords = ["urgent", "critical", "blocking", "security", "compliance"]
        combined = f"{title} {description}".lower()
        if any(kw in combined for kw in urgency_keywords):
            score += 1

        if score >= 4:
            return RequestPriority.HIGH
        elif score >= 2:
            return RequestPriority.MEDIUM
        else:
            return RequestPriority.LOW


# Export for testing
__all__ = [
    "FeatureRequestHandler",
    "FeatureRequest",
    "RequestStatus",
    "RequestPriority",
    "RequestCategory",
    "PRIORITY_FACTORS",
]
