"""Tag management tools."""

import logging
from typing import Any, List, Optional

from monarch_mcp_server.app import mcp
from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.helpers import json_success, json_error

logger = logging.getLogger(__name__)


def _extract_transaction_tags(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_tags = data.get("householdTransactionTags") or data.get("tags") or []
    return [
        {"id": tag.get("id"), "name": tag.get("name"), "color": tag.get("color")}
        for tag in raw_tags
        if isinstance(tag, dict)
    ]


def _find_tag_by_name(tags: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
    normalized = name.strip().casefold()
    for tag in tags:
        if str(tag.get("name") or "").strip().casefold() == normalized:
            return tag
    return None


@mcp.tool()
async def create_transaction_tag_safe(
    name: str,
    color: str = "#26B3FC",
    dry_run: bool = True,
) -> str:
    """
    Safely create a transaction tag, defaulting to dry-run.

    If a tag with the same case-insensitive name already exists, returns it
    without creating a duplicate. Use dry_run=false to actually create a missing
    tag.
    """
    try:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Tag name is required")

        client = await get_monarch_client()
        tags = _extract_transaction_tags(await client.get_transaction_tags())
        existing = _find_tag_by_name(tags, clean_name)
        if existing is not None:
            return json_success(
                {
                    "dry_run": dry_run,
                    "created": False,
                    "tag": existing,
                    "message": "Tag already exists; no mutation needed.",
                }
            )

        if dry_run:
            return json_success(
                {
                    "dry_run": True,
                    "created": False,
                    "name": clean_name,
                    "color": color,
                    "message": "Dry run only; call again with dry_run=false to create tag.",
                }
            )

        result = await client.create_transaction_tag(name=clean_name, color=color)
        return json_success(
            {
                "dry_run": False,
                "created": True,
                "name": clean_name,
                "color": color,
                "result": result,
            }
        )
    except Exception as e:
        return json_error("create_transaction_tag_safe", e)


@mcp.tool()
async def set_transaction_tags(
    transaction_id: str,
    tag_ids: List[str],
) -> str:
    """
    Set tags on a transaction.

    Note: This REPLACES all existing tags on the transaction.
    To add a tag, include both existing and new tag IDs.
    To remove all tags, pass an empty list.

    Args:
        transaction_id: The ID of the transaction to tag
        tag_ids: List of tag IDs to apply (use get_tags to find IDs)

    Returns:
        Updated transaction details.
    """
    try:
        client = await get_monarch_client()
        result = await client.set_transaction_tags(
            transaction_id=transaction_id,
            tag_ids=tag_ids,
        )
        return json_success(result)
    except Exception as e:
        return json_error("set_transaction_tags", e)


@mcp.tool()
async def get_transaction_tags() -> str:
    """Get all available transaction tags from Monarch Money."""
    try:
        client = await get_monarch_client()
        data = await client.get_transaction_tags()
        raw_tags = data.get("householdTransactionTags") or data.get("tags") or []
        tags = [
            {"id": t.get("id"), "name": t.get("name"), "color": t.get("color")}
            for t in raw_tags
        ]
        return json_success(tags)
    except Exception as e:
        return json_error("get_transaction_tags", e)


@mcp.tool()
async def create_transaction_tag(name: str, color: str) -> str:
    """
    Create a new transaction tag.

    Args:
        name: Name of the new tag
        color: Hex color code for the tag (e.g. "#ff0000")
    """
    try:
        client = await get_monarch_client()
        result = await client.create_transaction_tag(name=name, color=color)
        return json_success(result)
    except Exception as e:
        return json_error("create_transaction_tag", e)


@mcp.tool()
async def add_transaction_tag(transaction_id: str, tag_id: str) -> str:
    """
    Add a tag to a transaction, preserving any tags already on it.

    Args:
        transaction_id: The ID of the transaction
        tag_id: The tag ID to add
    """
    try:
        client = await get_monarch_client()
        details = await client.get_transaction_details(transaction_id)
        txn = details.get("getTransaction") or {}
        existing = [t.get("id") for t in (txn.get("tags") or []) if t.get("id")]
        if tag_id not in existing:
            existing.append(tag_id)
        result = await client.set_transaction_tags(
            transaction_id=transaction_id, tag_ids=existing
        )
        return json_success(result)
    except Exception as e:
        return json_error("add_transaction_tag", e)
