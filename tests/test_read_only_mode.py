"""Tests for Monarch MCP read-only mode."""

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

MUTATING_TOOL_NAMES = {
    "create_transaction",
    "update_transaction",
    "create_transaction_category",
    "create_transaction_tag",
    "set_transaction_tags",
    "add_transaction_tag",
    "categorize_transaction",
    "refresh_accounts",
}

READ_TOOL_NAMES = {
    "setup_authentication",
    "check_auth_status",
    "debug_session_loading",
    "get_accounts",
    "get_transactions",
    "get_budgets",
    "get_cashflow",
    "get_account_holdings",
    "get_transaction_categories",
    "get_transaction_category_groups",
    "get_transaction_tags",
}


def _server_env(read_only: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["MONARCH_MCP_READ_ONLY"] = "true" if read_only else "0"
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _list_tools(read_only: bool) -> set[str]:
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
        env=_server_env(read_only),
        text=True,
    )
    return set(json.loads(output))


def test_default_mode_includes_mutating_tools():
    tool_names = _list_tools(read_only=False)

    assert MUTATING_TOOL_NAMES <= tool_names
    assert READ_TOOL_NAMES <= tool_names


def test_read_only_mode_excludes_mutating_tools():
    tool_names = _list_tools(read_only=True)

    assert MUTATING_TOOL_NAMES.isdisjoint(tool_names)
    assert READ_TOOL_NAMES <= tool_names


def test_read_only_mode_mutating_tools_are_not_callable():
    code = """
import asyncio
from monarch_mcp_server.server import mcp

async def main():
    try:
        await mcp.call_tool(
            "create_transaction",
            {
                "date": "2026-01-01",
                "account_id": "acc-1",
                "amount": 1.0,
                "merchant_name": "Test",
                "category_id": "cat-1",
            },
        )
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
        return

    raise AssertionError("create_transaction was callable in read-only mode")

asyncio.run(main())
"""
    output = subprocess.check_output(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        env=_server_env(read_only=True),
        text=True,
    )

    assert "ToolError: Unknown tool: create_transaction" in output
