"""
PARWA NLP Provisioner.

NLP-based agent provisioning service that interprets natural language
commands to provision, configure, and manage agents.

CRITICAL Test Case:
- "Add 2 Mini" → agents spun up, billing updated

Features:
- Provision agents from NLP commands
- Spin up new agents
- Update billing based on agent count
- Support for all variants (mini, parwa, parwa_high)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
import uuid

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger
from backend.nlp.command_parser import CommandParser, IntentType

logger = get_logger(__name__)


class AgentVariant(str, Enum):
    """Supported agent variants."""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class ProvisionStatus(str, Enum):
    """Status of provision operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentInstance:
    """Represents a provisioned agent instance."""
    agent_id: str
    variant: AgentVariant
    company_id: str
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProvisionRequest(BaseModel):
    """Provision request model."""
    request_id: str
    company_id: str
    variant: str
    count: int = Field(ge=1, le=100)
    status: ProvisionStatus = ProvisionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agents: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class ProvisionResult(BaseModel):
    """Result of a provision operation."""
    success: bool
    request_id: str
    company_id: str
    variant: str
    agents_provisioned: int
    agent_ids: List[str]
    billing_updated: bool
    total_monthly_cost: float
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict()


class BillingUpdate(BaseModel):
    """Billing update result."""
    company_id: str
    previous_agent_count: int
    new_agent_count: int
    previous_monthly_cost: float
    new_monthly_cost: float
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict()


class NLPProvisioner:
    """
    NLP-based agent provisioner.

    Interprets natural language commands to provision agents.

    CRITICAL Test Case:
    - "Add 2 Mini" → agents spun up, billing updated

    Features:
    - Parse NLP commands for provisioning
    - Spin up new agents
    - Update billing automatically
    - Support for all variants
    """

    # Pricing per variant (monthly)
    VARIANT_PRICING = {
        AgentVariant.MINI: 29.0,
        AgentVariant.PARWA: 99.0,
        AgentVariant.PARWA_HIGH: 299.0,
    }

    # Variant limits
    VARIANT_LIMITS = {
        AgentVariant.MINI: 10,
        AgentVariant.PARWA: 50,
        AgentVariant.PARWA_HIGH: 100,
    }

    def __init__(
        self,
        command_parser: Optional[CommandParser] = None
    ) -> None:
        """
        Initialize NLP Provisioner.

        Args:
            command_parser: Optional command parser instance
        """
        self._parser = command_parser or CommandParser()
        self._provision_requests: Dict[str, ProvisionRequest] = {}
        self._agents: Dict[str, AgentInstance] = {}
        self._company_agents: Dict[str, List[str]] = {}
        self._billing: Dict[str, Dict[str, Any]] = {}

        logger.info({
            "event": "nlp_provisioner_initialized",
            "variants": [v.value for v in AgentVariant]
        })

    async def provision_agents(
        self,
        command: Dict[str, Any],
        company_id: str
    ) -> ProvisionResult:
        """
        Provision agents from parsed NLP command.

        CRITICAL Test Case:
        - "Add 2 Mini" → agents spun up, billing updated

        Args:
            command: Parsed command dict with action, entities
            company_id: Company to provision agents for

        Returns:
            ProvisionResult with provisioned agent IDs
        """
        # Extract provisioning details
        variant = command.get("entities", {}).get("type", "mini")
        count = command.get("entities", {}).get("count", 1)

        # Map variant string to enum
        variant_enum = self._map_variant(variant)

        # Create provision request
        request_id = f"prov-{uuid.uuid4().hex[:8]}"
        request = ProvisionRequest(
            request_id=request_id,
            company_id=company_id,
            variant=variant_enum.value,
            count=count
        )
        self._provision_requests[request_id] = request

        logger.info({
            "event": "provision_request_created",
            "request_id": request_id,
            "company_id": company_id,
            "variant": variant_enum.value,
            "count": count
        })

        # Spin up agents
        agent_ids = await self.spin_up_agent(variant_enum.value, count, company_id)

        # Update billing
        billing_result = await self.update_billing(company_id, agent_ids)

        # Update request status
        request.status = ProvisionStatus.COMPLETED
        request.agents = agent_ids

        # Calculate total cost
        unit_cost = self.VARIANT_PRICING.get(variant_enum, 29.0)
        total_cost = unit_cost * count

        result = ProvisionResult(
            success=True,
            request_id=request_id,
            company_id=company_id,
            variant=variant_enum.value,
            agents_provisioned=len(agent_ids),
            agent_ids=agent_ids,
            billing_updated=billing_result is not None,
            total_monthly_cost=total_cost,
            message=f"Successfully provisioned {count} {variant_enum.value} agent(s)"
        )

        logger.info({
            "event": "provision_completed",
            "request_id": request_id,
            "company_id": company_id,
            "agents_provisioned": len(agent_ids),
            "total_monthly_cost": total_cost
        })

        return result

    async def spin_up_agent(
        self,
        agent_type: str,
        count: int,
        company_id: str
    ) -> List[str]:
        """
        Spin up new agent instances.

        Args:
            agent_type: Type of agent (mini, parwa, parwa_high)
            count: Number of agents to spin up
            company_id: Company to assign agents to

        Returns:
            List of provisioned agent IDs
        """
        variant_enum = self._map_variant(agent_type)
        agent_ids = []

        for i in range(count):
            agent_id = f"agent-{variant_enum.value}-{uuid.uuid4().hex[:8]}"

            agent = AgentInstance(
                agent_id=agent_id,
                variant=variant_enum,
                company_id=company_id,
                status="active",
                metadata={"index": i + 1}
            )

            self._agents[agent_id] = agent
            agent_ids.append(agent_id)

            # Track company agents
            if company_id not in self._company_agents:
                self._company_agents[company_id] = []
            self._company_agents[company_id].append(agent_id)

        logger.info({
            "event": "agents_spun_up",
            "company_id": company_id,
            "variant": variant_enum.value,
            "count": count,
            "agent_ids": agent_ids
        })

        return agent_ids

    async def update_billing(
        self,
        company_id: str,
        agents: List[str]
    ) -> BillingUpdate:
        """
        Update billing for a company based on agent count.

        Args:
            company_id: Company to update billing for
            agents: List of agent IDs to bill for

        Returns:
            BillingUpdate with billing changes
        """
        # Get current billing state
        current = self._billing.get(company_id, {
            "agent_count": 0,
            "monthly_cost": 0.0
        })

        previous_count = current["agent_count"]
        previous_cost = current["monthly_cost"]

        # Calculate new costs
        new_count = previous_count + len(agents)

        # Get company's agent variants
        company_agent_ids = self._company_agents.get(company_id, [])
        new_cost = 0.0
        for agent_id in company_agent_ids:
            agent = self._agents.get(agent_id)
            if agent:
                unit_cost = self.VARIANT_PRICING.get(agent.variant, 29.0)
                new_cost += unit_cost

        # Update billing
        self._billing[company_id] = {
            "agent_count": new_count,
            "monthly_cost": new_cost
        }

        update = BillingUpdate(
            company_id=company_id,
            previous_agent_count=previous_count,
            new_agent_count=new_count,
            previous_monthly_cost=previous_cost,
            new_monthly_cost=new_cost
        )

        logger.info({
            "event": "billing_updated",
            "company_id": company_id,
            "previous_count": previous_count,
            "new_count": new_count,
            "new_monthly_cost": new_cost
        })

        return update

    async def deprovision_agents(
        self,
        company_id: str,
        agent_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Deprovision agents for a company.

        Args:
            company_id: Company ID
            agent_ids: List of agent IDs to deprovision

        Returns:
            Dict with deprovision result
        """
        deprovisioned = []
        not_found = []

        for agent_id in agent_ids:
            agent = self._agents.get(agent_id)

            if agent and agent.company_id == company_id:
                agent.status = "deprovisioned"
                deprovisioned.append(agent_id)

                # Remove from company list
                if company_id in self._company_agents:
                    if agent_id in self._company_agents[company_id]:
                        self._company_agents[company_id].remove(agent_id)
            else:
                not_found.append(agent_id)

        # Update billing
        await self._recalculate_billing(company_id)

        logger.info({
            "event": "agents_deprovisioned",
            "company_id": company_id,
            "deprovisioned": deprovisioned,
            "not_found": not_found
        })

        return {
            "success": True,
            "company_id": company_id,
            "deprovisioned": deprovisioned,
            "not_found": not_found
        }

    async def _recalculate_billing(self, company_id: str) -> None:
        """Recalculate billing for a company."""
        company_agent_ids = self._company_agents.get(company_id, [])
        new_cost = 0.0

        for agent_id in company_agent_ids:
            agent = self._agents.get(agent_id)
            if agent and agent.status == "active":
                unit_cost = self.VARIANT_PRICING.get(agent.variant, 29.0)
                new_cost += unit_cost

        self._billing[company_id] = {
            "agent_count": len([a for a in company_agent_ids
                               if self._agents.get(a, AgentInstance(
                                   agent_id="", variant=AgentVariant.MINI,
                                   company_id=""
                               )).status == "active"]),
            "monthly_cost": new_cost
        }

    def parse_and_provision(
        self,
        text: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Parse natural language and provision agents.

        Args:
            text: Natural language command
            company_id: Company to provision for

        Returns:
            Dict with provisioning result
        """
        # Parse the command
        parsed = self._parser.parse(text)

        if parsed.intent != IntentType.PROVISION:
            return {
                "success": False,
                "error": f"Expected provision intent, got {parsed.intent.value}",
                "suggestions": parsed.suggestions
            }

        # Build command dict for provision_agents
        command = {
            "action": parsed.action,
            "intent": parsed.intent.value,
            "entities": parsed.entities,
            "confidence": parsed.confidence
        }

        # This is a sync wrapper - in production use async
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(self.provision_agents(command, company_id))

        return result.model_dump()

    def get_company_agents(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Get all agents for a company.

        Args:
            company_id: Company ID

        Returns:
            List of agent dicts
        """
        agent_ids = self._company_agents.get(company_id, [])
        agents = []

        for agent_id in agent_ids:
            agent = self._agents.get(agent_id)
            if agent:
                agents.append({
                    "agent_id": agent.agent_id,
                    "variant": agent.variant.value,
                    "status": agent.status,
                    "created_at": agent.created_at.isoformat()
                })

        return agents

    def get_company_billing(self, company_id: str) -> Dict[str, Any]:
        """
        Get billing info for a company.

        Args:
            company_id: Company ID

        Returns:
            Dict with billing info
        """
        return self._billing.get(company_id, {
            "agent_count": 0,
            "monthly_cost": 0.0
        })

    def get_provision_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a provision request by ID.

        Args:
            request_id: Request ID

        Returns:
            Request dict or None
        """
        request = self._provision_requests.get(request_id)
        if request:
            return {
                "request_id": request.request_id,
                "company_id": request.company_id,
                "variant": request.variant,
                "count": request.count,
                "status": request.status,
                "agents": request.agents
            }
        return None

    def _map_variant(self, variant: str) -> AgentVariant:
        """Map string variant to enum."""
        mapping = {
            "mini": AgentVariant.MINI,
            "parwa": AgentVariant.PARWA,
            "parwa_high": AgentVariant.PARWA_HIGH,
            "high": AgentVariant.PARWA_HIGH,
        }
        return mapping.get(variant.lower(), AgentVariant.MINI)


def get_nlp_provisioner() -> NLPProvisioner:
    """
    Get an NLP Provisioner instance.

    Returns:
        NLPProvisioner instance
    """
    return NLPProvisioner()
