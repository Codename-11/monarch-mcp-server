"""Tests for budget-related MCP tools."""

import json

import monarch_mcp_server.tools.budgets as budget_tools

get_budgets = budget_tools.get_budgets
set_budget_amount = budget_tools.set_budget_amount


class TestGetBudgets:
    async def test_returns_raw_budget_data(self):
        result = json.loads(await get_budgets())
        assert "budgetData" in result
        categories = result["budgetData"]["monthlyAmountsByCategory"]
        assert len(categories) == 2
        assert categories[0]["category"]["name"] == "Groceries"

    async def test_passes_date_params(self, mock_monarch_client):
        await get_budgets(start_date="2026-03-01", end_date="2026-03-31")
        mock_monarch_client.get_budgets.assert_called_once_with(
            start_date="2026-03-01", end_date="2026-03-31"
        )

    async def test_passes_none_dates_by_default(self, mock_monarch_client):
        await get_budgets()
        mock_monarch_client.get_budgets.assert_called_once_with(
            start_date=None, end_date=None
        )

    async def test_handles_api_error(self, mock_monarch_client):
        mock_monarch_client.get_budgets.side_effect = Exception("Budget error")
        result = await get_budgets()
        assert "get_budgets" in result


class TestSetBudgetAmount:
    async def test_requires_exactly_one_budget_target(self):
        no_target = json.loads(await set_budget_amount(amount=500.0))
        both_targets = json.loads(
            await set_budget_amount(
                amount=500.0,
                category_id="cat-1",
                category_group_id="grp-1",
            )
        )

        assert no_target["success"] is False
        assert "either category_id or category_group_id" in no_target["error"]
        assert both_targets["success"] is False
        assert "both category_id and category_group_id" in both_targets["error"]

    async def test_dry_run_is_default_and_does_not_mutate(self, mock_monarch_client):
        result = json.loads(
            await set_budget_amount(
                amount=650.0,
                category_id="cat-1",
                start_date="2026-03-01",
            )
        )

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["target"] == {"type": "category", "id": "cat-1"}
        assert result["start_date"] == "2026-03-01"
        assert result["current_amount"] == 500.0
        assert result["proposed_amount"] == 650.0
        assert result["delta"] == 150.0
        mock_monarch_client.set_budget_amount.assert_not_called()

    async def test_dry_run_for_category_group_reads_group_budget(self, mock_monarch_client):
        mock_monarch_client.get_budgets.return_value["budgetData"][
            "monthlyAmountsByCategoryGroup"
        ] = [
            {
                "categoryGroup": {"id": "grp-1", "name": "Food"},
                "monthlyAmounts": [
                    {"month": "2026-03-01", "plannedCashFlowAmount": 700.0}
                ],
            }
        ]

        result = json.loads(
            await set_budget_amount(
                amount=800.0,
                category_group_id="grp-1",
                start_date="2026-03-01",
            )
        )

        assert result["dry_run"] is True
        assert result["target"] == {"type": "category_group", "id": "grp-1"}
        assert result["current_amount"] == 700.0
        assert result["proposed_amount"] == 800.0
        assert result["delta"] == 100.0
        mock_monarch_client.set_budget_amount.assert_not_called()

    async def test_apply_with_dry_run_false_calls_client(self, mock_monarch_client):
        mock_monarch_client.set_budget_amount.return_value = {
            "updateOrCreateBudgetItem": {"budgetItem": {"id": "budget-1"}}
        }

        result = json.loads(
            await set_budget_amount(
                amount=650.0,
                category_id="cat-1",
                start_date="2026-03-01",
                apply_to_future=True,
                dry_run=False,
            )
        )

        assert result["success"] is True
        assert result["dry_run"] is False
        assert result["result"]["updateOrCreateBudgetItem"]["budgetItem"]["id"] == "budget-1"
        mock_monarch_client.set_budget_amount.assert_called_once_with(
            amount=650.0,
            apply_to_future=True,
            category_id="cat-1",
            start_date="2026-03-01",
        )


class TestUpdateFlexibleBudget:
    async def test_dry_run_is_default_and_does_not_mutate(self, mock_monarch_client):
        update_flexible_budget = getattr(budget_tools, "update_flexible_budget", None)
        assert update_flexible_budget is not None
        mock_monarch_client.get_budgets.return_value["budgetData"][
            "monthlyAmountsForFlexExpense"
        ] = {
            "monthlyAmounts": [
                {"month": "2026-03-01", "plannedCashFlowAmount": 2200.0}
            ]
        }

        result = json.loads(
            await update_flexible_budget(amount=2400.0, start_date="2026-03-01")
        )

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["current_amount"] == 2200.0
        assert result["proposed_amount"] == 2400.0
        assert result["delta"] == 200.0
        mock_monarch_client.update_flexible_budget.assert_not_called()

    async def test_apply_with_dry_run_false_calls_client(self, mock_monarch_client):
        update_flexible_budget = getattr(budget_tools, "update_flexible_budget", None)
        assert update_flexible_budget is not None
        mock_monarch_client.update_flexible_budget.return_value = {
            "updateOrCreateFlexBudgetItem": {"budgetItem": {"id": "flex-1"}}
        }

        result = json.loads(
            await update_flexible_budget(
                amount=2400.0,
                start_date="2026-03-01",
                apply_to_future=True,
                dry_run=False,
            )
        )

        assert result["success"] is True
        assert result["dry_run"] is False
        assert result["result"]["updateOrCreateFlexBudgetItem"]["budgetItem"]["id"] == "flex-1"
        mock_monarch_client.update_flexible_budget.assert_called_once_with(
            amount=2400.0,
            start_date="2026-03-01",
            apply_to_future=True,
        )
