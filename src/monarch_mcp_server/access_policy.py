"""Tool access policy for read-only and scoped write modes."""

import logging
import os
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

READ_ONLY_ENV_VAR = "MONARCH_MCP_READ_ONLY"
WRITE_SCOPE_ENV_VAR = "MONARCH_MCP_WRITE_SCOPE"
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

BUDGET_MUTATING_TOOL_NAMES: tuple[str, ...] = (
    "set_budget_amount",
    "update_flexible_budget",
)

NON_BUDGET_MUTATING_TOOL_NAMES: tuple[str, ...] = (
    "refresh_accounts",
    "upload_account_balance_history",
    "create_transaction",
    "update_transaction",
    "categorize_transaction",
    "update_transaction_notes",
    "mark_transaction_reviewed",
    "bulk_categorize_transactions",
    "delete_transaction",
    "split_transaction",
    "set_transaction_tags",
    "add_transaction_tag",
    "create_transaction_tag",
    "create_transaction_category",
    "update_category",
    "update_merchant",
    "review_recurring_stream",
    "create_transaction_rule",
    "update_transaction_rule",
    "delete_transaction_rule",
)

VALID_WRITE_SCOPES = {"none", "budgets", "all"}


def _env_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def resolve_write_scope() -> str:
    """Resolve the active write scope from env vars.

    Defaults to ``none`` for safety. ``MONARCH_MCP_WRITE_SCOPE`` is preferred.
    The legacy ``MONARCH_MCP_READ_ONLY=false`` opt-out still maps to ``all`` so
    existing non-read-only deployments keep their prior behavior.
    """
    raw_scope = os.getenv(WRITE_SCOPE_ENV_VAR)
    if raw_scope is not None:
        scope = raw_scope.strip().lower()
        if scope in VALID_WRITE_SCOPES:
            return scope
        logger.warning(
            "Invalid %s=%r; defaulting Monarch MCP write scope to 'none'",
            WRITE_SCOPE_ENV_VAR,
            raw_scope,
        )
        return "none"

    legacy_read_only = _env_bool(os.getenv(READ_ONLY_ENV_VAR))
    if legacy_read_only is False:
        return "all"
    return "none"


def _remove_tools(mcp: Any, tool_names: Iterable[str]) -> list[str]:
    removed: list[str] = []
    tool_manager = mcp._tool_manager
    tools = getattr(tool_manager, "_tools", {})
    for tool_name in tool_names:
        if tool_manager.get_tool(tool_name) is not None:
            tools.pop(tool_name, None)
            removed.append(tool_name)
    return removed


def apply_tool_access_policy(mcp: Any) -> None:
    """Remove mutating tools according to the active write scope."""
    scope = resolve_write_scope()

    if scope == "all":
        logger.info("Monarch MCP write scope: all mutating tools enabled")
        return

    removed: list[str]
    if scope == "budgets":
        removed = _remove_tools(mcp, NON_BUDGET_MUTATING_TOOL_NAMES)
    else:
        removed = _remove_tools(
            mcp,
            (*BUDGET_MUTATING_TOOL_NAMES, *NON_BUDGET_MUTATING_TOOL_NAMES),
        )

    logger.info(
        "Monarch MCP write scope %r; removed mutating tools: %s",
        scope,
        ", ".join(removed) if removed else "none",
    )
