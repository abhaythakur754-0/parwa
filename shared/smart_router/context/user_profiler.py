"""
User Profiler for Smart Router
User behavior profiling and preference learning
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SkillLevel(Enum):
    """User skill levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class LanguagePreference(Enum):
    """Language preferences"""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE = "zh"
    JAPANESE = "ja"
    OTHER = "other"


@dataclass
class UserBehavior:
    """User behavior metrics"""
    total_queries: int = 0
    successful_resolutions: int = 0
    escalations: int = 0
    avg_query_length: float = 0.0
    common_intents: Dict[str, int] = field(default_factory=dict)
    preferred_channels: Dict[str, int] = field(default_factory=dict)
    peak_usage_hours: List[int] = field(default_factory=list)
    last_10_queries: List[str] = field(default_factory=list)


@dataclass
class UserProfile:
    """Complete user profile"""
    user_id: str
    client_id: str
    skill_level: SkillLevel
    language_preference: LanguagePreference
    behavior: UserBehavior
    preferences: Dict[str, Any]
    created_at: datetime
    last_updated: datetime
    is_privacy_restricted: bool = False


class UserProfiler:
    """
    Profiles user behavior and preferences.
    Privacy-aware profiling with configurable data retention.
    """
    
    # Privacy settings
    MAX_HISTORY_SIZE = 100  # Max queries to keep
    PII_FIELDS = ['email', 'phone', 'address', 'name']
    
    # Skill level thresholds
    SKILL_THRESHOLDS = {
        SkillLevel.BEGINNER: 0,
        SkillLevel.INTERMEDIATE: 10,
        SkillLevel.ADVANCED: 50,
        SkillLevel.EXPERT: 100,
    }
    
    def __init__(self, privacy_mode: bool = False):
        self.privacy_mode = privacy_mode
        self._profiles: Dict[str, UserProfile] = {}
        self._behavior_history: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True
    
    def create_profile(
        self,
        user_id: str,
        client_id: str,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            initial_data: Optional initial profile data
            
        Returns:
            Created UserProfile
        """
        profile = UserProfile(
            user_id=user_id,
            client_id=client_id,
            skill_level=SkillLevel.BEGINNER,
            language_preference=LanguagePreference.ENGLISH,
            behavior=UserBehavior(),
            preferences=initial_data or {},
            created_at=datetime.now(),
            last_updated=datetime.now(),
            is_privacy_restricted=self.privacy_mode
        )
        
        self._profiles[user_id] = profile
        self._behavior_history[user_id] = []
        
        logger.info(f"Created profile for user {user_id}")
        return profile
    
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile."""
        return self._profiles.get(user_id)
    
    def update_behavior(
        self,
        user_id: str,
        query: str,
        intent: str,
        channel: str,
        resolved: bool,
        escalated: bool = False
    ) -> bool:
        """
        Update user behavior metrics.
        
        Args:
            user_id: User identifier
            query: User query
            intent: Detected intent
            channel: Communication channel
            resolved: Whether query was resolved
            escalated: Whether query was escalated
            
        Returns:
            True if update successful
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return False
        
        behavior = profile.behavior
        
        # Update basic metrics
        behavior.total_queries += 1
        if resolved:
            behavior.successful_resolutions += 1
        if escalated:
            behavior.escalations += 1
        
        # Update average query length
        if behavior.total_queries == 1:
            behavior.avg_query_length = len(query.split())
        else:
            behavior.avg_query_length = (
                (behavior.avg_query_length * (behavior.total_queries - 1) + len(query.split()))
                / behavior.total_queries
            )
        
        # Update common intents
        behavior.common_intents[intent] = behavior.common_intents.get(intent, 0) + 1
        
        # Update preferred channels
        behavior.preferred_channels[channel] = behavior.preferred_channels.get(channel, 0) + 1
        
        # Update peak hours
        current_hour = datetime.now().hour
        if current_hour not in behavior.peak_usage_hours:
            behavior.peak_usage_hours.append(current_hour)
            # Keep only top 5 hours
            if len(behavior.peak_usage_hours) > 5:
                behavior.peak_usage_hours = behavior.peak_usage_hours[-5:]
        
        # Update query history
        sanitized_query = self._sanitize_pii(query) if self.privacy_mode else query
        behavior.last_10_queries.append(sanitized_query)
        if len(behavior.last_10_queries) > 10:
            behavior.last_10_queries = behavior.last_10_queries[-10:]
        
        # Record behavior event
        self._behavior_history[user_id].append({
            'timestamp': datetime.now().isoformat(),
            'intent': intent,
            'channel': channel,
            'resolved': resolved,
            'escalated': escalated,
        })
        
        # Trim history
        if len(self._behavior_history[user_id]) > self.MAX_HISTORY_SIZE:
            self._behavior_history[user_id] = self._behavior_history[user_id][-self.MAX_HISTORY_SIZE:]
        
        # Update skill level
        profile.skill_level = self._calculate_skill_level(behavior)
        
        profile.last_updated = datetime.now()
        
        return True
    
    def _calculate_skill_level(self, behavior: UserBehavior) -> SkillLevel:
        """Calculate user skill level from behavior."""
        total = behavior.total_queries
        
        if total >= self.SKILL_THRESHOLDS[SkillLevel.EXPERT]:
            return SkillLevel.EXPERT
        elif total >= self.SKILL_THRESHOLDS[SkillLevel.ADVANCED]:
            return SkillLevel.ADVANCED
        elif total >= self.SKILL_THRESHOLDS[SkillLevel.INTERMEDIATE]:
            return SkillLevel.INTERMEDIATE
        else:
            return SkillLevel.BEGINNER
    
    def _sanitize_pii(self, text: str) -> str:
        """Remove PII from text."""
        import re
        sanitized = text
        
        # Email patterns
        sanitized = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', sanitized)
        
        # Phone patterns
        sanitized = re.sub(r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[PHONE]', sanitized)
        
        return sanitized
    
    def learn_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: Any
    ) -> bool:
        """
        Learn a user preference.
        
        Args:
            user_id: User identifier
            preference_key: Preference name
            preference_value: Preference value
            
        Returns:
            True if learned successfully
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return False
        
        profile.preferences[preference_key] = preference_value
        profile.last_updated = datetime.now()
        
        logger.debug(f"Learned preference for user {user_id}: {preference_key}")
        return True
    
    def get_preference(
        self,
        user_id: str,
        preference_key: str,
        default: Any = None
    ) -> Any:
        """Get a user preference."""
        profile = self._profiles.get(user_id)
        if not profile:
            return default
        
        return profile.preferences.get(preference_key, default)
    
    def detect_language_preference(
        self,
        user_id: str,
        query: str
    ) -> LanguagePreference:
        """
        Detect language preference from query.
        
        Args:
            user_id: User identifier
            query: User query
            
        Returns:
            Detected LanguagePreference
        """
        # Simple language detection (production would use proper NLP)
        language_markers = {
            LanguagePreference.SPANISH: ['hola', 'gracias', 'por favor', 'ayuda'],
            LanguagePreference.FRENCH: ['bonjour', 'merci', 's\'il vous plaît', 'aide'],
            LanguagePreference.GERMAN: ['hallo', 'danke', 'bitte', 'hilfe'],
            LanguagePreference.CHINESE: ['你好', '谢谢', '请', '帮助'],
            LanguagePreference.JAPANESE: ['こんにちは', 'ありがとう', 'ください', '助けて'],
        }
        
        query_lower = query.lower()
        
        for lang, markers in language_markers.items():
            if any(marker in query_lower for marker in markers):
                # Update profile
                profile = self._profiles.get(user_id)
                if profile:
                    profile.language_preference = lang
                return lang
        
        return LanguagePreference.ENGLISH
    
    def get_behavior_summary(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get summary of user behavior.
        
        Args:
            user_id: User identifier
            
        Returns:
            Behavior summary dict
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return {}
        
        behavior = profile.behavior
        
        resolution_rate = (
            behavior.successful_resolutions / behavior.total_queries
            if behavior.total_queries > 0 else 0
        )
        
        escalation_rate = (
            behavior.escalations / behavior.total_queries
            if behavior.total_queries > 0 else 0
        )
        
        return {
            'total_queries': behavior.total_queries,
            'resolution_rate': resolution_rate,
            'escalation_rate': escalation_rate,
            'skill_level': profile.skill_level.value,
            'top_intents': sorted(
                behavior.common_intents.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'preferred_channel': max(
                behavior.preferred_channels.items(),
                key=lambda x: x[1]
            )[0] if behavior.preferred_channels else None,
        }
    
    def get_similar_users(
        self,
        user_id: str,
        limit: int = 5
    ) -> List[str]:
        """
        Find users with similar behavior patterns.
        
        Args:
            user_id: User identifier
            limit: Maximum number of similar users
            
        Returns:
            List of similar user IDs
        """
        profile = self._profiles.get(user_id)
        if not profile:
            return []
        
        user_intents = set(profile.behavior.common_intents.keys())
        
        similarities: List[tuple[str, float]] = []
        
        for other_id, other_profile in self._profiles.items():
            if other_id == user_id:
                continue
            
            other_intents = set(other_profile.behavior.common_intents.keys())
            
            # Jaccard similarity
            intersection = len(user_intents & other_intents)
            union = len(user_intents | other_intents)
            similarity = intersection / union if union > 0 else 0
            
            similarities.append((other_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [uid for uid, _ in similarities[:limit]]
    
    def respect_privacy(
        self,
        user_id: str,
        restrict: bool = True
    ) -> None:
        """
        Set privacy restriction for a user.
        
        Args:
            user_id: User identifier
            restrict: Whether to restrict data collection
        """
        profile = self._profiles.get(user_id)
        if profile:
            profile.is_privacy_restricted = restrict
            
            if restrict:
                # Clear PII from history
                profile.behavior.last_10_queries = [
                    self._sanitize_pii(q) for q in profile.behavior.last_10_queries
                ]
    
    def is_initialized(self) -> bool:
        """Check if profiler is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics."""
        return {
            'total_profiles': len(self._profiles),
            'privacy_restricted': sum(
                1 for p in self._profiles.values()
                if p.is_privacy_restricted
            ),
            'skill_distribution': {
                level.value: sum(
                    1 for p in self._profiles.values()
                    if p.skill_level == level
                )
                for level in SkillLevel
            },
        }
