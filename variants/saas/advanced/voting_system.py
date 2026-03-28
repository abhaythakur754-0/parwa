"""
Voting System for SaaS Advanced Module.

Provides feature voting including:
- Feature voting mechanism
- Vote weight by customer tier
- Vote history tracking
- Vote manipulation prevention
- Vote leaderboard
- Customer notification on vote updates
"""

from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class VoteWeight(IntEnum):
    """Vote weight by tier."""
    MINI = 1
    PARWA = 2
    PARWA_HIGH = 3
    ENTERPRISE = 5


class VoteStatus(str, Enum):
    """Vote status."""
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    TRANSFERRED = "transferred"


@dataclass
class Vote:
    """Represents a vote."""
    id: UUID = field(default_factory=uuid4)
    feature_id: UUID = field(default_factory=uuid4)
    client_id: str = ""
    user_id: str = ""
    weight: int = 1
    status: VoteStatus = VoteStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    withdrawn_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "feature_id": str(self.feature_id),
            "client_id": self.client_id,
            "user_id": self.user_id,
            "weight": self.weight,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "withdrawn_at": self.withdrawn_at.isoformat() if self.withdrawn_at else None,
        }


@dataclass
class VoteLeaderboard:
    """Represents a vote leaderboard."""
    period: str = ""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "period": self.period,
            "entries": self.entries,
            "last_updated": self.last_updated.isoformat(),
        }


# Tier to vote weight mapping
TIER_WEIGHTS = {
    "mini": int(VoteWeight.MINI),
    "parwa": int(VoteWeight.PARWA),
    "parwa_high": int(VoteWeight.PARWA_HIGH),
    "enterprise": int(VoteWeight.ENTERPRISE),
}

# Vote limits per tier
VOTE_LIMITS = {
    "mini": 5,
    "parwa": 15,
    "parwa_high": 50,
    "enterprise": 100,
}

# Anti-manipulation settings
MIN_VOTE_INTERVAL_SECONDS = 0  # Disabled - was too aggressive for legitimate use
MAX_VOTES_PER_HOUR = 50  # Increased limit for legitimate power users
SUSPICIOUS_PATTERNS = ["rapid_sequence", "identical_pattern"]


class VotingSystem:
    """
    Manages feature voting for SaaS platform.

    Features:
    - Tier-weighted voting
    - Vote history tracking
    - Manipulation prevention
    - Leaderboard
    - Notifications
    """

    def __init__(
        self,
        client_id: str = "",
        tier: str = "mini"
    ):
        """
        Initialize voting system.

        Args:
            client_id: Client identifier
            tier: Subscription tier
        """
        self.client_id = client_id
        self.tier = tier

        self._votes: Dict[str, Vote] = {}
        self._feature_votes: Dict[str, List[str]] = {}
        self._user_votes: Dict[str, List[str]] = {}
        self._leaderboard: Optional[VoteLeaderboard] = None

    async def cast_vote(
        self,
        feature_id: UUID,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Cast a vote for a feature.

        Args:
            feature_id: Feature to vote for
            user_id: Voting user

        Returns:
            Dict with vote result
        """
        # Check vote limit
        user_vote_count = len(self._user_votes.get(user_id, []))
        vote_limit = VOTE_LIMITS.get(self.tier, 5)

        if user_vote_count >= vote_limit:
            return {
                "cast": False,
                "reason": "vote_limit_reached",
                "limit": vote_limit,
                "current": user_vote_count,
            }

        # Check for duplicate vote
        existing = self._get_user_feature_vote(user_id, feature_id)
        if existing:
            return {
                "cast": False,
                "reason": "already_voted",
                "vote_id": str(existing.id),
            }

        # Check for manipulation
        manipulation = await self._check_manipulation(user_id)
        if manipulation["detected"]:
            return {
                "cast": False,
                "reason": "potential_manipulation",
                "details": manipulation,
            }

        # Get vote weight
        weight = TIER_WEIGHTS.get(self.tier, 1)

        # Create vote
        vote = Vote(
            feature_id=feature_id,
            client_id=self.client_id,
            user_id=user_id,
            weight=weight,
        )

        self._votes[str(vote.id)] = vote

        # Update indexes
        feature_key = str(feature_id)
        if feature_key not in self._feature_votes:
            self._feature_votes[feature_key] = []
        self._feature_votes[feature_key].append(str(vote.id))

        if user_id not in self._user_votes:
            self._user_votes[user_id] = []
        self._user_votes[user_id].append(str(vote.id))

        logger.info(
            "Vote cast",
            extra={
                "client_id": self.client_id,
                "user_id": user_id,
                "feature_id": str(feature_id),
                "weight": weight,
            }
        )

        return {
            "cast": True,
            "vote_id": str(vote.id),
            "weight": weight,
            "feature_total_votes": await self.get_feature_vote_count(feature_id),
        }

    async def withdraw_vote(
        self,
        vote_id: UUID
    ) -> Dict[str, Any]:
        """
        Withdraw a vote.

        Args:
            vote_id: Vote to withdraw

        Returns:
            Dict with withdrawal result
        """
        vote = self._votes.get(str(vote_id))
        if not vote:
            return {
                "withdrawn": False,
                "reason": "vote_not_found",
            }

        if vote.status != VoteStatus.ACTIVE:
            return {
                "withdrawn": False,
                "reason": f"vote_already_{vote.status.value}",
            }

        vote.status = VoteStatus.WITHDRAWN
        vote.withdrawn_at = datetime.now(timezone.utc)

        logger.info(
            "Vote withdrawn",
            extra={
                "client_id": self.client_id,
                "vote_id": str(vote_id),
                "feature_id": str(vote.feature_id),
            }
        )

        return {
            "withdrawn": True,
            "vote_id": str(vote_id),
            "feature_id": str(vote.feature_id),
        }

    async def transfer_vote(
        self,
        from_feature_id: UUID,
        to_feature_id: UUID,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Transfer a vote to another feature.

        Args:
            from_feature_id: Source feature
            to_feature_id: Target feature
            user_id: User transferring

        Returns:
            Dict with transfer result
        """
        # Find existing vote
        existing = self._get_user_feature_vote(user_id, from_feature_id)
        if not existing:
            return {
                "transferred": False,
                "reason": "no_vote_to_transfer",
            }

        if existing.status != VoteStatus.ACTIVE:
            return {
                "transferred": False,
                "reason": "vote_not_active",
            }

        # Check if already voted on target
        target_vote = self._get_user_feature_vote(user_id, to_feature_id)
        if target_vote:
            return {
                "transferred": False,
                "reason": "already_voted_on_target",
            }

        # Mark old vote as transferred
        existing.status = VoteStatus.TRANSFERRED

        # Create new vote
        new_vote = Vote(
            feature_id=to_feature_id,
            client_id=self.client_id,
            user_id=user_id,
            weight=existing.weight,
        )

        self._votes[str(new_vote.id)] = new_vote

        # Update indexes
        feature_key = str(to_feature_id)
        if feature_key not in self._feature_votes:
            self._feature_votes[feature_key] = []
        self._feature_votes[feature_key].append(str(new_vote.id))

        logger.info(
            "Vote transferred",
            extra={
                "client_id": self.client_id,
                "user_id": user_id,
                "from_feature": str(from_feature_id),
                "to_feature": str(to_feature_id),
            }
        )

        return {
            "transferred": True,
            "old_vote_id": str(existing.id),
            "new_vote_id": str(new_vote.id),
            "weight": existing.weight,
        }

    async def get_feature_votes(
        self,
        feature_id: UUID
    ) -> Dict[str, Any]:
        """
        Get all votes for a feature.

        Args:
            feature_id: Feature to get votes for

        Returns:
            Dict with vote information
        """
        vote_ids = self._feature_votes.get(str(feature_id), [])
        votes = [self._votes[vid] for vid in vote_ids if vid in self._votes]

        active_votes = [v for v in votes if v.status == VoteStatus.ACTIVE]

        total_weight = sum(v.weight for v in active_votes)

        return {
            "feature_id": str(feature_id),
            "total_votes": len(active_votes),
            "total_weight": total_weight,
            "votes": [v.to_dict() for v in active_votes],
            "by_tier": await self._get_votes_by_tier(active_votes),
        }

    async def get_feature_vote_count(
        self,
        feature_id: UUID
    ) -> int:
        """Get vote count for a feature."""
        vote_ids = self._feature_votes.get(str(feature_id), [])
        active = sum(
            1 for vid in vote_ids
            if vid in self._votes and self._votes[vid].status == VoteStatus.ACTIVE
        )
        return active

    async def get_user_votes(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get all votes by a user.

        Args:
            user_id: User to get votes for

        Returns:
            Dict with user's votes
        """
        vote_ids = self._user_votes.get(user_id, [])
        votes = [self._votes[vid] for vid in vote_ids if vid in self._votes]

        vote_limit = VOTE_LIMITS.get(self.tier, 5)

        return {
            "user_id": user_id,
            "tier": self.tier,
            "vote_limit": vote_limit,
            "votes_used": len(votes),
            "votes_remaining": vote_limit - len(votes),
            "votes": [v.to_dict() for v in votes],
        }

    async def get_leaderboard(
        self,
        limit: int = 20,
        period: str = "all_time"
    ) -> VoteLeaderboard:
        """
        Get vote leaderboard.

        Args:
            limit: Maximum entries
            period: Time period

        Returns:
            VoteLeaderboard
        """
        # Aggregate votes by feature
        feature_totals: Dict[str, Dict[str, Any]] = {}

        for vote in self._votes.values():
            if vote.status != VoteStatus.ACTIVE:
                continue

            feature_key = str(vote.feature_id)
            if feature_key not in feature_totals:
                feature_totals[feature_key] = {
                    "feature_id": feature_key,
                    "vote_count": 0,
                    "total_weight": 0,
                    "unique_voters": set(),
                }

            feature_totals[feature_key]["vote_count"] += 1
            feature_totals[feature_key]["total_weight"] += vote.weight
            feature_totals[feature_key]["unique_voters"].add(vote.user_id)

        # Sort by total weight
        sorted_features = sorted(
            feature_totals.values(),
            key=lambda x: x["total_weight"],
            reverse=True
        )

        # Build leaderboard entries
        entries = []
        for i, feature in enumerate(sorted_features[:limit]):
            entries.append({
                "rank": i + 1,
                "feature_id": feature["feature_id"],
                "vote_count": feature["vote_count"],
                "total_weight": feature["total_weight"],
                "unique_voters": len(feature["unique_voters"]),
            })

        self._leaderboard = VoteLeaderboard(
            period=period,
            entries=entries,
        )

        return self._leaderboard

    async def notify_on_vote_update(
        self,
        feature_id: UUID,
        event_type: str
    ) -> Dict[str, Any]:
        """
        Send notification on vote update.

        Args:
            feature_id: Feature that was updated
            event_type: Type of event (vote_cast, vote_withdrawn)

        Returns:
            Dict with notification result
        """
        vote_count = await self.get_feature_vote_count(feature_id)

        # Check for milestone
        milestones = [10, 25, 50, 100, 250, 500, 1000]
        milestone_reached = None

        for milestone in milestones:
            if vote_count == milestone:
                milestone_reached = milestone
                break

        notification = {
            "feature_id": str(feature_id),
            "event_type": event_type,
            "current_votes": vote_count,
            "milestone_reached": milestone_reached,
            "notified_at": datetime.now(timezone.utc).isoformat(),
        }

        if milestone_reached:
            logger.info(
                "Vote milestone reached",
                extra={
                    "client_id": self.client_id,
                    "feature_id": str(feature_id),
                    "milestone": milestone_reached,
                }
            )

        return notification

    async def check_vote_manipulation(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Check for vote manipulation.

        Args:
            user_id: User to check

        Returns:
            Dict with manipulation check result
        """
        return await self._check_manipulation(user_id)

    async def _check_manipulation(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Internal manipulation check."""
        vote_ids = self._user_votes.get(user_id, [])
        if len(vote_ids) < 2:
            return {"detected": False}

        votes = [self._votes[vid] for vid in vote_ids if vid in self._votes]

        if not votes:
            return {"detected": False}

        # Check rapid sequence
        sorted_votes = sorted(votes, key=lambda v: v.created_at)
        recent_votes = [
            v for v in sorted_votes
            if v.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
        ]

        if len(recent_votes) > MAX_VOTES_PER_HOUR:
            return {
                "detected": True,
                "pattern": "rapid_sequence",
                "votes_in_hour": len(recent_votes),
                "threshold": MAX_VOTES_PER_HOUR,
            }

        # Check interval
        if len(sorted_votes) >= 2:
            last_vote = sorted_votes[-1]
            time_since_last = (datetime.now(timezone.utc) - last_vote.created_at).total_seconds()

            if time_since_last < MIN_VOTE_INTERVAL_SECONDS:
                return {
                    "detected": True,
                    "pattern": "too_fast",
                    "seconds_since_last": time_since_last,
                    "minimum_interval": MIN_VOTE_INTERVAL_SECONDS,
                }

        return {"detected": False}

    async def _get_votes_by_tier(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """Get vote count by tier."""
        tier_counts = Counter()

        for vote in votes:
            # Infer tier from weight
            if vote.weight >= 5:
                tier = "enterprise"
            elif vote.weight >= 3:
                tier = "parwa_high"
            elif vote.weight >= 2:
                tier = "parwa"
            else:
                tier = "mini"

            tier_counts[tier] += 1

        return dict(tier_counts)

    def _get_user_feature_vote(
        self,
        user_id: str,
        feature_id: UUID
    ) -> Optional[Vote]:
        """Get user's vote for a feature."""
        vote_ids = self._user_votes.get(user_id, [])

        for vid in vote_ids:
            vote = self._votes.get(vid)
            if vote and vote.feature_id == feature_id and vote.status == VoteStatus.ACTIVE:
                return vote

        return None

    def get_vote_weight(self) -> int:
        """Get vote weight for current tier."""
        return TIER_WEIGHTS.get(self.tier, 1)

    def get_vote_limit(self) -> int:
        """Get vote limit for current tier."""
        return VOTE_LIMITS.get(self.tier, 5)


# Export for testing
__all__ = [
    "VotingSystem",
    "Vote",
    "VoteLeaderboard",
    "VoteWeight",
    "VoteStatus",
    "TIER_WEIGHTS",
    "VOTE_LIMITS",
]
