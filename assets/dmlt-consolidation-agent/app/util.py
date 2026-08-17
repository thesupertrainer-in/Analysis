"""
Utility functions for MCP tool processing.

Provides helper functions for enhancing MCP tool descriptions and metadata.
"""
import asyncio
import hashlib
import logging
import os
import re
from typing import Any

import httpx
from langchain_core.tools import ToolException

logger = logging.getLogger(__name__)

_MCP_RETRY_ATTEMPTS = 4
_MCP_RETRY_DELAY = 4.0  # seconds
MCP_CALL_TIMEOUT_SECONDS = float(os.environ.get("MCP_CALL_TIMEOUT_SECONDS", 30.0))
MCP_MAX_RESPONSE_CHARS = int(os.environ.get("MCP_MAX_RESPONSE_CHARS", 100_000))


def _is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code < 400 or exc.response.status_code >= 500
    if isinstance(exc, (ExceptionGroup, BaseExceptionGroup)):
        return True
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    return True


def enhance_tool_description(mcp_tool: Any) -> str:
    if mcp_tool is None:
        logger.warning("enhance_tool_description called with None tool")
        return ""
    server_label = getattr(mcp_tool, "fragment_name", mcp_tool.server_name)
    return f"[{server_label}] {mcp_tool.description or ''}".strip()


def enhance_tool_name(mcp_tool: Any) -> str:
    if mcp_tool is None:
        return ""
    segments = mcp_tool.server_name.split(":")
    remaining = segments[2:] if len(segments) > 2 else segments
    raw = f"{'_'.join(remaining)}__{mcp_tool.name}"
    sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "_", raw)
    if len(sanitized) <= 64:
        return sanitized
    suffix = hashlib.sha256(sanitized.encode()).hexdigest()[:8]
    return f"{sanitized[:55]}_{suffix}"
