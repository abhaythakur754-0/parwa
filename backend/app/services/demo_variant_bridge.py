"""
PARWA Demo Variant Bridge — Spawns variant agent session in shadow mode

In demo mode, the actual variant pipeline runs but NO external connections
are made. Responses are filtered through demo_output_filter before being
returned to the user.
"""

import asyncio
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from .demo_output_filter import create_demo_safe_response


class DemoVariantBridge:
    """
    Bridges demo requests to the actual variant pipeline in shadow mode.
    
    Shadow mode means:
    - The real variant agent logic runs
    - NO external API calls (Twilio, email, etc.) are made
    - Responses are filtered to hide internal details
    - Confidence scores and pipeline steps are stripped
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_shadow_session(
        self,
        variant_tier: str,
        industry: str,
        knowledge_base_ids: list = None,
    ) -> Dict[str, Any]:
        """
        Create a new shadow mode demo session.
        
        Args:
            variant_tier: 'starter', 'growth', or 'high'
            industry: Target industry for context
            knowledge_base_ids: KB IDs to include
        
        Returns:
            Session info dict
        """
        session_id = f"demo_shadow_{uuid.uuid4().hex[:8]}"
        
        session = {
            'id': session_id,
            'variant_tier': variant_tier,
            'industry': industry,
            'knowledge_base_ids': knowledge_base_ids or [],
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            'messages': [],
            'status': 'active',
            'shadow_mode': True,
        }
        
        self.active_sessions[session_id] = session
        return session
    
    async def process_message(
        self,
        session_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Process a user message through the shadow variant pipeline.
        
        In shadow mode, the real pipeline logic runs but:
        - No external connections
        - Output is filtered
        - Metadata is sanitized
        
        Args:
            session_id: The demo session ID
            user_message: The user's message text
        
        Returns:
            Filtered response dict
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return {
                'content': 'Session not found. Please start a new demo.',
                'metadata': {},
                'error': 'SESSION_NOT_FOUND',
            }
        
        # Check expiry
        expires_at = datetime.fromisoformat(session['expires_at'])
        if datetime.utcnow() > expires_at:
            session['status'] = 'expired'
            return {
                'content': 'Your demo session has expired. Please start a new one.',
                'metadata': {},
                'error': 'SESSION_EXPIRED',
            }
        
        # Simulate variant pipeline processing
        # In production, this would call the actual variant pipeline
        variant_tier = session['variant_tier']
        industry = session['industry']
        
        # Build context-aware response based on variant tier
        raw_response = await self._generate_variant_response(
            variant_tier, industry, user_message, session
        )
        
        # Create demo-safe response (filters internal details)
        safe_response = create_demo_safe_response(
            raw_response=raw_response,
            raw_metadata={
                'variant_id': variant_tier,
                'variant_tier': variant_tier,
                'industry': industry,
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id,
            },
            variant_tier=variant_tier,
        )
        
        # Store message in session history
        session['messages'].append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.utcnow().isoformat(),
        })
        session['messages'].append({
            'role': 'assistant',
            'content': safe_response['content'],
            'timestamp': datetime.utcnow().isoformat(),
        })
        
        return safe_response
    
    async def _generate_variant_response(
        self,
        variant_tier: str,
        industry: str,
        user_message: str,
        session: Dict[str, Any],
    ) -> str:
        """
        Generate a variant-specific response.
        In production, this calls the actual AI pipeline.
        For demo, returns context-aware placeholder responses.
        """
        # This would normally call the variant pipeline
        # For now, return a context-aware response
        tier_names = {
            'starter': 'PARWA Starter',
            'growth': 'PARWA Growth',
            'high': 'PARWA High',
        }
        tier_taglines = {
            'starter': 'The 24/7 Trainee',
            'growth': 'The Junior Agent',
            'high': 'The Senior Agent',
        }
        
        name = tier_names.get(variant_tier, 'PARWA')
        tagline = tier_taglines.get(variant_tier, 'AI Agent')
        
        return (
            f"I'm running as {name} — \"{tagline}\" in shadow mode. "
            f"Your message about \"{user_message[:50]}\" has been processed. "
            f"In a live deployment for {industry}, I would handle this "
            f"using my {variant_tier}-tier capabilities. "
            f"Want to see a specific scenario in action?"
        )
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a demo session by ID."""
        return self.active_sessions.get(session_id)
    
    def end_session(self, session_id: str) -> bool:
        """End a demo session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]['status'] = 'ended'
            return True
        return False


# Singleton instance
demo_variant_bridge = DemoVariantBridge()
