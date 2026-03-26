"""
PARWA Grafana Dashboards Module.

This module provides Grafana dashboard JSON configurations for
monitoring the PARWA system across all variants and services.

Dashboards:
- main-dashboard.json: System overview with request rate, error rate, latency
- mcp-dashboard.json: MCP server metrics (all 11 servers)
- compliance-dashboard.json: GDPR, HIPAA, and compliance metrics
- sla-dashboard.json: SLA breach tracking and response times
- quality.json: Quality Coach scoring and trends

All dashboards use Prometheus as the datasource and follow
Grafana dashboard schema conventions.
"""
from typing import Dict, Any, List
import json
from pathlib import Path

# Dashboard directory path
DASHBOARD_DIR = Path(__file__).parent

# Dashboard file names
DASHBOARD_FILES = {
    "main": "main-dashboard.json",
    "mcp": "mcp-dashboard.json",
    "compliance": "compliance-dashboard.json",
    "sla": "sla-dashboard.json",
    "quality": "quality.json",
}


def load_dashboard(name: str) -> Dict[str, Any]:
    """
    Load a dashboard JSON by name.

    Args:
        name: Dashboard name (main, mcp, compliance, sla, quality)

    Returns:
        Dict with dashboard configuration

    Raises:
        ValueError: If dashboard name is invalid
        FileNotFoundError: If dashboard file doesn't exist
    """
    if name not in DASHBOARD_FILES:
        raise ValueError(
            f"Invalid dashboard name: {name}. "
            f"Valid names: {list(DASHBOARD_FILES.keys())}"
        )

    dashboard_path = DASHBOARD_DIR / DASHBOARD_FILES[name]

    if not dashboard_path.exists():
        raise FileNotFoundError(f"Dashboard file not found: {dashboard_path}")

    with open(dashboard_path, "r") as f:
        return json.load(f)


def get_all_dashboards() -> Dict[str, Dict[str, Any]]:
    """
    Load all dashboards.

    Returns:
        Dict mapping dashboard name to configuration
    """
    dashboards = {}
    for name in DASHBOARD_FILES:
        try:
            dashboards[name] = load_dashboard(name)
        except FileNotFoundError:
            continue
    return dashboards


def validate_dashboard(dashboard: Dict[str, Any]) -> bool:
    """
    Validate a dashboard configuration.

    Args:
        dashboard: Dashboard configuration dict

    Returns:
        True if valid, raises ValueError otherwise

    Raises:
        ValueError: If dashboard is invalid
    """
    required_fields = ["dashboard", "overwrite"]

    for field in required_fields:
        if field not in dashboard:
            raise ValueError(f"Missing required field: {field}")

    dash_obj = dashboard.get("dashboard", {})

    required_dash_fields = ["title", "panels", "uid"]
    for field in required_dash_fields:
        if field not in dash_obj:
            raise ValueError(f"Missing required dashboard field: {field}")

    # Validate panels
    panels = dash_obj.get("panels", [])
    if not isinstance(panels, list):
        raise ValueError("Panels must be a list")

    if len(panels) == 0:
        raise ValueError("Dashboard must have at least one panel")

    return True


def get_dashboard_panels(dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all panels from a dashboard.

    Args:
        dashboard: Dashboard configuration dict

    Returns:
        List of panel configurations
    """
    return dashboard.get("dashboard", {}).get("panels", [])


def get_datasource(dashboard: Dict[str, Any]) -> str:
    """
    Get the datasource name from a dashboard.

    Args:
        dashboard: Dashboard configuration dict

    Returns:
        Datasource name (default: "Prometheus")
    """
    panels = get_dashboard_panels(dashboard)
    if panels:
        return panels[0].get("datasource", {}).get("uid", "Prometheus")
    return "Prometheus"


__all__ = [
    "DASHBOARD_DIR",
    "DASHBOARD_FILES",
    "load_dashboard",
    "get_all_dashboards",
    "validate_dashboard",
    "get_dashboard_panels",
    "get_datasource",
]
