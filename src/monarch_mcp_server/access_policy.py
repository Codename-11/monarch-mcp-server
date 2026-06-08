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

REVIEW_MUTATING_TOOL_NAMES: tuple[str, ...] = (
    "create_transaction_tag_safe",
    "update_transaction_review",
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

VALID_WRITE_SCOPES = {"none", "budgets", "transactions_review", "all"}


def _parse_scope_set(raw_scope: str | None) -> set[str] | None:
    if raw_scope is None:
        return None
    scopes = {part.strip().lower() for part in raw_scope.split(",") if part.strip()}
    if not scopes:
        return {"none"}
    if "all" in scopes:
        return {"all"}
    if "none" in scopes and len(scopes) > 1:
        logger.warning(
            "Invalid %s=%r; 'none' cannot be combined with other scopes; defaulting to 'none'",
            WRITE_SCOPE_ENV_VAR,
            raw_scope,
        )
        return {"none"}
    invalid = scopes - VALID_WRITE_SCOPES
    if invalid:
        logger.warning(
            "Invalid %s=%r; unknown scope(s) %s; defaulting Monarch MCP write scope to 'none'",
            WRITE_SCOPE_ENV_VAR,
            raw_scope,
            ", ".join(sorted(invalid)),
        )
        return {"none"}
    return scopes


def _format_scope(scopes: set[str]) -> str:
    if scopes == {"all"}:
        return "all"
    if scopes == {"none"}:
        return "none"
    return ",".join(scope for scope in ("budgets", "transactions_review") if scope in scopes)


def _env_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def resolve_write_scope() -> set[str]:
    """Resolve the active write scope from env vars.

    Defaults to ``{"none"}`` for safety. ``MONARCH_MCP_WRITE_SCOPE`` is preferred
    and supports comma-separated scopes such as ``budgets,transactions_review``.
    The legacy ``MONARCH_MCP_READ_ONLY=false`` opt-out still maps to ``{"all"}``
    so existing non-read-only deployments keep their prior behavior.
    """
    parsed_scope = _parse_scope_set(os.getenv(WRITE_SCOPE_ENV_VAR))
    if parsed_scope is not None:
        return parsed_scope

    legacy_read_only = _env_bool(os.getenv(READ_ONLY_ENV_VAR))
    if legacy_read_only is False:
        return {"all"}
    return {"none"}


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
    scopes = resolve_write_scope()

    if scopes == {"all"}:
        logger.info("Monarch MCP write scope: all mutating tools enabled")
        return

    tools_to_remove: list[str] = list(NON_BUDGET_MUTATING_TOOL_NAMES)
    if "budgets" not in scopes:
        tools_to_remove.extend(BUDGET_MUTATING_TOOL_NAMES)
    if "transactions_review" not in scopes:
        tools_to_remove.extend(REVIEW_MUTATING_TOOL_NAMES)

    removed = _remove_tools(mcp, tools_to_remove)

    logger.info(
        "Monarch MCP write scope %r; removed mutating tools: %s",
        _format_scope(scopes),
        ", ".join(removed) if removed else "none",
    )
