"""
Widget Library
Enterprise Analytics & Reporting - Week 44 Builder 1
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WidgetData:
    """Data result for a widget"""
    widget_id: str
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "data": self.data,
            "metadata": self.metadata,
            "error": self.error,
            "fetched_at": self.fetched_at.isoformat()
        }


class BaseWidget(ABC):
    """Base class for all widgets"""
    
    widget_type: str = "base"
    
    def __init__(
        self,
        widget_id: str,
        title: str,
        config: Optional[Dict[str, Any]] = None
    ):
        self.widget_id = widget_id
        self.title = title
        self.config = config or {}
        self._data: Optional[WidgetData] = None
    
    @abstractmethod
    async def fetch_data(self, **kwargs) -> WidgetData:
        """Fetch data for the widget"""
        pass
    
    @abstractmethod
    def render(self) -> Dict[str, Any]:
        """Render the widget for display"""
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a config value"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set a config value"""
        self.config[key] = value


class KPICardWidget(BaseWidget):
    """KPI card widget for displaying key metrics"""
    
    widget_type = "kpi_card"
    
    def __init__(
        self,
        widget_id: str,
        title: str,
        metric_name: str,
        unit: str = "",
        target: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(widget_id, title, config)
        self.metric_name = metric_name
        self.unit = unit
        self.target = target
    
    async def fetch_data(self, **kwargs) -> WidgetData:
        """Fetch KPI data"""
        # In real implementation, would query data source
        value = kwargs.get("value", 0)
        previous_value = kwargs.get("previous_value")
        
        data = {
            "value": value,
            "unit": self.unit,
            "target": self.target,
            "target_percentage": (value / self.target * 100) if self.target else None
        }
        
        if previous_value is not None:
            change = value - previous_value
            change_percentage = (change / previous_value * 100) if previous_value else 0
            data["change"] = change
            data["change_percentage"] = change_percentage
            data["trend"] = "up" if change > 0 else "down" if change < 0 else "neutral"
        
        self._data = WidgetData(
            widget_id=self.widget_id,
            data=data,
            metadata={"metric_name": self.metric_name}
        )
        
        return self._data
    
    def render(self) -> Dict[str, Any]:
        """Render KPI card"""
        return {
            "type": self.widget_type,
            "widget_id": self.widget_id,
            "title": self.title,
            "data": self._data.data if self._data else {},
            "config": {
                "unit": self.unit,
                "target": self.target,
                "format": self.get_config("format", "number"),
                "decimals": self.get_config("decimals", 0)
            }
        }


class ChartWidget(BaseWidget):
    """Base class for chart widgets"""
    
    widget_type = "chart"
    
    def __init__(
        self,
        widget_id: str,
        title: str,
        chart_type: str,
        x_axis: str,
        y_axis: List[str],
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(widget_id, title, config)
        self.chart_type = chart_type
        self.x_axis = x_axis
        self.y_axis = y_axis
    
    async def fetch_data(self, **kwargs) -> WidgetData:
        """Fetch chart data"""
        # In real implementation, would query data source
        labels = kwargs.get("labels", [])
        series = kwargs.get("series", {})
        
        data = {
            "labels": labels,
            "datasets": [
                {
                    "label": name,
                    "data": values
                }
                for name, values in series.items()
            ]
        }
        
        self._data = WidgetData(
            widget_id=self.widget_id,
            data=data,
            metadata={
                "chart_type": self.chart_type,
                "x_axis": self.x_axis,
                "y_axis": self.y_axis
            }
        )
        
        return self._data
    
    def render(self) -> Dict[str, Any]:
        """Render chart"""
        return {
            "type": self.chart_type,
            "widget_id": self.widget_id,
            "title": self.title,
            "data": self._data.data if self._data else {},
            "config": {
                "x_axis_label": self.get_config("x_axis_label", self.x_axis),
                "y_axis_label": self.get_config("y_axis_label", ", ".join(self.y_axis)),
                "legend": self.get_config("legend", True),
                "stacked": self.get_config("stacked", False),
                "colors": self.get_config("colors", [])
            }
        }


class TableWidget(BaseWidget):
    """Table widget for displaying tabular data"""
    
    widget_type = "table"
    
    def __init__(
        self,
        widget_id: str,
        title: str,
        columns: List[Dict[str, str]],
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(widget_id, title, config)
        self.columns = columns
    
    async def fetch_data(self, **kwargs) -> WidgetData:
        """Fetch table data"""
        rows = kwargs.get("rows", [])
        total_rows = kwargs.get("total_rows", len(rows))
        
        data = {
            "columns": self.columns,
            "rows": rows,
            "total_rows": total_rows,
            "page": kwargs.get("page", 1),
            "page_size": kwargs.get("page_size", 10)
        }
        
        self._data = WidgetData(
            widget_id=self.widget_id,
            data=data,
            metadata={"column_count": len(self.columns)}
        )
        
        return self._data
    
    def render(self) -> Dict[str, Any]:
        """Render table"""
        return {
            "type": self.widget_type,
            "widget_id": self.widget_id,
            "title": self.title,
            "data": self._data.data if self._data else {},
            "config": {
                "sortable": self.get_config("sortable", True),
                "filterable": self.get_config("filterable", True),
                "pagination": self.get_config("pagination", True),
                "page_size": self.get_config("page_size", 10)
            }
        }


class GaugeWidget(BaseWidget):
    """Gauge widget for displaying progress or percentage"""
    
    widget_type = "gauge"
    
    def __init__(
        self,
        widget_id: str,
        title: str,
        min_value: float = 0,
        max_value: float = 100,
        thresholds: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(widget_id, title, config)
        self.min_value = min_value
        self.max_value = max_value
        self.thresholds = thresholds or [
            {"value": 0.33, "color": "red"},
            {"value": 0.66, "color": "yellow"},
            {"value": 1.0, "color": "green"}
        ]
    
    async def fetch_data(self, **kwargs) -> WidgetData:
        """Fetch gauge data"""
        value = kwargs.get("value", 0)
        
        # Calculate percentage
        percentage = (value - self.min_value) / (self.max_value - self.min_value) * 100
        
        # Determine color based on thresholds
        color = "green"
        for threshold in sorted(self.thresholds, key=lambda x: x["value"]):
            if percentage / 100 <= threshold["value"]:
                color = threshold["color"]
                break
        
        data = {
            "value": value,
            "min": self.min_value,
            "max": self.max_value,
            "percentage": percentage,
            "color": color
        }
        
        self._data = WidgetData(
            widget_id=self.widget_id,
            data=data,
            metadata={"thresholds": self.thresholds}
        )
        
        return self._data
    
    def render(self) -> Dict[str, Any]:
        """Render gauge"""
        return {
            "type": self.widget_type,
            "widget_id": self.widget_id,
            "title": self.title,
            "data": self._data.data if self._data else {},
            "config": {
                "min": self.min_value,
                "max": self.max_value,
                "thresholds": self.thresholds,
                "unit": self.get_config("unit", "%"),
                "show_value": self.get_config("show_value", True)
            }
        }


class WidgetFactory:
    """Factory for creating widgets"""
    
    _widget_classes = {
        "kpi_card": KPICardWidget,
        "line_chart": ChartWidget,
        "bar_chart": ChartWidget,
        "pie_chart": ChartWidget,
        "table": TableWidget,
        "gauge": GaugeWidget
    }
    
    @classmethod
    def create_widget(
        cls,
        widget_type: str,
        widget_id: str,
        title: str,
        **kwargs
    ) -> Optional[BaseWidget]:
        """Create a widget by type"""
        widget_class = cls._widget_classes.get(widget_type)
        
        if not widget_class:
            logger.error(f"Unknown widget type: {widget_type}")
            return None
        
        if widget_type == "kpi_card":
            return widget_class(
                widget_id=widget_id,
                title=title,
                metric_name=kwargs.get("metric_name", ""),
                unit=kwargs.get("unit", ""),
                target=kwargs.get("target"),
                config=kwargs.get("config")
            )
        
        elif widget_type in ["line_chart", "bar_chart", "pie_chart"]:
            return widget_class(
                widget_id=widget_id,
                title=title,
                chart_type=widget_type,
                x_axis=kwargs.get("x_axis", "x"),
                y_axis=kwargs.get("y_axis", ["y"]),
                config=kwargs.get("config")
            )
        
        elif widget_type == "table":
            return widget_class(
                widget_id=widget_id,
                title=title,
                columns=kwargs.get("columns", []),
                config=kwargs.get("config")
            )
        
        elif widget_type == "gauge":
            return widget_class(
                widget_id=widget_id,
                title=title,
                min_value=kwargs.get("min_value", 0),
                max_value=kwargs.get("max_value", 100),
                thresholds=kwargs.get("thresholds"),
                config=kwargs.get("config")
            )
        
        return None
    
    @classmethod
    def register_widget(cls, widget_type: str, widget_class: type) -> None:
        """Register a new widget type"""
        cls._widget_classes[widget_type] = widget_class
    
    @classmethod
    def list_widget_types(cls) -> List[str]:
        """List available widget types"""
        return list(cls._widget_classes.keys())


class WidgetLibrary:
    """Library of pre-configured widgets"""
    
    def __init__(self):
        self._presets: Dict[str, Dict[str, Any]] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        """Register default widget presets"""
        self._presets = {
            "tickets_open": {
                "type": "kpi_card",
                "title": "Open Tickets",
                "metric_name": "open_tickets",
                "unit": "",
                "config": {"format": "number", "decimals": 0}
            },
            "avg_response_time": {
                "type": "kpi_card",
                "title": "Avg Response Time",
                "metric_name": "avg_response_time",
                "unit": "min",
                "config": {"format": "number", "decimals": 1}
            },
            "customer_satisfaction": {
                "type": "gauge",
                "title": "Customer Satisfaction",
                "min_value": 0,
                "max_value": 100,
                "config": {"unit": "%"}
            },
            "tickets_over_time": {
                "type": "line_chart",
                "title": "Tickets Over Time",
                "x_axis": "date",
                "y_axis": ["count"],
                "config": {"colors": ["#3b82f6"]}
            },
            "tickets_by_category": {
                "type": "bar_chart",
                "title": "Tickets by Category",
                "x_axis": "category",
                "y_axis": ["count"],
                "config": {"colors": ["#10b981"]}
            },
            "ticket_table": {
                "type": "table",
                "title": "Recent Tickets",
                "columns": [
                    {"field": "id", "header": "ID"},
                    {"field": "subject", "header": "Subject"},
                    {"field": "status", "header": "Status"},
                    {"field": "created_at", "header": "Created"}
                ],
                "config": {"pagination": True, "page_size": 10}
            }
        }
    
    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a widget preset by name"""
        return self._presets.get(name)
    
    def list_presets(self) -> List[str]:
        """List available presets"""
        return list(self._presets.keys())
    
    def create_from_preset(
        self,
        preset_name: str,
        widget_id: str
    ) -> Optional[BaseWidget]:
        """Create a widget from a preset"""
        preset = self._presets.get(preset_name)
        if not preset:
            return None
        
        return WidgetFactory.create_widget(
            widget_type=preset["type"],
            widget_id=widget_id,
            title=preset.get("title", ""),
            **{k: v for k, v in preset.items() if k not in ["type", "title"]}
        )
    
    def register_preset(self, name: str, config: Dict[str, Any]) -> None:
        """Register a custom preset"""
        self._presets[name] = config
