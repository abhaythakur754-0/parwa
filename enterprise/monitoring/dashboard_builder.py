"""
Dashboard Builder Module - Week 53, Builder 5
Dynamic dashboard creation
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class DashboardType(Enum):
    """Dashboard type"""
    OPERATIONAL = "operational"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    CUSTOM = "custom"


class LayoutType(Enum):
    """Dashboard layout type"""
    GRID = "grid"
    FLEX = "flex"
    FIXED = "fixed"


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    dashboard_id: str
    name: str
    dashboard_type: DashboardType = DashboardType.OPERATIONAL
    layout: LayoutType = LayoutType.GRID
    refresh_interval: int = 30  # seconds
    widgets: List[Dict[str, Any]] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    permissions: Dict[str, List[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "type": self.dashboard_type.value,
            "layout": self.layout.value,
            "refresh_interval": self.refresh_interval,
            "widgets": self.widgets,
            "filters": self.filters,
        }


class DashboardBuilder:
    """
    Builder for creating dynamic dashboards.
    """

    def __init__(self):
        self.dashboards: Dict[str, DashboardConfig] = {}
        self._widget_templates: Dict[str, Dict[str, Any]] = {}

    def create_dashboard(
        self,
        name: str,
        dashboard_type: DashboardType = DashboardType.OPERATIONAL,
        layout: LayoutType = LayoutType.GRID,
    ) -> DashboardConfig:
        """Create a new dashboard"""
        import uuid
        dashboard = DashboardConfig(
            dashboard_id=str(uuid.uuid4())[:8],
            name=name,
            dashboard_type=dashboard_type,
            layout=layout,
        )
        self.dashboards[dashboard.dashboard_id] = dashboard
        logger.info(f"Created dashboard: {name}")
        return dashboard

    def get_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Get a dashboard by ID"""
        return self.dashboards.get(dashboard_id)

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard"""
        if dashboard_id in self.dashboards:
            del self.dashboards[dashboard_id]
            return True
        return False

    def add_widget(
        self,
        dashboard_id: str,
        widget_type: str,
        title: str,
        position: Dict[str, int],
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a widget to a dashboard"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return None

        widget = {
            "widget_id": f"widget_{len(dashboard.widgets) + 1}",
            "type": widget_type,
            "title": title,
            "position": position,
            "config": config or {},
        }

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    def remove_widget(
        self,
        dashboard_id: str,
        widget_id: str,
    ) -> bool:
        """Remove a widget from a dashboard"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False

        for i, widget in enumerate(dashboard.widgets):
            if widget["widget_id"] == widget_id:
                dashboard.widgets.pop(i)
                dashboard.updated_at = datetime.utcnow()
                return True

        return False

    def update_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """Update a widget"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False

        for widget in dashboard.widgets:
            if widget["widget_id"] == widget_id:
                widget.update(updates)
                dashboard.updated_at = datetime.utcnow()
                return True

        return False

    def add_filter(
        self,
        dashboard_id: str,
        filter_name: str,
        filter_config: Dict[str, Any],
    ) -> bool:
        """Add a filter to a dashboard"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return False

        dashboard.filters[filter_name] = filter_config
        dashboard.updated_at = datetime.utcnow()
        return True

    def register_widget_template(
        self,
        name: str,
        template: Dict[str, Any],
    ) -> None:
        """Register a widget template"""
        self._widget_templates[name] = template

    def add_widget_from_template(
        self,
        dashboard_id: str,
        template_name: str,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a widget from a template"""
        template = self._widget_templates.get(template_name)
        if not template:
            return None

        widget = template.copy()
        if overrides:
            widget.update(overrides)

        return self.add_widget(
            dashboard_id,
            widget.get("type", "generic"),
            widget.get("title", ""),
            widget.get("position", {"x": 0, "y": 0, "w": 1, "h": 1}),
            widget.get("config", {}),
        )

    def clone_dashboard(
        self,
        dashboard_id: str,
        new_name: str,
    ) -> Optional[DashboardConfig]:
        """Clone a dashboard"""
        original = self.dashboards.get(dashboard_id)
        if not original:
            return None

        import uuid
        clone = DashboardConfig(
            dashboard_id=str(uuid.uuid4())[:8],
            name=new_name,
            dashboard_type=original.dashboard_type,
            layout=original.layout,
            refresh_interval=original.refresh_interval,
            widgets=original.widgets.copy(),
            filters=original.filters.copy(),
        )

        self.dashboards[clone.dashboard_id] = clone
        return clone

    def list_dashboards(
        self,
        dashboard_type: Optional[DashboardType] = None,
    ) -> List[DashboardConfig]:
        """List all dashboards"""
        dashboards = list(self.dashboards.values())
        if dashboard_type:
            dashboards = [
                d for d in dashboards
                if d.dashboard_type == dashboard_type
            ]
        return dashboards

    def export_dashboard(self, dashboard_id: str) -> Optional[str]:
        """Export a dashboard as JSON"""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            return None

        return json.dumps(dashboard.to_dict(), indent=2)

    def import_dashboard(self, data: str) -> Optional[DashboardConfig]:
        """Import a dashboard from JSON"""
        try:
            parsed = json.loads(data)
            dashboard = DashboardConfig(
                dashboard_id=parsed.get("dashboard_id", ""),
                name=parsed.get("name", "Imported Dashboard"),
                dashboard_type=DashboardType(parsed.get("type", "operational")),
                layout=LayoutType(parsed.get("layout", "grid")),
                refresh_interval=parsed.get("refresh_interval", 30),
                widgets=parsed.get("widgets", []),
                filters=parsed.get("filters", {}),
            )
            self.dashboards[dashboard.dashboard_id] = dashboard
            return dashboard
        except Exception as e:
            logger.error(f"Failed to import dashboard: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        return {
            "total_dashboards": len(self.dashboards),
            "by_type": {
                t.value: len([d for d in self.dashboards.values()
                             if d.dashboard_type == t])
                for t in DashboardType
            },
            "total_widgets": sum(
                len(d.widgets) for d in self.dashboards.values()
            ),
            "templates": len(self._widget_templates),
        }
