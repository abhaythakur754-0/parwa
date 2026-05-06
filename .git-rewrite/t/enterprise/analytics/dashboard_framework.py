"""
Dashboard Framework
Enterprise Analytics & Reporting - Week 44 Builder 1
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type
import json
import uuid
import logging

logger = logging.getLogger(__name__)


class DashboardStatus(str, Enum):
    """Dashboard status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class WidgetType(str, Enum):
    """Types of dashboard widgets"""
    KPI_CARD = "kpi_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    GAUGE = "gauge"
    MAP = "map"
    HEATMAP = "heatmap"
    TREND = "trend"
    COUNTER = "counter"


class LayoutType(str, Enum):
    """Dashboard layout types"""
    GRID = "grid"
    FLEX = "flex"
    FREEFORM = "freeform"


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget"""
    widget_id: str
    widget_type: WidgetType
    title: str
    position: Dict[str, int]  # x, y, width, height
    data_source: Optional[str] = None
    query: Optional[str] = None
    refresh_interval: int = 300  # seconds
    filters: Dict[str, Any] = field(default_factory=dict)
    styling: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type.value,
            "title": self.title,
            "position": self.position,
            "data_source": self.data_source,
            "query": self.query,
            "refresh_interval": self.refresh_interval,
            "filters": self.filters,
            "styling": self.styling
        }


@dataclass
class DashboardConfig:
    """Configuration for a dashboard"""
    id: str
    name: str
    description: str = ""
    layout_type: LayoutType = LayoutType.GRID
    columns: int = 12
    row_height: int = 100
    widgets: List[WidgetConfig] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    theme: str = "light"
    status: DashboardStatus = DashboardStatus.DRAFT
    owner_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    shared_with: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "layout_type": self.layout_type.value,
            "columns": self.columns,
            "row_height": self.row_height,
            "widgets": [w.to_dict() for w in self.widgets],
            "filters": self.filters,
            "theme": self.theme,
            "status": self.status.value,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "shared_with": self.shared_with
        }
    
    def add_widget(self, widget: WidgetConfig) -> None:
        """Add a widget to the dashboard"""
        self.widgets.append(widget)
        self.updated_at = datetime.utcnow()
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove a widget from the dashboard"""
        for i, w in enumerate(self.widgets):
            if w.widget_id == widget_id:
                self.widgets.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def get_widget(self, widget_id: str) -> Optional[WidgetConfig]:
        """Get a widget by ID"""
        for w in self.widgets:
            if w.widget_id == widget_id:
                return w
        return None


class DashboardManager:
    """Manages dashboard creation, storage, and retrieval"""
    
    def __init__(self):
        self._dashboards: Dict[str, DashboardConfig] = {}
        self._templates: Dict[str, DashboardConfig] = {}
    
    def create_dashboard(
        self,
        name: str,
        description: str = "",
        layout_type: LayoutType = LayoutType.GRID,
        owner_id: Optional[str] = None,
        columns: int = 12,
        row_height: int = 100
    ) -> DashboardConfig:
        """Create a new dashboard"""
        dashboard_id = str(uuid.uuid4())
        
        dashboard = DashboardConfig(
            id=dashboard_id,
            name=name,
            description=description,
            layout_type=layout_type,
            columns=columns,
            row_height=row_height,
            owner_id=owner_id
        )
        
        self._dashboards[dashboard_id] = dashboard
        logger.info(f"Created dashboard: {name} ({dashboard_id})")
        
        return dashboard
    
    def get_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Get a dashboard by ID"""
        return self._dashboards.get(dashboard_id)
    
    def list_dashboards(
        self,
        owner_id: Optional[str] = None,
        status: Optional[DashboardStatus] = None
    ) -> List[DashboardConfig]:
        """List dashboards with optional filtering"""
        dashboards = list(self._dashboards.values())
        
        if owner_id:
            dashboards = [d for d in dashboards if d.owner_id == owner_id or owner_id in d.shared_with]
        
        if status:
            dashboards = [d for d in dashboards if d.status == status]
        
        return dashboards
    
    def update_dashboard(
        self,
        dashboard_id: str,
        **kwargs
    ) -> Optional[DashboardConfig]:
        """Update dashboard properties"""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        for key, value in kwargs.items():
            if hasattr(dashboard, key) and key != "id":
                setattr(dashboard, key, value)
        
        dashboard.updated_at = datetime.utcnow()
        return dashboard
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard"""
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
        return False
    
    def publish_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Publish a dashboard"""
        return self.update_dashboard(dashboard_id, status=DashboardStatus.PUBLISHED)
    
    def archive_dashboard(self, dashboard_id: str) -> Optional[DashboardConfig]:
        """Archive a dashboard"""
        return self.update_dashboard(dashboard_id, status=DashboardStatus.ARCHIVED)
    
    def share_dashboard(
        self,
        dashboard_id: str,
        user_ids: List[str]
    ) -> Optional[DashboardConfig]:
        """Share dashboard with users"""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        for user_id in user_ids:
            if user_id not in dashboard.shared_with:
                dashboard.shared_with.append(user_id)
        
        dashboard.updated_at = datetime.utcnow()
        return dashboard
    
    def unshare_dashboard(
        self,
        dashboard_id: str,
        user_ids: List[str]
    ) -> Optional[DashboardConfig]:
        """Remove sharing from users"""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        dashboard.shared_with = [
            uid for uid in dashboard.shared_with 
            if uid not in user_ids
        ]
        
        dashboard.updated_at = datetime.utcnow()
        return dashboard
    
    def duplicate_dashboard(
        self,
        dashboard_id: str,
        new_name: str
    ) -> Optional[DashboardConfig]:
        """Create a copy of a dashboard"""
        original = self._dashboards.get(dashboard_id)
        if not original:
            return None
        
        new_dashboard = self.create_dashboard(
            name=new_name,
            description=original.description,
            layout_type=original.layout_type,
            owner_id=original.owner_id,
            columns=original.columns,
            row_height=original.row_height
        )
        
        # Copy widgets
        for widget in original.widgets:
            new_widget = WidgetConfig(
                widget_id=str(uuid.uuid4()),
                widget_type=widget.widget_type,
                title=widget.title,
                position=widget.position.copy(),
                data_source=widget.data_source,
                query=widget.query,
                refresh_interval=widget.refresh_interval,
                filters=widget.filters.copy(),
                styling=widget.styling.copy()
            )
            new_dashboard.widgets.append(new_widget)
        
        return new_dashboard
    
    def save_as_template(
        self,
        dashboard_id: str,
        template_name: str
    ) -> Optional[DashboardConfig]:
        """Save dashboard as a template"""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        template = DashboardConfig(
            id=f"template_{str(uuid.uuid4())}",
            name=template_name,
            description=dashboard.description,
            layout_type=dashboard.layout_type,
            columns=dashboard.columns,
            row_height=dashboard.row_height,
            widgets=dashboard.widgets.copy()
        )
        
        self._templates[template.id] = template
        logger.info(f"Created template: {template_name}")
        
        return template
    
    def create_from_template(
        self,
        template_id: str,
        name: str,
        owner_id: Optional[str] = None
    ) -> Optional[DashboardConfig]:
        """Create dashboard from template"""
        template = self._templates.get(template_id)
        if not template:
            return None
        
        dashboard = self.create_dashboard(
            name=name,
            description=template.description,
            layout_type=template.layout_type,
            owner_id=owner_id,
            columns=template.columns,
            row_height=template.row_height
        )
        
        # Copy widgets from template
        for widget in template.widgets:
            new_widget = WidgetConfig(
                widget_id=str(uuid.uuid4()),
                widget_type=widget.widget_type,
                title=widget.title,
                position=widget.position.copy(),
                data_source=widget.data_source,
                query=widget.query,
                refresh_interval=widget.refresh_interval,
                filters=widget.filters.copy(),
                styling=widget.styling.copy()
            )
            dashboard.widgets.append(new_widget)
        
        return dashboard
    
    def list_templates(self) -> List[DashboardConfig]:
        """List available templates"""
        return list(self._templates.values())
    
    def export_dashboard(self, dashboard_id: str) -> Optional[str]:
        """Export dashboard as JSON"""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None
        
        return json.dumps(dashboard.to_dict(), indent=2)
    
    def import_dashboard(
        self,
        json_data: str,
        owner_id: Optional[str] = None
    ) -> Optional[DashboardConfig]:
        """Import dashboard from JSON"""
        try:
            data = json.loads(json_data)
            
            dashboard = self.create_dashboard(
                name=data.get("name", "Imported Dashboard"),
                description=data.get("description", ""),
                layout_type=LayoutType(data.get("layout_type", "grid")),
                owner_id=owner_id,
                columns=data.get("columns", 12),
                row_height=data.get("row_height", 100)
            )
            
            # Import widgets
            for w in data.get("widgets", []):
                widget = WidgetConfig(
                    widget_id=str(uuid.uuid4()),
                    widget_type=WidgetType(w.get("widget_type", "kpi_card")),
                    title=w.get("title", ""),
                    position=w.get("position", {"x": 0, "y": 0, "width": 4, "height": 2}),
                    data_source=w.get("data_source"),
                    query=w.get("query"),
                    refresh_interval=w.get("refresh_interval", 300),
                    filters=w.get("filters", {}),
                    styling=w.get("styling", {})
                )
                dashboard.widgets.append(widget)
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Dashboard import error: {e}")
            return None
