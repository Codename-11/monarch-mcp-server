"""Tests for review-scoped transaction mutation tools."""

import json
from unittest.mock import patch

import monarch_mcp_server.tools.transactions as transaction_tools
import monarch_mcp_server.tools.tags as tag_tools


class TestCreateTransactionTagSafe:
    async def test_dry_run_is_default_and_does_not_mutate(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(await tag_tools.create_transaction_tag_safe(name="AI"))

        assert result["dry_run"] is True
        assert result["name"] == "AI"
        mock_monarch_client.create_transaction_tag.assert_not_called()

    async def test_existing_tag_returns_existing_without_mutating(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await tag_tools.create_transaction_tag_safe(name="business", dry_run=False)
            )

        assert result["created"] is False
        assert result["tag"]["id"] == "tag-1"
        mock_monarch_client.create_transaction_tag.assert_not_called()

    async def test_apply_with_dry_run_false_creates_tag(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.tags.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await tag_tools.create_transaction_tag_safe(
                    name="AI",
                    color="#26B3FC",
                    dry_run=False,
                )
            )

        assert result["dry_run"] is False
        assert result["created"] is True
        mock_monarch_client.create_transaction_tag.assert_awaited_once_with(
            name="AI",
            color="#26B3FC",
        )


class TestUpdateTransactionReview:
    async def test_dry_run_is_default_and_does_not_mutate(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.transactions.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await transaction_tools.update_transaction_review(
                    transaction_id="txn-1",
                    category_id="cat-2",
                    add_tag_ids=["tag-2"],
                    mark_reviewed=True,
                )
            )

        assert result["dry_run"] is True
        assert result["planned_update"]["category_id"] == "cat-2"
        assert result["planned_update"]["tag_ids"] == ["tag-1", "tag-2"]
        assert result["planned_update"]["needs_review"] is False
        mock_monarch_client.update_transaction.assert_not_called()
        mock_monarch_client.set_transaction_tags.assert_not_called()

    async def test_resolves_tag_names_preserves_existing_and_applies(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.transactions.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await transaction_tools.update_transaction_review(
                    transaction_id="txn-1",
                    add_tag_names=["vacation"],
                    mark_reviewed=True,
                    dry_run=False,
                )
            )

        assert result["dry_run"] is False
        mock_monarch_client.update_transaction.assert_awaited_once_with(
            transaction_id="txn-1",
            needs_review=False,
        )
        mock_monarch_client.set_transaction_tags.assert_awaited_once_with(
            transaction_id="txn-1",
            tag_ids=["tag-1", "tag-2"],
        )

    async def test_unknown_tag_name_returns_error_without_mutating(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.transactions.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await transaction_tools.update_transaction_review(
                    transaction_id="txn-1",
                    add_tag_names=["AI"],
                    dry_run=False,
                )
            )

        assert result["error"] is True
        assert "Unknown tag name" in result["message"]
        mock_monarch_client.update_transaction.assert_not_called()
        mock_monarch_client.set_transaction_tags.assert_not_called()

    async def test_requires_at_least_one_review_update(self, mock_monarch_client):
        with patch("monarch_mcp_server.tools.transactions.get_monarch_client", return_value=mock_monarch_client):
            result = json.loads(
                await transaction_tools.update_transaction_review(transaction_id="txn-1")
            )

        assert result["error"] is True
        assert "No review update requested" in result["message"]
