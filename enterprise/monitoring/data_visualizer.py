"""
Data Visualizer Module - Week 53, Builder 5
Data visualization engine
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class ChartType(Enum):
    """Chart types"""
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    COLUMN = "column"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    HEATMAP = "heatmap"


class ScaleType(Enum):
    """Scale types"""
    LINEAR = "linear"
    LOG = "log"
    TIME = "time"


@dataclass
class DataSeries:
    """Data series for visualization"""
    name: str
    values: List[Tuple[Any, float]]  # (label, value) pairs
    color: str = "#4285f4"
    visible: bool = True


@dataclass
class AxisConfig:
    """Axis configuration"""
    label: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    scale: ScaleType = ScaleType.LINEAR
    format: str = ""  # Number format


@dataclass
class ChartConfig:
    """Chart configuration"""
    chart_type: ChartType
    title: str = ""
    x_axis: AxisConfig = field(default_factory=AxisConfig)
    y_axis: AxisConfig = field(default_factory=AxisConfig)
    show_legend: bool = True
    show_grid: bool = True
    animate: bool = True
    series: List[DataSeries] = field(default_factory=list)


class DataVisualizer:
    """
    Creates visualizations from data.
    """

    def __init__(self):
        self._color_palette = [
            "#4285f4", "#34a853", "#fbbc05", "#ea4335",
            "#9c27b0", "#00bcd4", "#ff9800", "#795548",
        ]

    def create_line_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        title: str = "",
        group_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a line chart"""
        config = ChartConfig(
            chart_type=ChartType.LINE,
            title=title,
            x_axis=AxisConfig(label=x_field, scale=ScaleType.TIME),
            y_axis=AxisConfig(label=y_field),
        )

        if group_by:
            # Group data
            groups = {}
            for item in data:
                group_key = item.get(group_by, "default")
                if group_key not in groups:
                    groups[group_key] = []
                groups[group_key].append((item.get(x_field), item.get(y_field, 0)))

            # Create series
            for i, (group_name, values) in enumerate(groups.items()):
                series = DataSeries(
                    name=str(group_name),
                    values=values,
                    color=self._color_palette[i % len(self._color_palette)],
                )
                config.series.append(series)
        else:
            # Single series
            values = [(item.get(x_field), item.get(y_field, 0)) for item in data]
            config.series.append(DataSeries(name=y_field, values=values))

        return self._build_chart(config)

    def create_bar_chart(
        self,
        data: List[Dict[str, Any]],
        x_field: str,
        y_field: str,
        title: str = "",
        horizontal: bool = False,
    ) -> Dict[str, Any]:
        """Create a bar chart"""
        config = ChartConfig(
            chart_type=ChartType.BAR if horizontal else ChartType.COLUMN,
            title=title,
            x_axis=AxisConfig(label=x_field),
            y_axis=AxisConfig(label=y_field),
        )

        values = [(item.get(x_field), item.get(y_field, 0)) for item in data]
        config.series.append(DataSeries(name=y_field, values=values))

        return self._build_chart(config)

    def create_pie_chart(
        self,
        data: List[Dict[str, Any]],
        label_field: str,
        value_field: str,
        title: str = "",
        donut: bool = False,
    ) -> Dict[str, Any]:
        """Create a pie chart"""
        config = ChartConfig(
            chart_type=ChartType.DONUT if donut else ChartType.PIE,
            title=title,
        )

        values = [(item.get(label_field), item.get(value_field, 0)) for item in data]
        config.series.append(DataSeries(name=title, values=values))

        return self._build_chart(config)

    def create_gauge(
        self,
        value: float,
        min_val: float = 0,
        max_val: float = 100,
        title: str = "",
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Create a gauge visualization"""
        thresholds = thresholds or {}

        # Determine status
        status = "normal"
        color = "#4285f4"
        if "critical" in thresholds and value >= thresholds["critical"]:
            status = "critical"
            color = "#ea4335"
        elif "warning" in thresholds and value >= thresholds["warning"]:
            status = "warning"
            color = "#fbbc05"

        # Calculate percentage
        if max_val > min_val:
            percentage = (value - min_val) / (max_val - min_val) * 100
        else:
            percentage = 0

        return {
            "type": "gauge",
            "title": title,
            "value": value,
            "min": min_val,
            "max": max_val,
            "percentage": percentage,
            "status": status,
            "color": color,
            "thresholds": thresholds,
        }

    def create_heatmap(
        self,
        data: List[List[float]],
        x_labels: List[str],
        y_labels: List[str],
        title: str = "",
    ) -> Dict[str, Any]:
        """Create a heatmap visualization"""
        # Calculate color scale
        flat_values = [v for row in data for v in row]
        min_val = min(flat_values) if flat_values else 0
        max_val = max(flat_values) if flat_values else 1

        # Normalize values
        normalized = []
        for row in data:
            norm_row = []
            for v in row:
                if max_val > min_val:
                    norm = (v - min_val) / (max_val - min_val)
                else:
                    norm = 0
                norm_row.append(norm)
            normalized.append(norm_row)

        return {
            "type": "heatmap",
            "title": title,
            "data": normalized,
            "raw_data": data,
            "x_labels": x_labels,
            "y_labels": y_labels,
            "min": min_val,
            "max": max_val,
            "color_scale": ["#f7fbff", "#08306b"],
        }

    def create_table(
        self,
        data: List[Dict[str, Any]],
        columns: List[str],
        title: str = "",
        sortable: bool = True,
        pagination: bool = True,
    ) -> Dict[str, Any]:
        """Create a table visualization"""
        return {
            "type": "table",
            "title": title,
            "columns": columns,
            "rows": data,
            "sortable": sortable,
            "pagination": pagination,
            "row_count": len(data),
        }

    def _build_chart(self, config: ChartConfig) -> Dict[str, Any]:
        """Build chart from configuration"""
        chart = {
            "type": config.chart_type.value,
            "title": config.title,
            "showLegend": config.show_legend,
            "showGrid": config.show_grid,
            "animate": config.animate,
            "xAxis": {
                "label": config.x_axis.label,
                "min": config.x_axis.min,
                "max": config.x_axis.max,
                "scale": config.x_axis.scale.value,
            },
            "yAxis": {
                "label": config.y_axis.label,
                "min": config.y_axis.min,
                "max": config.y_axis.max,
                "scale": config.y_axis.scale.value,
            },
            "series": [
                {
                    "name": s.name,
                    "values": s.values,
                    "color": s.color,
                    "visible": s.visible,
                }
                for s in config.series
            ],
        }

        # Calculate y-axis range if not specified
        if config.y_axis.min is None or config.y_axis.max is None:
            all_values = [v for s in config.series for _, v in s.values]
            if all_values:
                if config.y_axis.min is None:
                    chart["yAxis"]["min"] = min(all_values) * 0.9
                if config.y_axis.max is None:
                    chart["yAxis"]["max"] = max(all_values) * 1.1

        return chart

    def calculate_statistics(
        self,
        values: List[float],
    ) -> Dict[str, float]:
        """Calculate basic statistics"""
        if not values:
            return {}

        import statistics
        sorted_values = sorted(values)

        return {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "p50": self._percentile(sorted_values, 50),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99),
        }

    def _percentile(self, sorted_values: List[float], p: float) -> float:
        """Calculate percentile"""
        if not sorted_values:
            return 0
        idx = (p / 100) * (len(sorted_values) - 1)
        lower = int(idx)
        upper = lower + 1
        if upper >= len(sorted_values):
            return sorted_values[-1]
        weight = idx - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    def format_value(
        self,
        value: float,
        format_type: str = "number",
        decimals: int = 2,
    ) -> str:
        """Format a value for display"""
        if format_type == "number":
            if abs(value) >= 1e9:
                return f"{value/1e9:.{decimals}f}B"
            elif abs(value) >= 1e6:
                return f"{value/1e6:.{decimals}f}M"
            elif abs(value) >= 1e3:
                return f"{value/1e3:.{decimals}f}K"
            return f"{value:.{decimals}f}"

        elif format_type == "percent":
            return f"{value:.{decimals}f}%"

        elif format_type == "currency":
            return f"${value:,.{decimals}f}"

        elif format_type == "duration":
            if value < 1000:
                return f"{value:.{decimals}f}ms"
            elif value < 60000:
                return f"{value/1000:.{decimals}f}s"
            elif value < 3600000:
                return f"{value/60000:.{decimals}f}m"
            return f"{value/3600000:.{decimals}f}h"

        return str(value)
