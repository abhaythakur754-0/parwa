"""Compatibility shim.

Many react-tool modules use ``from .base import ...``. The canonical
implementations live in ``base_tool.py``. This shim re-exports them so the
existing import statements resolve without modifying every file.
"""
from .base_tool import (  # noqa: F401
    ActionSchema,
    BaseReactTool,
    ToolCall,
    ToolResult,
    ToolSchema,
    ValidationResult,
)
