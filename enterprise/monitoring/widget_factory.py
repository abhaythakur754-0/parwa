"""
Widget Factory Module - Week 53, Builder 5
Dashboard widget factory
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class WidgetType(Enum):
    """Widget types"""
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    GAUGE = "gauge"
    COUNTER = "counter"
    TABLE = "table"
    LIST = "list"
    HEATMAP = "heatmap"
    MAP = "map"
    STATUS = "status"
    TIMELINE = "timeline"
    LOG_VIEWER = "log_viewer"
    ALERT_LIST = "alert_list"


@dataclass
class WidgetDefinition:
    """Widget definition"""
    type: WidgetType
    title: str
    description: str = ""
    default_config: Dict[str, Any] = field(default_factory=dict)
    data_source: str = ""
    refresh_interval: int = 30
    min_width: int = 1
    min_height: int = 1
    max_width: int = 12
    max_height: int = 12


class WidgetFactory:
    """
    Factory for creating dashboard widgets.
    """

    def __init__(self):
        self._definitions: Dict[WidgetType, WidgetDefinition] = {}
        self._data_providers: Dict[str, Callable] = {}
        self._setup_default_widgets()

    def _setup_default_widgets(self) -> None:
        """Setup default widget definitions"""
        # Charts
        self.register_definition(WidgetDefinition(
            type=WidgetType.LINE_CHART,
            title="Line Chart",
            description="Time series line chart",
            default_config={
                "show_legend": True,
                "show_grid": True,
                "line_width": 2,
            },
            min_width=2,
            min_height=2,
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.BAR_CHART,
            title="Bar Chart",
            description="Vertical or horizontal bar chart",
            default_config={
                "orientation": "vertical",
                "show_values": True,
            },
            min_width=2,
            min_height=2,
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.PIE_CHART,
            title="Pie Chart",
            description="Circular pie chart",
            default_config={
                "show_percentages": True,
                "show_legend": True,
            },
            min_width=2,
            min_height=2,
        ))

        # Indicators
        self.register_definition(WidgetDefinition(
            type=WidgetType.GAUGE,
            title="Gauge",
            description="Single value gauge indicator",
            default_config={
                "min": 0,
                "max": 100,
                "thresholds": {"warning": 70, "critical": 90},
            },
            min_width=1,
            min_height=1,
            max_width=4,
            max_height=4,
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.COUNTER,
            title="Counter",
            description="Single value counter with trend",
            default_config={
                "show_trend": True,
                "format": "number",
            },
            min_width=1,
            min_height=1,
            max_width=3,
            max_height=2,
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.STATUS,
            title="Status",
            description="Status indicator with color coding",
            default_config={
                "states": {
                    "healthy": {"color": "green", "icon": "check"},
                    "warning": {"color": "yellow", "icon": "warning"},
                    "critical": {"color": "red", "icon": "error"},
                },
            },
            min_width=1,
            min_height=1,
        ))

        # Data displays
        self.register_definition(WidgetDefinition(
            type=WidgetType.TABLE,
            title="Table",
            description="Data table with sorting and filtering",
            default_config={
                "sortable": True,
                "filterable": True,
                "pagination": True,
                "page_size": 10,
            },
            min_width=3,
            min_height=2,
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.LIST,
            title="List",
            description="Scrollable list display",
            default_config={
                "max_items": 10,
                "show_timestamp": True,
            },
            min_width=2,
            min_height=2,
        ))

        # Special widgets
        self.register_definition(WidgetDefinition(
            type=WidgetType.ALERT_LIST,
            title="Alert List",
            description="Active alerts widget",
            default_config={
                "show_severity": True,
                "show_source": True,
                "max_alerts": 10,
            },
            min_width=3,
            min_height=3,
            data_source="alerts",
        ))

        self.register_definition(WidgetDefinition(
            type=WidgetType.LOG_VIEWER,
            title="Log Viewer",
            description="Real-time log viewer",
            default_config={
                "max_lines": 100,
                "auto_scroll": True,
                "highlight_patterns": [],
            },
            min_width=4,
            min_height=3,
            data_source="logs",
        ))

    def register_definition(self, definition: WidgetDefinition) -> None:
        """Register a widget definition"""
        self._definitions[definition.type] = definition

    def create_widget(
        self,
        widget_type: WidgetType,
        title: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a widget from definition"""
        definition = self._definitions.get(widget_type)
        if not definition:
            return None

        widget = {
            "widget_id": f"{widget_type.value}_{datetime.utcnow().timestamp():.0f}",
            "type": widget_type.value,
            "title": title or definition.title,
            "config": {**definition.default_config, **(config or {})},
            "position": position or {"x": 0, "y": 0, "w": definition.min_width, "h": definition.min_height},
            "refresh_interval": definition.refresh_interval,
            "data_source": definition.data_source,
        }

        return widget

    def get_definition(self, widget_type: WidgetType) -> Optional[WidgetDefinition]:
        """Get a widget definition"""
        return self._definitions.get(widget_type)

    def list_definitions(self) -> List[WidgetDefinition]:
        """List all widget definitions"""
        return list(self._definitions.values())

    def register_data_provider(
        self,
        name: str,
        provider: Callable,
    ) -> None:
        """Register a data provider"""
        self._data_providers[name] = provider

    def get_widget_data(
        self,
        data_source: str,
        config: Dict[str, Any],
    ) -> Optional[Any]:
        """Get data for a widget"""
        provider = self._data_providers.get(data_source)
        if provider:
            try:
                return provider(config)
            except Exception as e:
                logger.error(f"Data provider error: {e}")
        return None

    def validate_widget(self, widget: Dict[str, Any]) -> List[str]:
        """Validate a widget configuration"""
        errors = []

        widget_type = WidgetType(widget.get("type", ""))
        definition = self._definitions.get(widget_type)

        if not definition:
            errors.append(f"Unknown widget type: {widget.get('type')}")
            return errors

        # Validate position
        position = widget.get("position", {})
        width = position.get("w", 1)
        height = position.get("h", 1)

        if width < definition.min_width:
            errors.append(f"Width {width} below minimum {definition.min_width}")
        if width > definition.max_width:
            errors.append(f"Width {width} above maximum {definition.max_width}")
        if height < definition.min_height:
            errors.append(f"Height {height} below minimum {definition.min_height}")
        if height > definition.max_height:
            errors.append(f"Height {height} above maximum {definition.max_height}")

        return errors
