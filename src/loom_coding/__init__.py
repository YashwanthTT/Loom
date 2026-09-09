"""Minimal loom_coding package - only tools + version for learning."""

from loom_coding.tools import (
    ImageSupportState,
    ReadOperations,
    ToolDefinition,
    create_bash_tool,
    create_bash_tool_definition,
    create_coding_tools,
    create_edit_tool,
    create_edit_tool_definition,
    create_read_tool,
    create_read_tool_definition,
    create_write_tool,
    create_write_tool_definition,
)
from loom_coding.version import current_version

__version__ = current_version()

__all__ = [
    "__version__",
    "ImageSupportState",
    "ReadOperations",
    "ToolDefinition",
    "create_bash_tool",
    "create_bash_tool_definition",
    "create_coding_tools",
    "create_edit_tool",
    "create_edit_tool_definition",
    "create_read_tool",
    "create_read_tool_definition",
    "create_write_tool",
    "create_write_tool_definition",
    "current_version",
]
