"""
Enterprise Billing - Contract Manager
Manage enterprise contracts
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import uuid


class ContractStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class ContractType(str, Enum):
    ANNUAL = "annual"
    MULTI_YEAR = "multi_year"
    CUSTOM = "custom"


class EnterpriseContract(BaseModel):
    """Enterprise contract definition"""
    contract_id: str = Field(default_factory=lambda: f"ctr_{uuid.uuid4().hex[:8]}")
    client_id: str
    contract_type: ContractType
    status: ContractStatus = ContractStatus.DRAFT
    start_date: datetime
    end_date: datetime
    value: float  # Total contract value
    currency: str = "USD"
    seats: int = 0
    features: List[str] = Field(default_factory=list)
    custom_terms: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    signed_at: Optional[datetime] = None

    model_config = ConfigDict()


class ContractManager:
    """
    Manage enterprise contracts.
    """

    def __init__(self):
        self.contracts: Dict[str, EnterpriseContract] = {}

    def create_contract(
        self,
        client_id: str,
        contract_type: ContractType,
        value: float,
        duration_months: int = 12,
        seats: int = 0,
        features: Optional[List[str]] = None
    ) -> EnterpriseContract:
        """Create a new contract"""
        now = datetime.utcnow()
        contract = EnterpriseContract(
            client_id=client_id,
            contract_type=contract_type,
            start_date=now,
            end_date=now + timedelta(days=duration_months * 30),
            value=value,
            seats=seats,
            features=features or []
        )
        self.contracts[contract.contract_id] = contract
        return contract

    def activate_contract(self, contract_id: str) -> bool:
        """Activate a contract"""
        if contract_id not in self.contracts:
            return False

        contract = self.contracts[contract_id]
        contract.status = ContractStatus.ACTIVE
        contract.signed_at = datetime.utcnow()
        return True

    def terminate_contract(self, contract_id: str) -> bool:
        """Terminate a contract"""
        if contract_id not in self.contracts:
            return False

        self.contracts[contract_id].status = ContractStatus.TERMINATED
        return True

    def renew_contract(
        self,
        contract_id: str,
        new_value: Optional[float] = None,
        additional_months: int = 12
    ) -> Optional[EnterpriseContract]:
        """Renew a contract"""
        if contract_id not in self.contracts:
            return None

        old = self.contracts[contract_id]
        new_contract = EnterpriseContract(
            client_id=old.client_id,
            contract_type=old.contract_type,
            start_date=old.end_date,
            end_date=old.end_date + timedelta(days=additional_months * 30),
            value=new_value or old.value,
            seats=old.seats,
            features=old.features
        )
        self.contracts[new_contract.contract_id] = new_contract
        return new_contract

    def get_client_contracts(self, client_id: str) -> List[EnterpriseContract]:
        """Get all contracts for a client"""
        return [c for c in self.contracts.values() if c.client_id == client_id]

    def get_active_contracts(self) -> List[EnterpriseContract]:
        """Get all active contracts"""
        now = datetime.utcnow()
        return [
            c for c in self.contracts.values()
            if c.status == ContractStatus.ACTIVE and c.end_date > now
        ]

    def get_expiring_contracts(self, days: int = 30) -> List[EnterpriseContract]:
        """Get contracts expiring within days"""
        now = datetime.utcnow()
        threshold = now + timedelta(days=days)
        return [
            c for c in self.contracts.values()
            if c.status == ContractStatus.ACTIVE and now < c.end_date <= threshold
        ]
