"""Tests for Monarch MCP tool access policy."""

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

BUDGET_MUTATING_TOOL_NAMES = {
    "set_budget_amount",
    "update_flexible_budget",
}

NON_BUDGET_MUTATING_TOOL_NAMES = {
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
}

READ_TOOL_NAMES = {
    "setup_authentication",
    "check_auth_status",
    "debug_session_loading",
    "get_accounts",
    "get_transactions",
    "search_transactions",
    "get_transaction_details",
    "get_transactions_needing_review",
    "get_recurring_transactions",
    "get_budgets",
    "get_cashflow",
    "get_account_holdings",
    "get_transaction_categories",
    "get_transaction_category_groups",
    "get_transaction_tags",
    "get_cashflow_by_month",
    "get_net_worth",
    "get_net_worth_by_account_type",
    "get_spending_summary",
    "get_transactions_summary",
    "get_merchant",
    "get_transaction_rules",
    "get_transaction_splits",
}


def _server_env(write_scope: str | None = None, legacy_read_only: bool | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MONARCH_MCP_READ_ONLY", None)
    env.pop("MONARCH_MCP_WRITE_SCOPE", None)
    if write_scope is not None:
        env["MONARCH_MCP_WRITE_SCOPE"] = write_scope
    if legacy_read_only is not None:
        env["MONARCH_MCP_READ_ONLY"] = "true" if legacy_read_only else "0"
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _list_tools(write_scope: str | None = None, legacy_read_only: bool | None = None) -> set[str]:
    code = """
import asyncio
import json
from monarch_mcp_server.server import mcp

async def main():
    tools = await mcp.list_tools()
    print(json.dumps(sorted(tool.name for tool in tools)))

asyncio.run(main())
"""
    output = subprocess.check_output(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        env=_server_env(write_scope=write_scope, legacy_read_only=legacy_read_only),
        text=True,
    )
    return set(json.loads(output))


def test_default_scope_excludes_all_mutating_tools():
    tool_names = _list_tools()

    assert (BUDGET_MUTATING_TOOL_NAMES | NON_BUDGET_MUTATING_TOOL_NAMES).isdisjoint(tool_names)
    assert READ_TOOL_NAMES <= tool_names


def test_legacy_read_only_false_allows_all_mutating_tools():
    tool_names = _list_tools(legacy_read_only=False)

    assert BUDGET_MUTATING_TOOL_NAMES <= tool_names
    assert NON_BUDGET_MUTATING_TOOL_NAMES <= tool_names
    assert READ_TOOL_NAMES <= tool_names


def test_write_scope_budgets_exposes_only_budget_mutators():
    tool_names = _list_tools(write_scope="budgets")

    assert BUDGET_MUTATING_TOOL_NAMES <= tool_names
    assert NON_BUDGET_MUTATING_TOOL_NAMES.isdisjoint(tool_names)
    assert READ_TOOL_NAMES <= tool_names


def test_write_scope_all_exposes_all_mutating_tools():
    tool_names = _list_tools(write_scope="all")

    assert BUDGET_MUTATING_TOOL_NAMES <= tool_names
    assert NON_BUDGET_MUTATING_TOOL_NAMES <= tool_names
    assert READ_TOOL_NAMES <= tool_names


def test_default_scope_mutating_tools_are_not_callable():
    code = """
import asyncio
from monarch_mcp_server.server import mcp

async def main():
    try:
        await mcp.call_tool("create_transaction", {"date": "2026-01-01"})
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
        return

    raise AssertionError("create_transaction was callable in default no-write scope")

asyncio.run(main())
"""
    output = subprocess.check_output(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        env=_server_env(),
        text=True,
    )

    assert "ToolError: Unknown tool: create_transaction" in output
