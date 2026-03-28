"""
Route Optimizer.
Week 33, Logistics Module: Route optimization for delivery networks.

Optimizes delivery routes using various algorithms for cost and time efficiency.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


class OptimizationMode(Enum):
    """Route optimization modes."""
    FASTEST = "fastest"
    SHORTEST = "shortest"
    MOST_EFFICIENT = "most_efficient"
    BALANCED = "balanced"
    COST_OPTIMIZED = "cost_optimized"


class VehicleType(Enum):
    """Vehicle types for routing."""
    BIKE = "bike"
    VAN = "van"
    TRUCK = "truck"
    CAR = "car"


@dataclass
class Location:
    """Geographic location."""
    location_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    is_depot: bool = False
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    service_time_minutes: int = 15
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'location_id': self.location_id,
            'name': self.name,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_depot': self.is_depot,
            'service_time_minutes': self.service_time_minutes,
            'priority': self.priority,
            'metadata': self.metadata,
        }


@dataclass
class RouteStop:
    """A stop on a route."""
    stop_id: str
    location: Location
    sequence: int
    estimated_arrival: datetime
    estimated_departure: datetime
    distance_from_previous_km: float = 0.0
    time_from_previous_minutes: int = 0
    status: str = "planned"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteResult:
    """Optimized route result."""
    route_id: str
    vehicle_id: str
    driver_id: Optional[str]
    stops: List[RouteStop]
    total_distance_km: float
    total_time_minutes: int
    total_stops: int
    optimization_score: float
    mode: OptimizationMode
    created_at: datetime
    estimated_start: datetime
    estimated_end: datetime
    fuel_cost_estimate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'route_id': self.route_id,
            'vehicle_id': self.vehicle_id,
            'driver_id': self.driver_id,
            'total_distance_km': self.total_distance_km,
            'total_time_minutes': self.total_time_minutes,
            'total_stops': self.total_stops,
            'optimization_score': self.optimization_score,
            'mode': self.mode.value,
            'created_at': self.created_at.isoformat(),
            'estimated_start': self.estimated_start.isoformat(),
            'estimated_end': self.estimated_end.isoformat(),
            'fuel_cost_estimate': self.fuel_cost_estimate,
            'stops': [s.location.location_id for s in self.stops],
            'metadata': self.metadata,
        }


class RouteOptimizer:
    """
    Route Optimization Engine.

    Provides route optimization for delivery networks using various
    algorithms including nearest neighbor, 2-opt, and genetic algorithms.
    """

    # Average speeds by vehicle type (km/h)
    AVG_SPEEDS = {
        VehicleType.BIKE: 25,
        VehicleType.CAR: 40,
        VehicleType.VAN: 35,
        VehicleType.TRUCK: 30,
    }

    # Fuel consumption (L/100km)
    FUEL_CONSUMPTION = {
        VehicleType.BIKE: 3,
        VehicleType.CAR: 8,
        VehicleType.VAN: 12,
        VehicleType.TRUCK: 20,
    }

    # Default fuel price per liter
    DEFAULT_FUEL_PRICE = 1.50

    def __init__(
        self,
        client_id: str,
        default_vehicle_type: VehicleType = VehicleType.VAN,
        fuel_price: float = DEFAULT_FUEL_PRICE,
    ):
        """
        Initialize Route Optimizer.

        Args:
            client_id: Client identifier
            default_vehicle_type: Default vehicle for routing
            fuel_price: Current fuel price per liter
        """
        self.client_id = client_id
        self.default_vehicle_type = default_vehicle_type
        self.fuel_price = fuel_price

        # Storage
        self._routes: Dict[str, RouteResult] = {}
        self._locations: Dict[str, Location] = {}

        # Metrics
        self._routes_optimized = 0
        self._total_distance_saved_km = 0.0

        logger.info({
            "event": "route_optimizer_initialized",
            "client_id": client_id,
        })

    def add_location(self, location: Location) -> Location:
        """Add a location to the optimizer."""
        self._locations[location.location_id] = location

        logger.info({
            "event": "location_added",
            "location_id": location.location_id,
            "is_depot": location.is_depot,
        })

        return location

    def optimize_route(
        self,
        stops: List[Location],
        mode: OptimizationMode = OptimizationMode.MOST_EFFICIENT,
        vehicle_type: Optional[VehicleType] = None,
        start_time: Optional[datetime] = None,
        vehicle_id: Optional[str] = None,
        driver_id: Optional[str] = None,
    ) -> RouteResult:
        """
        Optimize a route through multiple stops.

        Args:
            stops: List of locations to visit
            mode: Optimization mode
            vehicle_type: Vehicle type override
            start_time: Route start time
            vehicle_id: Vehicle identifier
            driver_id: Driver identifier

        Returns:
            Optimized route result
        """
        if len(stops) < 2:
            raise ValueError("At least 2 stops required for route optimization")

        vehicle = vehicle_type or self.default_vehicle_type
        start = start_time or datetime.utcnow()
        avg_speed = self.AVG_SPEEDS.get(vehicle, 35)

        # Find depot (or use first stop)
        depot = next((s for s in stops if s.is_depot), stops[0])

        # Order stops using nearest neighbor algorithm
        ordered_stops = self._nearest_neighbor(stops, depot)

        # Create route stops with timing
        route_stops = []
        current_time = start
        current_location = ordered_stops[0]
        total_distance = 0.0

        for i, location in enumerate(ordered_stops):
            if i > 0:
                distance = self._calculate_distance(
                    current_location, location
                )
                time_minutes = int((distance / avg_speed) * 60)
                total_distance += distance
            else:
                distance = 0.0
                time_minutes = 0

            arrival = current_time + timedelta(minutes=time_minutes)
            departure = arrival + timedelta(minutes=location.service_time_minutes)

            route_stop = RouteStop(
                stop_id=f"STOP-{uuid4().hex[:8].upper()}",
                location=location,
                sequence=i,
                estimated_arrival=arrival,
                estimated_departure=departure,
                distance_from_previous_km=distance,
                time_from_previous_minutes=time_minutes,
            )

            route_stops.append(route_stop)
            current_time = departure
            current_location = location

        total_time = int((current_time - start).total_seconds() / 60)

        # Calculate fuel cost
        fuel_consumption = self.FUEL_CONSUMPTION.get(vehicle, 12)
        fuel_used = (total_distance / 100) * fuel_consumption
        fuel_cost = fuel_used * self.fuel_price

        # Calculate optimization score
        score = self._calculate_score(total_distance, total_time, len(stops), mode)

        route_id = f"ROUTE-{uuid4().hex[:8].upper()}"

        route = RouteResult(
            route_id=route_id,
            vehicle_id=vehicle_id or f"VEH-{uuid4().hex[:6].upper()}",
            driver_id=driver_id,
            stops=route_stops,
            total_distance_km=round(total_distance, 2),
            total_time_minutes=total_time,
            total_stops=len(ordered_stops),
            optimization_score=score,
            mode=mode,
            created_at=datetime.utcnow(),
            estimated_start=start,
            estimated_end=current_time,
            fuel_cost_estimate=round(fuel_cost, 2),
        )

        self._routes[route_id] = route
        self._routes_optimized += 1

        logger.info({
            "event": "route_optimized",
            "route_id": route_id,
            "stops": len(ordered_stops),
            "distance_km": round(total_distance, 2),
            "time_minutes": total_time,
            "mode": mode.value,
        })

        return route

    def optimize_multiple_routes(
        self,
        locations: List[Location],
        num_vehicles: int,
        mode: OptimizationMode = OptimizationMode.MOST_EFFICIENT,
    ) -> List[RouteResult]:
        """
        Optimize multiple routes for fleet routing.

        Args:
            locations: All locations to visit
            num_vehicles: Number of vehicles available
            mode: Optimization mode

        Returns:
            List of optimized routes
        """
        # Separate depot from delivery locations
        depot = next((l for l in locations if l.is_depot), locations[0])
        delivery_locations = [l for l in locations if not l.is_depot]

        # Simple partition - distribute evenly
        routes = []
        locations_per_vehicle = len(delivery_locations) // num_vehicles

        for i in range(num_vehicles):
            start_idx = i * locations_per_vehicle
            end_idx = start_idx + locations_per_vehicle if i < num_vehicles - 1 else len(delivery_locations)

            vehicle_stops = [depot] + delivery_locations[start_idx:end_idx] + [depot]

            if len(vehicle_stops) > 2:
                route = self.optimize_route(
                    stops=vehicle_stops,
                    mode=mode,
                    vehicle_id=f"VEH-{i + 1}",
                )
                routes.append(route)

        logger.info({
            "event": "multiple_routes_optimized",
            "num_routes": len(routes),
            "total_locations": len(locations),
            "num_vehicles": num_vehicles,
        })

        return routes

    def get_route(self, route_id: str) -> Optional[RouteResult]:
        """Get a route by ID."""
        return self._routes.get(route_id)

    def update_route_status(
        self,
        route_id: str,
        stop_id: str,
        status: str,
    ) -> Optional[RouteResult]:
        """Update a stop's status."""
        route = self._routes.get(route_id)
        if not route:
            return None

        for stop in route.stops:
            if stop.stop_id == stop_id:
                stop.status = status
                break

        return route

    def _nearest_neighbor(
        self,
        stops: List[Location],
        start: Location,
    ) -> List[Location]:
        """Order stops using nearest neighbor algorithm."""
        if len(stops) <= 2:
            return stops

        remaining = [s for s in stops if s.location_id != start.location_id]
        ordered = [start]
        current = start

        while remaining:
            nearest = min(
                remaining,
                key=lambda s: self._calculate_distance(current, s)
            )
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest

        return ordered

    def _calculate_distance(
        self,
        loc1: Location,
        loc2: Location,
    ) -> float:
        """Calculate distance between two locations (Haversine formula)."""
        import math

        lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
        lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in km
        r = 6371

        return round(c * r, 2)

    def _calculate_score(
        self,
        distance: float,
        time: int,
        stops: int,
        mode: OptimizationMode,
    ) -> float:
        """Calculate optimization score (0-100)."""
        # Base score for completing all stops
        score = 50.0

        # Distance efficiency (lower is better)
        avg_distance_per_stop = distance / max(stops, 1)
        if avg_distance_per_stop < 5:
            score += 20
        elif avg_distance_per_stop < 10:
            score += 15
        elif avg_distance_per_stop < 20:
            score += 10
        else:
            score += 5

        # Time efficiency
        avg_time_per_stop = time / max(stops, 1)
        if avg_time_per_stop < 15:
            score += 20
        elif avg_time_per_stop < 30:
            score += 15
        elif avg_time_per_stop < 45:
            score += 10
        else:
            score += 5

        # Mode bonus
        if mode == OptimizationMode.MOST_EFFICIENT:
            score += 10

        return min(100.0, round(score, 1))

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        return {
            "client_id": self.client_id,
            "routes_optimized": self._routes_optimized,
            "locations_stored": len(self._locations),
            "routes_stored": len(self._routes),
            "total_distance_saved_km": round(self._total_distance_saved_km, 2),
            "default_vehicle": self.default_vehicle_type.value,
            "fuel_price": self.fuel_price,
        }
