"""
Enterprise Billing - Revenue Recognizer
Revenue recognition for enterprise contracts
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from decimal import Decimal


class RevenueStatus(str, Enum):
    RECOGNIZED = "recognized"
    DEFERRED = "deferred"
    PARTIAL = "partial"


class RevenueEntry(BaseModel):
    """Revenue recognition entry"""
    entry_id: str
    contract_id: str
    client_id: str
    amount: float
    recognized_amount: float = 0.0
    deferred_amount: float = 0.0
    status: RevenueStatus = RevenueStatus.DEFERRED
    recognition_date: Optional[datetime] = None
    period_start: datetime
    period_end: datetime

    model_config = ConfigDict()


class RevenueReport(BaseModel):
    """Revenue report"""
    period_start: datetime
    period_end: datetime
    total_contract_value: float
    recognized_revenue: float
    deferred_revenue: float
    entries: List[RevenueEntry] = Field(default_factory=list)

    model_config = ConfigDict()


class RevenueRecognizer:
    """
    Revenue recognition for enterprise contracts.
    """

    def __init__(self):
        self.entries: Dict[str, RevenueEntry] = {}

    def create_entry(
        self,
        contract_id: str,
        client_id: str,
        total_amount: float,
        period_start: datetime,
        period_end: datetime
    ) -> RevenueEntry:
        """Create a revenue entry"""
        import uuid
        entry = RevenueEntry(
            entry_id=f"rev_{uuid.uuid4().hex[:8]}",
            contract_id=contract_id,
            client_id=client_id,
            amount=total_amount,
            deferred_amount=total_amount,
            period_start=period_start,
            period_end=period_end
        )
        self.entries[entry.entry_id] = entry
        return entry

    def recognize_revenue(
        self,
        entry_id: str,
        amount: float
    ) -> bool:
        """Recognize revenue"""
        if entry_id not in self.entries:
            return False

        entry = self.entries[entry_id]
        if amount > entry.deferred_amount:
            return False

        entry.recognized_amount += amount
        entry.deferred_amount -= amount
        entry.recognition_date = datetime.utcnow()

        if entry.deferred_amount == 0:
            entry.status = RevenueStatus.RECOGNIZED
        elif entry.recognized_amount > 0:
            entry.status = RevenueStatus.PARTIAL

        return True

    def auto_recognize_monthly(self) -> List[RevenueEntry]:
        """Auto-recognize monthly revenue"""
        recognized = []
        now = datetime.utcnow()

        for entry in self.entries.values():
            if entry.status == RevenueStatus.DEFERRED:
                # Calculate monthly amount
                days_in_period = (entry.period_end - entry.period_start).days
                days_elapsed = (now - entry.period_start).days
                days_elapsed = max(0, min(days_elapsed, days_in_period))

                monthly_amount = entry.amount / (days_in_period / 30) if days_in_period > 0 else 0
                expected_recognized = (entry.amount * days_elapsed) / days_in_period if days_in_period > 0 else 0

                amount_to_recognize = expected_recognized - entry.recognized_amount
                if amount_to_recognize > 0:
                    self.recognize_revenue(entry.entry_id, amount_to_recognize)
                    recognized.append(entry)

        return recognized

    def get_report(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> RevenueReport:
        """Generate revenue report"""
        entries = [
            e for e in self.entries.values()
            if e.period_start >= period_start and e.period_end <= period_end
        ]

        total_value = sum(e.amount for e in entries)
        recognized = sum(e.recognized_amount for e in entries)
        deferred = sum(e.deferred_amount for e in entries)

        return RevenueReport(
            period_start=period_start,
            period_end=period_end,
            total_contract_value=total_value,
            recognized_revenue=recognized,
            deferred_revenue=deferred,
            entries=entries
        )

    def get_deferred_revenue(self) -> float:
        """Get total deferred revenue"""
        return sum(e.deferred_amount for e in self.entries.values())
