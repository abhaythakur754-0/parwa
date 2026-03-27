"""
Shipment Tracker.
Week 33, Logistics Module: Real-time shipment tracking and milestone management.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


class ShipmentStatus(Enum):
    """Shipment status enumeration."""
    PENDING = "pending"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class TrackingEvent:
    """Tracking event type."""
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DEPARTED = "departed"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERY_ATTEMPTED = "delivery_attempted"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    CUSTOMS = "customs"
    RETURNED = "returned"


@dataclass
class TrackingCheckpoint:
    """A checkpoint in shipment tracking."""
    checkpoint_id: str
    status: str
    location: str
    timestamp: datetime
    description: str
    carrier_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checkpoint_id': self.checkpoint_id,
            'status': self.status,
            'location': self.location,
            'timestamp': self.timestamp.isoformat(),
            'description': self.description,
            'carrier_code': self.carrier_code,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'zip_code': self.zip_code,
            'metadata': self.metadata,
        }


@dataclass
class Shipment:
    """Shipment record."""
    shipment_id: str
    tracking_number: str
    carrier: str
    status: ShipmentStatus
    origin: Dict[str, str]
    destination: Dict[str, str]
    created_at: datetime
    updated_at: datetime
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[Dict[str, float]] = None
    service_type: str = "standard"
    signature_required: bool = False
    checkpoints: List[TrackingCheckpoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'shipment_id': self.shipment_id,
            'tracking_number': self.tracking_number,
            'carrier': self.carrier,
            'status': self.status.value,
            'origin': self.origin,
            'destination': self.destination,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'estimated_delivery': self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            'actual_delivery': self.actual_delivery.isoformat() if self.actual_delivery else None,
            'weight_kg': self.weight_kg,
            'service_type': self.service_type,
            'signature_required': self.signature_required,
            'checkpoint_count': len(self.checkpoints),
            'metadata': self.metadata,
        }

    @property
    def is_delivered(self) -> bool:
        return self.status == ShipmentStatus.DELIVERED

    @property
    def is_in_transit(self) -> bool:
        return self.status in [ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY]

    @property
    def has_exception(self) -> bool:
        return self.status == ShipmentStatus.EXCEPTION

    @property
    def latest_checkpoint(self) -> Optional[TrackingCheckpoint]:
        return self.checkpoints[-1] if self.checkpoints else None


class ShipmentTracker:
    """
    Shipment Tracking System.

    Provides real-time tracking for shipments across multiple carriers
    with milestone tracking and delivery estimation.
    """

    # Milestone statuses
    MILESTONES = [
        ("order_placed", "Order Placed"),
        ("label_created", "Label Created"),
        ("picked_up", "Picked Up"),
        ("in_transit", "In Transit"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
    ]

    def __init__(
        self,
        client_id: str,
        enable_notifications: bool = True,
    ):
        """
        Initialize Shipment Tracker.

        Args:
            client_id: Client identifier
            enable_notifications: Enable delivery notifications
        """
        self.client_id = client_id
        self.enable_notifications = enable_notifications

        # Storage
        self._shipments: Dict[str, Shipment] = {}
        self._tracking_index: Dict[str, str] = {}  # tracking_number -> shipment_id

        # Metrics
        self._shipments_tracked = 0
        self._checkpoints_added = 0

        logger.info({
            "event": "shipment_tracker_initialized",
            "client_id": client_id,
        })

    def create_shipment(
        self,
        tracking_number: str,
        carrier: str,
        origin: Dict[str, str],
        destination: Dict[str, str],
        estimated_delivery: Optional[datetime] = None,
        service_type: str = "standard",
        weight_kg: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Shipment:
        """
        Create a new shipment record.

        Args:
            tracking_number: Carrier tracking number
            carrier: Carrier name
            origin: Origin address
            destination: Destination address
            estimated_delivery: Estimated delivery date
            service_type: Service type (standard, express, overnight)
            weight_kg: Package weight
            metadata: Additional metadata

        Returns:
            Created shipment
        """
        shipment_id = f"SHP-{uuid4().hex[:8].upper()}"
        now = datetime.utcnow()

        shipment = Shipment(
            shipment_id=shipment_id,
            tracking_number=tracking_number,
            carrier=carrier,
            status=ShipmentStatus.PENDING,
            origin=origin,
            destination=destination,
            created_at=now,
            updated_at=now,
            estimated_delivery=estimated_delivery,
            service_type=service_type,
            weight_kg=weight_kg,
            metadata=metadata or {},
        )

        # Add initial checkpoint
        initial_checkpoint = TrackingCheckpoint(
            checkpoint_id=f"CHK-{uuid4().hex[:8].upper()}",
            status="pending",
            location=origin.get("city", "Origin"),
            timestamp=now,
            description="Shipment created, awaiting pickup",
            city=origin.get("city"),
            state=origin.get("state"),
            country=origin.get("country", "US"),
        )
        shipment.checkpoints.append(initial_checkpoint)

        self._shipments[shipment_id] = shipment
        self._tracking_index[tracking_number] = shipment_id
        self._shipments_tracked += 1

        logger.info({
            "event": "shipment_created",
            "shipment_id": shipment_id,
            "tracking_number": tracking_number,
            "carrier": carrier,
        })

        return shipment

    def track_shipment(self, tracking_number: str) -> Optional[Shipment]:
        """
        Track a shipment by tracking number.

        Args:
            tracking_number: Tracking number to look up

        Returns:
            Shipment or None
        """
        shipment_id = self._tracking_index.get(tracking_number)
        if shipment_id:
            return self._shipments.get(shipment_id)
        return None

    def add_checkpoint(
        self,
        shipment_id: str,
        status: str,
        location: str,
        description: str,
        timestamp: Optional[datetime] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Optional[TrackingCheckpoint]:
        """
        Add a tracking checkpoint.

        Args:
            shipment_id: Shipment identifier
            status: Checkpoint status
            location: Location name
            description: Checkpoint description
            timestamp: Optional timestamp
            city: City
            state: State
            country: Country

        Returns:
            Created checkpoint
        """
        shipment = self._shipments.get(shipment_id)
        if not shipment:
            return None

        checkpoint = TrackingCheckpoint(
            checkpoint_id=f"CHK-{uuid4().hex[:8].upper()}",
            status=status,
            location=location,
            timestamp=timestamp or datetime.utcnow(),
            description=description,
            city=city,
            state=state,
            country=country,
        )

        shipment.checkpoints.append(checkpoint)
        shipment.updated_at = datetime.utcnow()
        self._checkpoints_added += 1

        # Update shipment status based on checkpoint
        self._update_shipment_status(shipment, status)

        logger.info({
            "event": "checkpoint_added",
            "shipment_id": shipment_id,
            "status": status,
            "location": location,
        })

        return checkpoint

    def update_status(
        self,
        shipment_id: str,
        status: ShipmentStatus,
        notes: Optional[str] = None,
    ) -> Optional[Shipment]:
        """
        Update shipment status.

        Args:
            shipment_id: Shipment identifier
            status: New status
            notes: Optional notes

        Returns:
            Updated shipment
        """
        shipment = self._shipments.get(shipment_id)
        if not shipment:
            return None

        shipment.status = status
        shipment.updated_at = datetime.utcnow()

        if status == ShipmentStatus.DELIVERED:
            shipment.actual_delivery = datetime.utcnow()

        logger.info({
            "event": "shipment_status_updated",
            "shipment_id": shipment_id,
            "status": status.value,
        })

        return shipment

    def get_milestones(self, shipment_id: str) -> List[Dict[str, Any]]:
        """
        Get shipment milestones.

        Args:
            shipment_id: Shipment identifier

        Returns:
            List of milestones with completion status
        """
        shipment = self._shipments.get(shipment_id)
        if not shipment:
            return []

        checkpoint_statuses = {c.status for c in shipment.checkpoints}

        milestones = []
        for status_code, status_name in self.MILESTONES:
            milestones.append({
                "status": status_code,
                "name": status_name,
                "completed": status_code in checkpoint_statuses,
                "timestamp": next(
                    (c.timestamp.isoformat() for c in shipment.checkpoints if c.status == status_code),
                    None
                ),
            })

        return milestones

    def get_transit_time(self, shipment_id: str) -> Optional[int]:
        """
        Get transit time in days.

        Args:
            shipment_id: Shipment identifier

        Returns:
            Transit time in days or None
        """
        shipment = self._shipments.get(shipment_id)
        if not shipment or not shipment.checkpoints:
            return None

        first = shipment.checkpoints[0].timestamp
        last = shipment.actual_delivery or shipment.updated_at

        return (last - first).days

    def list_shipments(
        self,
        status: Optional[ShipmentStatus] = None,
        carrier: Optional[str] = None,
        limit: int = 50,
    ) -> List[Shipment]:
        """
        List shipments with optional filters.

        Args:
            status: Filter by status
            carrier: Filter by carrier
            limit: Maximum results

        Returns:
            List of shipments
        """
        results = list(self._shipments.values())

        if status:
            results = [s for s in results if s.status == status]
        if carrier:
            results = [s for s in results if s.carrier.lower() == carrier.lower()]

        return sorted(results, key=lambda s: s.updated_at, reverse=True)[:limit]

    def get_deliveries_today(self) -> List[Shipment]:
        """Get shipments scheduled for delivery today."""
        today = datetime.utcnow().date()

        return [
            s for s in self._shipments.values()
            if s.estimated_delivery and s.estimated_delivery.date() == today
            and s.status not in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED]
        ]

    def get_exceptions(self) -> List[Shipment]:
        """Get shipments with exceptions."""
        return [s for s in self._shipments.values() if s.has_exception]

    def _update_shipment_status(self, shipment: Shipment, checkpoint_status: str):
        """Update shipment status based on checkpoint."""
        status_map = {
            "picked_up": ShipmentStatus.PICKED_UP,
            "in_transit": ShipmentStatus.IN_TRANSIT,
            "out_for_delivery": ShipmentStatus.OUT_FOR_DELIVERY,
            "delivered": ShipmentStatus.DELIVERED,
            "exception": ShipmentStatus.EXCEPTION,
            "returned": ShipmentStatus.RETURNED,
        }

        new_status = status_map.get(checkpoint_status)
        if new_status:
            shipment.status = new_status

            if new_status == ShipmentStatus.DELIVERED:
                shipment.actual_delivery = datetime.utcnow()

    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        by_status = {}
        for status in ShipmentStatus:
            by_status[status.value] = sum(
                1 for s in self._shipments.values() if s.status == status
            )

        return {
            "client_id": self.client_id,
            "total_shipments": len(self._shipments),
            "shipments_tracked": self._shipments_tracked,
            "checkpoints_added": self._checkpoints_added,
            "by_status": by_status,
            "exceptions": len(self.get_exceptions()),
            "deliveries_today": len(self.get_deliveries_today()),
        }
