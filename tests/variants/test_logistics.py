"""
Tests for Logistics Module (Week 33).

Tests cover:
- RouteOptimizer: Route optimization, distance calculation
- ShipmentTracker: Tracking, milestones, status updates
- CarrierIntegrationHub: Rate quotes, label creation, tracking
- SupplyChainIntelligence: Risk assessment, inventory alerts
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from variants.logistics.route_optimizer import (
    RouteOptimizer,
    OptimizationMode,
    VehicleType,
    Location,
    RouteResult,
)
from variants.logistics.shipment_tracker import (
    ShipmentTracker,
    ShipmentStatus,
    Shipment,
    TrackingCheckpoint,
)
from variants.logistics.carrier_integration import (
    CarrierIntegrationHub,
    CarrierType,
    ServiceType,
    CarrierResponse,
)
from variants.logistics.supply_chain import (
    SupplyChainIntelligence,
    RiskLevel,
    EventType,
    SupplyChainEvent,
)


# =============================================================================
# Route Optimizer Tests
# =============================================================================

class TestRouteOptimizer:
    """Tests for RouteOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create a route optimizer instance."""
        return RouteOptimizer(client_id="test_client_001")

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations."""
        return [
            Location(
                location_id="DEPOT",
                name="Main Depot",
                address="123 Main St",
                latitude=34.0522,
                longitude=-118.2437,
                is_depot=True,
            ),
            Location(
                location_id="STOP1",
                name="Stop 1",
                address="456 Oak Ave",
                latitude=34.0622,
                longitude=-118.2537,
            ),
            Location(
                location_id="STOP2",
                name="Stop 2",
                address="789 Pine Rd",
                latitude=34.0722,
                longitude=-118.2637,
            ),
        ]

    def test_optimizer_initializes(self, optimizer):
        """Test that optimizer initializes correctly."""
        assert optimizer.client_id == "test_client_001"
        assert optimizer.default_vehicle_type == VehicleType.VAN

    def test_add_location(self, optimizer):
        """Test adding a location."""
        location = Location(
            location_id="LOC1",
            name="Test Location",
            address="123 Test St",
            latitude=34.0,
            longitude=-118.0,
        )

        result = optimizer.add_location(location)

        assert result.location_id == "LOC1"
        assert len(optimizer._locations) == 1

    def test_optimize_route(self, optimizer, sample_locations):
        """Test route optimization."""
        route = optimizer.optimize_route(
            stops=sample_locations,
            mode=OptimizationMode.MOST_EFFICIENT,
        )

        assert route.route_id is not None
        assert route.total_stops == 3
        assert route.total_distance_km > 0
        assert route.optimization_score > 0

    def test_optimize_route_fastest(self, optimizer, sample_locations):
        """Test fastest route mode."""
        route = optimizer.optimize_route(
            stops=sample_locations,
            mode=OptimizationMode.FASTEST,
            vehicle_type=VehicleType.CAR,
        )

        assert route.mode == OptimizationMode.FASTEST

    def test_optimize_route_with_time_windows(self, optimizer):
        """Test route with time windows."""
        locations = [
            Location(
                location_id="DEPOT",
                name="Depot",
                address="1 Main St",
                latitude=34.0,
                longitude=-118.0,
                is_depot=True,
            ),
            Location(
                location_id="STOP1",
                name="Priority Stop",
                address="2 Oak Ave",
                latitude=34.01,
                longitude=-118.01,
                time_window_start=datetime.utcnow(),
                time_window_end=datetime.utcnow() + timedelta(hours=2),
                priority=10,
            ),
        ]

        route = optimizer.optimize_route(locations)

        assert route.total_stops == 2

    def test_optimize_multiple_routes(self, optimizer):
        """Test multiple route optimization."""
        locations = [
            Location(
                location_id="DEPOT",
                name="Depot",
                address="1 Main St",
                latitude=34.0,
                longitude=-118.0,
                is_depot=True,
            ),
        ]

        # Add more locations
        for i in range(6):
            locations.append(Location(
                location_id=f"STOP{i}",
                name=f"Stop {i}",
                address=f"{i} Street",
                latitude=34.0 + (i * 0.01),
                longitude=-118.0 + (i * 0.01),
            ))

        routes = optimizer.optimize_multiple_routes(
            locations=locations,
            num_vehicles=2,
        )

        assert len(routes) == 2

    def test_get_route(self, optimizer, sample_locations):
        """Test getting route by ID."""
        route = optimizer.optimize_route(sample_locations)
        retrieved = optimizer.get_route(route.route_id)

        assert retrieved is not None
        assert retrieved.route_id == route.route_id

    def test_update_route_status(self, optimizer, sample_locations):
        """Test updating route stop status."""
        route = optimizer.optimize_route(sample_locations)
        stop_id = route.stops[0].stop_id

        updated = optimizer.update_route_status(
            route_id=route.route_id,
            stop_id=stop_id,
            status="completed",
        )

        assert updated is not None
        assert updated.stops[0].status == "completed"

    def test_calculate_distance(self, optimizer):
        """Test distance calculation."""
        loc1 = Location(
            location_id="L1",
            name="Location 1",
            address="",
            latitude=34.0522,
            longitude=-118.2437,
        )
        loc2 = Location(
            location_id="L2",
            name="Location 2",
            address="",
            latitude=34.0622,
            longitude=-118.2537,
        )

        distance = optimizer._calculate_distance(loc1, loc2)

        assert distance > 0
        assert distance < 5  # Should be less than 5 km

    def test_get_stats(self, optimizer, sample_locations):
        """Test getting optimizer stats."""
        optimizer.optimize_route(sample_locations)
        stats = optimizer.get_stats()

        assert stats["routes_optimized"] >= 1


# =============================================================================
# Shipment Tracker Tests
# =============================================================================

class TestShipmentTracker:
    """Tests for ShipmentTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a shipment tracker instance."""
        return ShipmentTracker(client_id="test_client_001")

    @pytest.fixture
    def sample_shipment_data(self):
        """Sample shipment data."""
        return {
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
            "origin": {
                "city": "Los Angeles",
                "state": "CA",
                "zip": "90001",
                "country": "US",
            },
            "destination": {
                "city": "New York",
                "state": "NY",
                "zip": "10001",
                "country": "US",
            },
        }

    def test_tracker_initializes(self, tracker):
        """Test that tracker initializes correctly."""
        assert tracker.client_id == "test_client_001"

    def test_create_shipment(self, tracker, sample_shipment_data):
        """Test shipment creation."""
        shipment = tracker.create_shipment(**sample_shipment_data)

        assert shipment.shipment_id is not None
        assert shipment.tracking_number == sample_shipment_data["tracking_number"]
        assert shipment.status == ShipmentStatus.PENDING
        assert len(shipment.checkpoints) == 1

    def test_track_shipment(self, tracker, sample_shipment_data):
        """Test shipment tracking."""
        created = tracker.create_shipment(**sample_shipment_data)
        found = tracker.track_shipment(sample_shipment_data["tracking_number"])

        assert found is not None
        assert found.shipment_id == created.shipment_id

    def test_track_nonexistent_shipment(self, tracker):
        """Test tracking non-existent shipment."""
        result = tracker.track_shipment("NOTFOUND123")

        assert result is None

    def test_add_checkpoint(self, tracker, sample_shipment_data):
        """Test adding checkpoint."""
        shipment = tracker.create_shipment(**sample_shipment_data)

        checkpoint = tracker.add_checkpoint(
            shipment_id=shipment.shipment_id,
            status="in_transit",
            location="Phoenix, AZ",
            description="Package departed facility",
            city="Phoenix",
            state="AZ",
        )

        assert checkpoint is not None
        assert checkpoint.status == "in_transit"
        assert len(shipment.checkpoints) == 2

    def test_update_status(self, tracker, sample_shipment_data):
        """Test status update."""
        shipment = tracker.create_shipment(**sample_shipment_data)

        updated = tracker.update_status(
            shipment_id=shipment.shipment_id,
            status=ShipmentStatus.IN_TRANSIT,
        )

        assert updated.status == ShipmentStatus.IN_TRANSIT

    def test_delivered_sets_actual_delivery(self, tracker, sample_shipment_data):
        """Test that delivered status sets actual delivery time."""
        shipment = tracker.create_shipment(**sample_shipment_data)

        tracker.update_status(
            shipment_id=shipment.shipment_id,
            status=ShipmentStatus.DELIVERED,
        )

        assert shipment.actual_delivery is not None
        assert shipment.is_delivered is True

    def test_get_milestones(self, tracker, sample_shipment_data):
        """Test milestone retrieval."""
        shipment = tracker.create_shipment(**sample_shipment_data)
        tracker.add_checkpoint(
            shipment_id=shipment.shipment_id,
            status="picked_up",
            location="Los Angeles",
            description="Picked up",
        )

        milestones = tracker.get_milestones(shipment.shipment_id)

        assert len(milestones) > 0
        assert any(m["status"] == "picked_up" and m["completed"] for m in milestones)

    def test_list_shipments(self, tracker, sample_shipment_data):
        """Test listing shipments."""
        tracker.create_shipment(**sample_shipment_data)

        shipments = tracker.list_shipments()

        assert len(shipments) >= 1

    def test_list_shipments_by_status(self, tracker, sample_shipment_data):
        """Test listing shipments by status."""
        shipment = tracker.create_shipment(**sample_shipment_data)
        tracker.update_status(shipment.shipment_id, ShipmentStatus.IN_TRANSIT)

        shipments = tracker.list_shipments(status=ShipmentStatus.IN_TRANSIT)

        assert all(s.status == ShipmentStatus.IN_TRANSIT for s in shipments)

    def test_get_deliveries_today(self, tracker):
        """Test getting today's deliveries."""
        today = datetime.utcnow().date()

        shipment = tracker.create_shipment(
            tracking_number="TODAY123",
            carrier="UPS",
            origin={"city": "LA", "state": "CA"},
            destination={"city": "NY", "state": "NY"},
            estimated_delivery=datetime.utcnow(),
        )

        deliveries = tracker.get_deliveries_today()

        assert shipment.shipment_id in [s.shipment_id for s in deliveries]

    def test_get_exceptions(self, tracker, sample_shipment_data):
        """Test getting exception shipments."""
        shipment = tracker.create_shipment(**sample_shipment_data)
        tracker.update_status(shipment.shipment_id, ShipmentStatus.EXCEPTION)

        exceptions = tracker.get_exceptions()

        assert len(exceptions) >= 1


# =============================================================================
# Carrier Integration Tests
# =============================================================================

class TestCarrierIntegrationHub:
    """Tests for CarrierIntegrationHub class."""

    @pytest.fixture
    def hub(self):
        """Create a carrier hub instance."""
        return CarrierIntegrationHub(client_id="test_client_001")

    def test_hub_initializes(self, hub):
        """Test that hub initializes correctly."""
        assert hub.client_id == "test_client_001"
        assert hub.default_carrier == CarrierType.UPS

    def test_get_rates(self, hub):
        """Test getting shipping rates."""
        origin = {"city": "Los Angeles", "state": "CA", "zip": "90001"}
        destination = {"city": "New York", "state": "NY", "zip": "10001"}

        rates = hub.get_rates(
            origin=origin,
            destination=destination,
            weight_kg=5.0,
        )

        assert len(rates) > 0
        assert all(r.total_cost > 0 for r in rates)

    def test_get_rates_sorted_by_cost(self, hub):
        """Test rates are sorted by cost."""
        origin = {"city": "LA", "state": "CA", "zip": "90001"}
        destination = {"city": "NY", "state": "NY", "zip": "10001"}

        rates = hub.get_rates(origin=origin, destination=destination, weight_kg=1.0)

        costs = [r.total_cost for r in rates]
        assert costs == sorted(costs)

    def test_create_label(self, hub):
        """Test creating shipping label."""
        label = hub.create_label(
            carrier=CarrierType.UPS,
            shipment_data={
                "weight_kg": 5.0,
                "origin": {"city": "LA", "state": "CA"},
                "destination": {"city": "NY", "state": "NY"},
            },
            service_type=ServiceType.GROUND,
        )

        assert label.label_id is not None
        assert label.tracking_number is not None
        assert label.tracking_number.startswith("1Z")

    def test_track_shipment(self, hub):
        """Test tracking via carrier hub."""
        response = hub.track_shipment(
            carrier=CarrierType.FEDEX,
            tracking_number="123456789012",
        )

        assert response.success is True
        assert "tracking_number" in response.data

    def test_void_label(self, hub):
        """Test voiding a label."""
        response = hub.void_label(
            carrier=CarrierType.UPS,
            label_id="LBL-12345",
        )

        assert response.success is True
        assert response.data["voided"] is True

    def test_validate_address(self, hub):
        """Test address validation."""
        valid_address = {
            "street": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "zip": "90001",
        }

        response = hub.validate_address(
            carrier=CarrierType.UPS,
            address=valid_address,
        )

        assert response.success is True
        assert response.data["valid"] is True

    def test_schedule_pickup(self, hub):
        """Test scheduling pickup."""
        response = hub.schedule_pickup(
            carrier=CarrierType.UPS,
            pickup_date=datetime.utcnow() + timedelta(days=1),
            location={"city": "LA", "state": "CA", "zip": "90001"},
            packages=5,
        )

        assert response.success is True
        assert "confirmation_number" in response.data


# =============================================================================
# Supply Chain Intelligence Tests
# =============================================================================

class TestSupplyChainIntelligence:
    """Tests for SupplyChainIntelligence class."""

    @pytest.fixture
    def intel(self):
        """Create supply chain intelligence instance."""
        return SupplyChainIntelligence(client_id="test_client_001")

    def test_intel_initializes(self, intel):
        """Test that intel initializes correctly."""
        assert intel.client_id == "test_client_001"
        assert intel.enable_predictive is True

    def test_record_event(self, intel):
        """Test recording supply chain event."""
        event = intel.record_event(
            event_type=EventType.SHIPMENT_DELAYED,
            title="Shipment Delayed",
            description="Weather delay in Chicago hub",
            severity=RiskLevel.MEDIUM,
            location="Chicago, IL",
        )

        assert event.event_id is not None
        assert event.severity == RiskLevel.MEDIUM

    def test_assess_risk(self, intel):
        """Test risk assessment."""
        assessment = intel.assess_risk()

        assert assessment.assessment_id is not None
        assert assessment.overall_risk in RiskLevel
        assert 0 <= assessment.risk_score <= 100
        assert len(assessment.categories) == 5

    def test_check_inventory_critical(self, intel):
        """Test critical inventory alert."""
        alert = intel.check_inventory(
            sku="SKU-001",
            product_name="Critical Product",
            current_stock=10,
            daily_usage=5.0,
            reorder_point=50,
        )

        assert alert is not None
        assert alert.severity == RiskLevel.CRITICAL
        assert alert.days_of_stock == 2

    def test_check_inventory_healthy(self, intel):
        """Test healthy inventory (no alert)."""
        alert = intel.check_inventory(
            sku="SKU-002",
            product_name="Healthy Product",
            current_stock=1000,
            daily_usage=10.0,
            reorder_point=100,
        )

        assert alert is None

    def test_get_active_events(self, intel):
        """Test getting active events."""
        intel.record_event(
            event_type=EventType.PORT_CONGESTION,
            title="Port Congestion",
            description="LA port congested",
            severity=RiskLevel.HIGH,
        )

        events = intel.get_active_events()

        assert len(events) >= 1

    def test_get_active_events_by_severity(self, intel):
        """Test getting events by severity."""
        intel.record_event(
            event_type=EventType.CARRIER_ISSUE,
            title="Carrier Issue",
            description="Carrier delays",
            severity=RiskLevel.HIGH,
        )

        events = intel.get_active_events(severity=RiskLevel.HIGH)

        assert all(e.severity == RiskLevel.HIGH for e in events)

    def test_resolve_event(self, intel):
        """Test resolving an event."""
        event = intel.record_event(
            event_type=EventType.WEATHER_DISRUPTION,
            title="Weather Event",
            description="Storm passed",
            severity=RiskLevel.HIGH,
        )

        resolved = intel.resolve_event(
            event_id=event.event_id,
            actions=["Waited for storm to pass", "Resumed operations"],
        )

        assert resolved.resolution_status == "resolved"
        assert len(resolved.resolution_actions) == 2

    def test_predict_delays(self, intel):
        """Test delay prediction."""
        prediction = intel.predict_delays("ROUTE-001")

        assert "delay_probability" in prediction
        assert "risk_factors" in prediction

    def test_predict_delays_with_events(self, intel):
        """Test prediction with active events."""
        intel.record_event(
            event_type=EventType.PORT_CONGESTION,
            title="Port Congestion",
            description="Major delays",
            severity=RiskLevel.HIGH,
            affected_routes=["ROUTE-001"],
        )

        prediction = intel.predict_delays("ROUTE-001")

        assert prediction["delay_probability"] > 0.3


# =============================================================================
# Integration Tests
# =============================================================================

class TestLogisticsIntegration:
    """Integration tests for logistics modules."""

    @pytest.mark.asyncio
    async def test_shipment_to_route_workflow(self):
        """Test shipment to route optimization workflow."""
        client_id = "test_logistics_001"

        # Create shipment
        tracker = ShipmentTracker(client_id=client_id)
        shipment = tracker.create_shipment(
            tracking_number="INT123",
            carrier="UPS",
            origin={"city": "LA", "state": "CA"},
            destination={"city": "NY", "state": "NY"},
        )

        # Track shipment
        found = tracker.track_shipment("INT123")
        assert found is not None

        # Add checkpoint
        tracker.add_checkpoint(
            shipment_id=shipment.shipment_id,
            status="in_transit",
            location="Phoenix, AZ",
            description="In transit",
        )

        assert len(shipment.checkpoints) == 2

    @pytest.mark.asyncio
    async def test_carrier_to_tracker_workflow(self):
        """Test carrier hub to tracker workflow."""
        client_id = "test_carrier_001"

        # Get rates from carrier hub
        hub = CarrierIntegrationHub(client_id=client_id)
        rates = hub.get_rates(
            origin={"city": "LA", "state": "CA", "zip": "90001"},
            destination={"city": "NY", "state": "NY", "zip": "10001"},
            weight_kg=2.0,
        )

        assert len(rates) > 0

        # Create label with cheapest rate
        cheapest = rates[0]
        label = hub.create_label(
            carrier=cheapest.carrier,
            shipment_data={},
            service_type=cheapest.service_type,
        )

        assert label.tracking_number is not None

        # Add to tracker
        tracker = ShipmentTracker(client_id=client_id)
        shipment = tracker.create_shipment(
            tracking_number=label.tracking_number,
            carrier=cheapest.carrier.value,
            origin={"city": "LA", "state": "CA"},
            destination={"city": "NY", "state": "NY"},
        )

        assert shipment.tracking_number == label.tracking_number


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
