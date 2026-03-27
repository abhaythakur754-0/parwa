"""
Logistics Variant for PARWA.

Supply chain and logistics support automation with:
- Route Optimization
- Shipment Tracking
- Carrier Integration Hub
- Supply Chain Intelligence
- Delivery Milestone Management
"""

from variants.logistics.route_optimizer import (
    RouteOptimizer,
    OptimizationMode,
    RouteResult,
)
from variants.logistics.shipment_tracker import (
    ShipmentTracker,
    ShipmentStatus,
    TrackingEvent,
)
from variants.logistics.carrier_integration import (
    CarrierIntegrationHub,
    CarrierType,
    CarrierResponse,
)
from variants.logistics.supply_chain import (
    SupplyChainIntelligence,
    RiskLevel,
    SupplyChainEvent,
)

__all__ = [
    # Route Optimizer
    'RouteOptimizer',
    'OptimizationMode',
    'RouteResult',
    # Shipment Tracker
    'ShipmentTracker',
    'ShipmentStatus',
    'TrackingEvent',
    # Carrier Integration
    'CarrierIntegrationHub',
    'CarrierType',
    'CarrierResponse',
    # Supply Chain
    'SupplyChainIntelligence',
    'RiskLevel',
    'SupplyChainEvent',
]
