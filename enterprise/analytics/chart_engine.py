"""
Chart Engine
Enterprise Analytics & Reporting - Week 44 Builder 5
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ChartType(str, Enum):
    """Types of charts"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    DONUT = "donut"
    AREA = "area"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    TREEMAP = "treemap"


class ColorScheme(str, Enum):
    """Color schemes"""
    DEFAULT = "default"
    SEQUENTIAL = "sequential"
    DIVERGING = "diverging"
    CATEGORICAL = "categorical"
    CUSTOM = "custom"


@dataclass
class ChartAxis:
    """Chart axis configuration"""
    label: str
    field: str
    min: Optional[float] = None
    max: Optional[float] = None
    format: Optional[str] = None  # number, date, currency, percent
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "field": self.field,
            "min": self.min,
            "max": self.max,
            "format": self.format
        }


@dataclass
class ChartSeries:
    """Chart data series"""
    name: str
    data: List[Any]
    color: Optional[str] = None
    type: Optional[ChartType] = None  # For mixed charts
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data": self.data,
            "color": self.color,
            "type": self.type.value if self.type else None
        }


@dataclass
class ChartConfig:
    """Chart configuration"""
    id: str
    title: str
    chart_type: ChartType
    x_axis: Optional[ChartAxis] = None
    y_axis: Optional[ChartAxis] = None
    series: List[ChartSeries] = field(default_factory=list)
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    colors: List[str] = field(default_factory=list)
    show_legend: bool = True
    show_grid: bool = True
    show_tooltip: bool = True
    animated: bool = True
    responsive: bool = True
    options: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "chart_type": self.chart_type.value,
            "x_axis": self.x_axis.to_dict() if self.x_axis else None,
            "y_axis": self.y_axis.to_dict() if self.y_axis else None,
            "series": [s.to_dict() for s in self.series],
            "color_scheme": self.color_scheme.value,
            "colors": self.colors,
            "show_legend": self.show_legend,
            "show_grid": self.show_grid,
            "show_tooltip": self.show_tooltip,
            "animated": self.animated,
            "responsive": self.responsive,
            "options": self.options
        }


@dataclass
class ChartData:
    """Processed chart data"""
    config_id: str
    labels: List[str]
    datasets: List[Dict[str, Any]]
    processed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "labels": self.labels,
            "datasets": self.datasets,
            "processed_at": self.processed_at.isoformat()
        }


class ChartEngine:
    """Engine for creating charts and visualizations"""
    
    DEFAULT_COLORS = [
        "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
        "#06b6d4", "#ec4899", "#14b8a6", "#f97316", "#6366f1"
    ]
    
    def __init__(self):
        self._configs: Dict[str, ChartConfig] = {}
    
    def create_chart(
        self,
        title: str,
        chart_type: ChartType,
        x_axis: Optional[ChartAxis] = None,
        y_axis: Optional[ChartAxis] = None,
        color_scheme: ColorScheme = ColorScheme.DEFAULT
    ) -> ChartConfig:
        """Create a new chart configuration"""
        import uuid
        
        config = ChartConfig(
            id=str(uuid.uuid4()),
            title=title,
            chart_type=chart_type,
            x_axis=x_axis,
            y_axis=y_axis,
            color_scheme=color_scheme
        )
        
        self._configs[config.id] = config
        return config
    
    def get_chart(self, config_id: str) -> Optional[ChartConfig]:
        """Get chart configuration by ID"""
        return self._configs.get(config_id)
    
    def add_series(
        self,
        config_id: str,
        name: str,
        data: List[Any],
        color: Optional[str] = None
    ) -> Optional[ChartSeries]:
        """Add a data series to a chart"""
        config = self._configs.get(config_id)
        if not config:
            return None
        
        series = ChartSeries(
            name=name,
            data=data,
            color=color or self.DEFAULT_COLORS[len(config.series) % len(self.DEFAULT_COLORS)]
        )
        
        config.series.append(series)
        return series
    
    def process_data(
        self,
        config_id: str,
        raw_data: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        aggregation: str = "sum"
    ) -> ChartData:
        """Process raw data into chart format"""
        config = self._configs.get(config_id)
        
        # Aggregate data
        aggregated = {}
        for item in raw_data:
            x_val = str(item.get(x_field, ""))
            y_val = item.get(y_field, 0)
            
            if x_val not in aggregated:
                aggregated[x_val] = 0
            
            if aggregation == "sum":
                aggregated[x_val] += y_val
            elif aggregation == "avg":
                aggregated[x_val] = (aggregated[x_val] + y_val) / 2
            elif aggregation == "max":
                aggregated[x_val] = max(aggregated[x_val], y_val)
            elif aggregation == "min":
                aggregated[x_val] = min(aggregated[x_val], y_val)
        
        labels = list(aggregated.keys())
        data = list(aggregated.values())
        
        return ChartData(
            config_id=config_id,
            labels=labels,
            datasets=[{
                "label": config.title if config else "Data",
                "data": data
            }]
        )
    
    def render(self, config_id: str) -> Dict[str, Any]:
        """Render chart to display format"""
        config = self._configs.get(config_id)
        if not config:
            return {"error": "Chart not found"}
        
        return {
            "type": config.chart_type.value,
            "data": {
                "labels": [],  # Would be filled with actual data
                "datasets": [s.to_dict() for s in config.series]
            },
            "options": {
                "responsive": config.responsive,
                "plugins": {
                    "title": {"display": True, "text": config.title},
                    "legend": {"display": config.show_legend}
                },
                "scales": {
                    "x": {"display": config.show_grid},
                    "y": {"display": config.show_grid}
                }
            }
        }
    
    def list_charts(self) -> List[ChartConfig]:
        """List all chart configurations"""
        return list(self._configs.values())
    
    def delete_chart(self, config_id: str) -> bool:
        """Delete a chart configuration"""
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False
    
    async def export(self, config_id: str, format: str = "json") -> Optional[str]:
        """Export chart configuration"""
        import json
        
        config = self._configs.get(config_id)
        if not config:
            return None
        
        return json.dumps(config.to_dict(), indent=2)


class VisualizationConfig:
    """Manages visualization configurations"""
    
    def __init__(self):
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._presets = self._create_presets()
    
    def _create_presets(self) -> Dict[str, Dict[str, Any]]:
        """Create visualization presets"""
        return {
            "line_trend": {
                "chart_type": "line",
                "show_grid": True,
                "animated": True,
                "fill": False,
                "tension": 0.4
            },
            "bar_comparison": {
                "chart_type": "bar",
                "show_grid": True,
                "animated": True,
                "horizontal": False
            },
            "pie_distribution": {
                "chart_type": "pie",
                "show_legend": True,
                "cutout": 0
            },
            "donut_ratio": {
                "chart_type": "donut",
                "show_legend": True,
                "cutout": 0.6
            },
            "area_trend": {
                "chart_type": "area",
                "show_grid": True,
                "fill": True,
                "opacity": 0.3
            },
            "gauge_kpi": {
                "chart_type": "gauge",
                "min": 0,
                "max": 100,
                "thresholds": [
                    {"value": 33, "color": "red"},
                    {"value": 66, "color": "yellow"},
                    {"value": 100, "color": "green"}
                ]
            }
        }
    
    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a preset configuration"""
        return self._presets.get(name)
    
    def list_presets(self) -> List[str]:
        """List available presets"""
        return list(self._presets.keys())
    
    def create_custom(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> None:
        """Create custom visualization config"""
        self._configs[name] = config
    
    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a configuration"""
        return self._configs.get(name) or self._presets.get(name)
