"""
MCP tool loader stub.

This agent does not use external MCP tools — it uses its own deterministic
calculation tools and AI analysis tools instead.

The reset_user_token / set_user_token / get_user_token functions are provided
for compatibility with the A2A framework middleware.
"""
from contextvars import ContextVar, Token
from typing import Optional

_user_token_context: ContextVar[str | None] = ContextVar('user_token', default=None)


async def get_mcp_tools(user_token: str | None = None) -> list:
    """Return empty list — this agent has no external MCP tools."""
    return []


def set_user_token(user_token: str | None) -> Token:
    return _user_token_context.set(user_token)


def reset_user_token(token: Token) -> None:
    _user_token_context.reset(token)


def get_user_token() -> str | None:
    return _user_token_context.get()
