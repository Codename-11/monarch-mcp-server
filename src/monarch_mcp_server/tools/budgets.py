"""Budget tools."""

import logging
from typing import Any, Dict, Optional

from monarch_mcp_server.app import mcp
from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.helpers import json_success, json_error

logger = logging.getLogger(__name__)


@mcp.tool()
async def get_budgets(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Get budget information from Monarch Money.

    Args:
        start_date: Start date in YYYY-MM-DD format (defaults to last month)
        end_date: End date in YYYY-MM-DD format (defaults to next month)

    Returns:
        List of budgets with amounts, spent, and remaining for each category.
    """
    try:
        client = await get_monarch_client()
        budgets = await client.get_budgets(start_date=start_date, end_date=end_date)
        return json_success(budgets)
    except Exception as e:
        return json_error("get_budgets", e)


def _planned_amount(monthly_amount: Dict[str, Any]) -> Optional[float]:
    for key in ("plannedCashFlowAmount", "plannedAmount", "budgetAmount"):
        value = monthly_amount.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _find_monthly_amount(
    monthly_amounts: list[Dict[str, Any]], start_date: Optional[str]
) -> Dict[str, Any] | None:
    if not monthly_amounts:
        return None
    if start_date:
        for monthly_amount in monthly_amounts:
            if monthly_amount.get("month") == start_date:
                return monthly_amount
    return monthly_amounts[0]


def _find_current_budget_amount(
    budgets: Dict[str, Any],
    *,
    category_id: Optional[str] = None,
    category_group_id: Optional[str] = None,
    start_date: Optional[str] = None,
) -> Optional[float]:
    budget_data = budgets.get("budgetData") or {}

    if category_id:
        rows = budget_data.get("monthlyAmountsByCategory") or []
        target_key = "category"
        target_id = category_id
    else:
        rows = budget_data.get("monthlyAmountsByCategoryGroup") or []
        target_key = "categoryGroup"
        target_id = category_group_id

    for row in rows:
        target = row.get(target_key) or {}
        if target.get("id") != target_id:
            continue
        monthly_amount = _find_monthly_amount(row.get("monthlyAmounts") or [], start_date)
        return _planned_amount(monthly_amount or {})

    return None


def _find_current_flexible_budget_amount(
    budgets: Dict[str, Any], start_date: Optional[str] = None
) -> Optional[float]:
    budget_data = budgets.get("budgetData") or {}
    flex_data = budget_data.get("monthlyAmountsForFlexExpense") or {}
    monthly_amount = _find_monthly_amount(flex_data.get("monthlyAmounts") or [], start_date)
    return _planned_amount(monthly_amount or {})


def _dry_run_response(
    *,
    target: Dict[str, str],
    current_amount: Optional[float],
    proposed_amount: float,
    start_date: Optional[str],
    apply_to_future: bool,
) -> str:
    delta = None if current_amount is None else proposed_amount - current_amount
    return json_success(
        {
            "success": True,
            "dry_run": True,
            "target": target,
            "start_date": start_date,
            "apply_to_future": apply_to_future,
            "current_amount": current_amount,
            "proposed_amount": proposed_amount,
            "delta": delta,
            "message": "Dry run only; call again with dry_run=false to apply.",
        }
    )


@mcp.tool()
async def set_budget_amount(
    amount: float,
    category_id: Optional[str] = None,
    category_group_id: Optional[str] = None,
    start_date: Optional[str] = None,
    apply_to_future: bool = False,
    dry_run: bool = True,
) -> str:
    """
    Set or update a budget amount for a category or category group.

    Use get_budgets() first to see current budgets and category IDs.
    Use get_categories() or get_category_groups() to find category/group IDs.

    Args:
        amount: The budget amount to set. Use 0 to clear/unset the budget.
        category_id: The ID of the category to budget (cannot use with category_group_id)
        category_group_id: The ID of the category group to budget (cannot use with category_id)
        start_date: The month to set budget for in YYYY-MM-DD format (defaults to current month)
        apply_to_future: Whether to apply this amount to all future months (default: False)
        dry_run: If True, return current/proposed values without mutating (default: True)

    Returns:
        Result of the budget update, or a dry-run diff.
    """
    try:
        if category_id and category_group_id:
            return json_success(
                {
                    "success": False,
                    "error": "Cannot specify both category_id and category_group_id. Choose one.",
                }
            )

        if not category_id and not category_group_id:
            return json_success(
                {
                    "success": False,
                    "error": "Must specify either category_id or category_group_id.",
                }
            )

        client = await get_monarch_client()

        if dry_run:
            budgets = await client.get_budgets(start_date=start_date, end_date=start_date)
            current_amount = _find_current_budget_amount(
                budgets,
                category_id=category_id,
                category_group_id=category_group_id,
                start_date=start_date,
            )
            target = (
                {"type": "category", "id": category_id}
                if category_id
                else {"type": "category_group", "id": category_group_id or ""}
            )
            return _dry_run_response(
                target=target,
                current_amount=current_amount,
                proposed_amount=float(amount),
                start_date=start_date,
                apply_to_future=apply_to_future,
            )

        params: Dict[str, Any] = {
            "amount": amount,
            "apply_to_future": apply_to_future,
        }

        if category_id:
            params["category_id"] = category_id
        if category_group_id:
            params["category_group_id"] = category_group_id
        if start_date:
            params["start_date"] = start_date

        result = await client.set_budget_amount(**params)

        return json_success(
            {
                "success": True,
                "dry_run": False,
                "message": f"Budget set to ${amount:.2f}"
                + (" for all future months" if apply_to_future else ""),
                "result": result,
            }
        )
    except Exception as e:
        return json_error("set_budget_amount", e)


@mcp.tool()
async def update_flexible_budget(
    amount: float,
    start_date: Optional[str] = None,
    apply_to_future: bool = False,
    dry_run: bool = True,
) -> str:
    """
    Set or update the Flexible expense bucket amount.

    Args:
        amount: The flexible budget amount to set. Use 0 to clear/unset it.
        start_date: The month to set budget for in YYYY-MM-DD format (defaults to current month)
        apply_to_future: Whether to apply this amount to all future months (default: False)
        dry_run: If True, return current/proposed values without mutating (default: True)
    """
    try:
        client = await get_monarch_client()

        if dry_run:
            budgets = await client.get_budgets(start_date=start_date, end_date=start_date)
            current_amount = _find_current_flexible_budget_amount(budgets, start_date)
            return _dry_run_response(
                target={"type": "flexible_budget", "id": "flexible"},
                current_amount=current_amount,
                proposed_amount=float(amount),
                start_date=start_date,
                apply_to_future=apply_to_future,
            )

        update_flexible_budget_method = getattr(client, "update_flexible_budget", None)
        if update_flexible_budget_method is None:
            return json_success(
                {
                    "success": False,
                    "dry_run": False,
                    "error": "Installed monarchmoney client does not support update_flexible_budget.",
                }
            )

        result = await update_flexible_budget_method(
            amount=amount,
            start_date=start_date,
            apply_to_future=apply_to_future,
        )
        return json_success(
            {
                "success": True,
                "dry_run": False,
                "message": f"Flexible budget set to ${amount:.2f}"
                + (" for all future months" if apply_to_future else ""),
                "result": result,
            }
        )
    except Exception as e:
        return json_error("update_flexible_budget", e)
