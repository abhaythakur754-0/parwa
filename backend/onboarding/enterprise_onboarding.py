"""
Enterprise Onboarding Module for Enterprise Client Setup.

This module provides enterprise-specific onboarding flows including
contract signing, SSO configuration, and initial setup wizards.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class OnboardingStep(str, Enum):
    """Enterprise onboarding steps."""
    
    COMPANY_INFO = "company_info"
    CONTRACT_REVIEW = "contract_review"
    CONTRACT_SIGNING = "contract_signing"
    SSO_CONFIGURATION = "sso_configuration"
    TEAM_SETUP = "team_setup"
    KNOWLEDGE_BASE = "knowledge_base"
    INTEGRATION_SETUP = "integration_setup"
    TRAINING = "training"
    COMPLETED = "completed"


class OnboardingStepStatus(BaseModel):
    """Status of a single onboarding step."""
    
    step: OnboardingStep
    status: str = "pending"  # pending, in_progress, completed, skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class EnterpriseOnboarding(BaseModel):
    """Enterprise onboarding session model."""
    
    onboarding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    company_name: str
    admin_email: EmailStr
    admin_name: str
    contract_id: Optional[str] = None
    current_step: OnboardingStep = OnboardingStep.COMPANY_INFO
    steps: Dict[str, OnboardingStepStatus] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    assigned_csm: Optional[str] = None
    
    def get_progress_percent(self) -> int:
        """Calculate onboarding progress percentage."""
        total_steps = len(OnboardingStep) - 1  # Exclude COMPLETED
        completed_steps = sum(
            1 for s in self.steps.values()
            if s.status == "completed"
        )
        return int((completed_steps / total_steps) * 100)


class EnterpriseOnboardingService:
    """
    Enterprise onboarding service.
    
    Manages the enterprise client onboarding flow from initial
    setup through full activation.
    """
    
    def __init__(self):
        """Initialize onboarding service."""
        self._onboardings: Dict[str, EnterpriseOnboarding] = {}
        self._tenant_onboarding_index: Dict[str, str] = {}
    
    def start_onboarding(
        self,
        tenant_id: str,
        company_name: str,
        admin_email: str,
        admin_name: str,
        assigned_csm: Optional[str] = None
    ) -> EnterpriseOnboarding:
        """
        Start a new enterprise onboarding process.
        
        Args:
            tenant_id: Tenant identifier
            company_name: Company name
            admin_email: Admin email address
            admin_name: Admin name
            assigned_csm: Assigned Customer Success Manager
            
        Returns:
            Created EnterpriseOnboarding
        """
        # Initialize all steps
        steps = {}
        for step in OnboardingStep:
            steps[step.value] = OnboardingStepStatus(step=step)
        
        onboarding = EnterpriseOnboarding(
            tenant_id=tenant_id,
            company_name=company_name,
            admin_email=admin_email,
            admin_name=admin_name,
            assigned_csm=assigned_csm,
            steps=steps
        )
        
        self._onboardings[onboarding.onboarding_id] = onboarding
        self._tenant_onboarding_index[tenant_id] = onboarding.onboarding_id
        
        return onboarding
    
    def get_onboarding(self, onboarding_id: str) -> Optional[EnterpriseOnboarding]:
        """Get onboarding by ID."""
        return self._onboardings.get(onboarding_id)
    
    def get_onboarding_for_tenant(self, tenant_id: str) -> Optional[EnterpriseOnboarding]:
        """Get onboarding for a tenant."""
        onboarding_id = self._tenant_onboarding_index.get(tenant_id)
        if onboarding_id:
            return self._onboardings.get(onboarding_id)
        return None
    
    def update_step(
        self,
        onboarding_id: str,
        step: OnboardingStep,
        status: str,
        data: Optional[Dict[str, Any]] = None,
        notes: str = ""
    ) -> Optional[EnterpriseOnboarding]:
        """
        Update an onboarding step.
        
        Args:
            onboarding_id: Onboarding identifier
            step: Step to update
            status: New status
            data: Step data
            notes: Notes for the step
            
        Returns:
            Updated onboarding or None
        """
        onboarding = self._onboardings.get(onboarding_id)
        if not onboarding:
            return None
        
        step_status = onboarding.steps.get(step.value)
        if not step_status:
            return None
        
        now = datetime.now(timezone.utc)
        
        step_status.status = status
        step_status.notes = notes
        
        if status == "in_progress" and not step_status.started_at:
            step_status.started_at = now
        
        if status == "completed":
            step_status.completed_at = now
        
        if data:
            step_status.data.update(data)
        
        onboarding.updated_at = now
        
        # Update current step
        if status == "completed":
            onboarding.current_step = self._get_next_step(step)
            
            # Check if all complete
            if onboarding.current_step == OnboardingStep.COMPLETED:
                onboarding.completed_at = now
        
        return onboarding
    
    def _get_next_step(self, current: OnboardingStep) -> OnboardingStep:
        """Get the next step after current."""
        steps = list(OnboardingStep)
        try:
            idx = steps.index(current)
            if idx < len(steps) - 1:
                return steps[idx + 1]
        except ValueError:
            pass
        return OnboardingStep.COMPLETED
    
    def submit_company_info(
        self,
        onboarding_id: str,
        company_info: Dict[str, Any]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Submit company information.
        
        Args:
            onboarding_id: Onboarding identifier
            company_info: Company information dict
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.COMPANY_INFO,
            "completed",
            data=company_info
        )
    
    def link_contract(
        self,
        onboarding_id: str,
        contract_id: str
    ) -> Optional[EnterpriseOnboarding]:
        """
        Link a contract to the onboarding.
        
        Args:
            onboarding_id: Onboarding identifier
            contract_id: Contract identifier
            
        Returns:
            Updated onboarding or None
        """
        onboarding = self._onboardings.get(onboarding_id)
        if not onboarding:
            return None
        
        onboarding.contract_id = contract_id
        onboarding.updated_at = datetime.now(timezone.utc)
        
        return onboarding
    
    def complete_contract_signing(
        self,
        onboarding_id: str,
        signed_by: str,
        signed_at: datetime
    ) -> Optional[EnterpriseOnboarding]:
        """
        Complete contract signing step.
        
        Args:
            onboarding_id: Onboarding identifier
            signed_by: Email of signer
            signed_at: Timestamp of signing
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.CONTRACT_SIGNING,
            "completed",
            data={
                "signed_by": signed_by,
                "signed_at": signed_at.isoformat()
            }
        )
    
    def configure_sso(
        self,
        onboarding_id: str,
        sso_config: Dict[str, Any]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Configure SSO settings.
        
        Args:
            onboarding_id: Onboarding identifier
            sso_config: SSO configuration
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.SSO_CONFIGURATION,
            "completed",
            data=sso_config
        )
    
    def setup_team(
        self,
        onboarding_id: str,
        team_members: List[Dict[str, str]]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Setup initial team members.
        
        Args:
            onboarding_id: Onboarding identifier
            team_members: List of team member data
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.TEAM_SETUP,
            "completed",
            data={"members": team_members, "count": len(team_members)}
        )
    
    def setup_knowledge_base(
        self,
        onboarding_id: str,
        kb_config: Dict[str, Any]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Setup initial knowledge base.
        
        Args:
            onboarding_id: Onboarding identifier
            kb_config: Knowledge base configuration
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.KNOWLEDGE_BASE,
            "completed",
            data=kb_config
        )
    
    def setup_integrations(
        self,
        onboarding_id: str,
        integrations: List[Dict[str, Any]]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Setup integrations.
        
        Args:
            onboarding_id: Onboarding identifier
            integrations: List of integration configs
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.INTEGRATION_SETUP,
            "completed",
            data={"integrations": integrations}
        )
    
    def complete_training(
        self,
        onboarding_id: str,
        training_data: Dict[str, Any]
    ) -> Optional[EnterpriseOnboarding]:
        """
        Complete training step.
        
        Args:
            onboarding_id: Onboarding identifier
            training_data: Training completion data
            
        Returns:
            Updated onboarding or None
        """
        return self.update_step(
            onboarding_id,
            OnboardingStep.TRAINING,
            "completed",
            data=training_data
        )
    
    def get_onboarding_checklist(self, onboarding_id: str) -> List[Dict[str, Any]]:
        """
        Get onboarding checklist with status.
        
        Args:
            onboarding_id: Onboarding identifier
            
        Returns:
            List of checklist items
        """
        onboarding = self._onboardings.get(onboarding_id)
        if not onboarding:
            return []
        
        checklist = []
        for step in OnboardingStep:
            if step == OnboardingStep.COMPLETED:
                continue
            
            step_status = onboarding.steps.get(step.value)
            checklist.append({
                "step": step.value,
                "name": self._get_step_display_name(step),
                "status": step_status.status if step_status else "pending",
                "description": self._get_step_description(step)
            })
        
        return checklist
    
    def _get_step_display_name(self, step: OnboardingStep) -> str:
        """Get display name for a step."""
        names = {
            OnboardingStep.COMPANY_INFO: "Company Information",
            OnboardingStep.CONTRACT_REVIEW: "Contract Review",
            OnboardingStep.CONTRACT_SIGNING: "Contract Signing",
            OnboardingStep.SSO_CONFIGURATION: "SSO Configuration",
            OnboardingStep.TEAM_SETUP: "Team Setup",
            OnboardingStep.KNOWLEDGE_BASE: "Knowledge Base Setup",
            OnboardingStep.INTEGRATION_SETUP: "Integration Setup",
            OnboardingStep.TRAINING: "Training & Onboarding",
            OnboardingStep.COMPLETED: "Completed"
        }
        return names.get(step, step.value)
    
    def _get_step_description(self, step: OnboardingStep) -> str:
        """Get description for a step."""
        descriptions = {
            OnboardingStep.COMPANY_INFO: "Provide your company details and billing information",
            OnboardingStep.CONTRACT_REVIEW: "Review your enterprise contract terms",
            OnboardingStep.CONTRACT_SIGNING: "Sign your enterprise agreement",
            OnboardingStep.SSO_CONFIGURATION: "Configure SSO with your identity provider",
            OnboardingStep.TEAM_SETUP: "Add your team members and assign roles",
            OnboardingStep.KNOWLEDGE_BASE: "Set up your initial knowledge base",
            OnboardingStep.INTEGRATION_SETUP: "Connect your existing tools",
            OnboardingStep.TRAINING: "Complete admin training session",
            OnboardingStep.COMPLETED: "Onboarding complete!"
        }
        return descriptions.get(step, "")


# Global service instance
_enterprise_onboarding_service: Optional[EnterpriseOnboardingService] = None


def get_enterprise_onboarding_service() -> EnterpriseOnboardingService:
    """Get the enterprise onboarding service instance."""
    global _enterprise_onboarding_service
    if _enterprise_onboarding_service is None:
        _enterprise_onboarding_service = EnterpriseOnboardingService()
    return _enterprise_onboarding_service
