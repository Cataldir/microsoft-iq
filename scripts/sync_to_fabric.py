"""Sync data from PostgreSQL to Fabric Lakehouse.

Exports transactional data (orders, items, payments, agent insights) from Postgres
and loads it into Fabric Lakehouse tables for analytical processing.

This is the Transactional → Analytical bridge in the data cycle.

Usage:
    python scripts/sync_to_fabric.py --workspace microsoft-iq-demo --lakehouse iq-lakehouse
    python scripts/sync_to_fabric.py --workspace microsoft-iq-demo --lakehouse iq-lakehouse --tables orders,insights
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import sys
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Allow importing shared module
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


async def _export_table(query: str, columns: list[str]) -> str:
    """Run a Postgres query and return the results as CSV."""
    from postgres_client import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: str(row.get(col, "")) for col in columns})

    return output.getvalue()


async def export_orders() -> str:
    """Export orders table to CSV."""
    return await _export_table(
        "SELECT order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_timestamp, order_estimated_delivery FROM orders ORDER BY order_purchase_timestamp",
        ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at", "order_delivered_timestamp", "order_estimated_delivery"],
    )


async def export_order_items() -> str:
    """Export order items table to CSV."""
    return await _export_table(
        "SELECT order_id, product_id, seller_id, price, freight_value FROM order_items",
        ["order_id", "product_id", "seller_id", "price", "freight_value"],
    )


async def export_payments() -> str:
    """Export payments table to CSV."""
    return await _export_table(
        "SELECT order_id, payment_type, payment_installments, payment_value FROM order_payments",
        ["order_id", "payment_type", "payment_installments", "payment_value"],
    )


async def export_insights() -> str:
    """Export unsynced agent insights to CSV and mark them as synced."""
    from postgres_client import get_unsynced_insights, mark_insights_synced

    rows = await get_unsynced_insights(limit=5000)
    if not rows:
        return ""

    output = io.StringIO()
    columns = ["id", "created_at", "agent_name", "question", "answer"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: str(row.get(col, "")) for col in columns})

    # Mark as synced
    await mark_insights_synced([r["id"] for r in rows])
    return output.getvalue()


def _fabric_headers() -> dict[str, str]:
    credential = DefaultAzureCredential()
    token = credential.get_token(FABRIC_SCOPE)
    return {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "text/csv",
    }


def _find_workspace(name: str, headers: dict) -> dict | None:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{FABRIC_API}/workspaces", headers={**headers, "Content-Type": "application/json"})
        resp.raise_for_status()
    return next((w for w in resp.json().get("value", []) if w.get("displayName") == name), None)


def _find_lakehouse(workspace_id: str, name: str, headers: dict) -> dict | None:
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
            headers={**headers, "Content-Type": "application/json"},
        )
        resp.raise_for_status()
    return next((lh for lh in resp.json().get("value", []) if lh.get("displayName") == name), None)


def upload_csv_to_lakehouse(workspace_id: str, lakehouse_id: str, table_name: str, csv_data: str) -> dict:
    """Upload CSV data to a Fabric Lakehouse table."""
    headers = _fabric_headers()

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}/load",
            headers=headers,
            content=csv_data.encode("utf-8"),
            params={"mode": "overwrite", "format": "csv", "header": "true"},
        )

    if resp.status_code in (200, 202):
        lines = csv_data.count("\n") - 1
        print(f"  Table '{table_name}': loaded {lines} rows")
        return {"table": table_name, "rows": lines, "status": "success"}
    else:
        print(f"  Table '{table_name}': HTTP {resp.status_code}")
        return {"table": table_name, "status": "error", "detail": resp.text[:300]}


async def sync_all(workspace_name: str, lakehouse_name: str, tables: list[str] | None = None) -> dict:
    """Run full sync from Postgres to Fabric Lakehouse."""
    headers = _fabric_headers()

    ws = _find_workspace(workspace_name, headers)
    if not ws:
        print(f"Workspace '{workspace_name}' not found")
        return {"error": "workspace_not_found"}

    lh = _find_lakehouse(ws["id"], lakehouse_name, headers)
    if not lh:
        print(f"Lakehouse '{lakehouse_name}' not found")
        return {"error": "lakehouse_not_found"}

    all_tables = tables or ["orders", "order_items", "order_payments", "agent_insights"]
    results = {}

    exporters = {
        "orders": export_orders,
        "order_items": export_order_items,
        "order_payments": export_payments,
        "agent_insights": export_insights,
    }

    for table_name in all_tables:
        exporter = exporters.get(table_name)
        if not exporter:
            print(f"  Skipping unknown table: {table_name}")
            continue

        print(f"Exporting {table_name} from Postgres...")
        csv_data = await exporter()
        if not csv_data or csv_data.count("\n") <= 1:
            print(f"  {table_name}: no data to sync")
            results[table_name] = {"status": "empty"}
            continue

        print(f"Uploading {table_name} to Fabric...")
        results[table_name] = upload_csv_to_lakehouse(ws["id"], lh["id"], table_name, csv_data)

    return results


def main():
    parser = argparse.ArgumentParser(description="Sync Postgres data to Fabric Lakehouse")
    parser.add_argument("--workspace", required=True, help="Fabric workspace name")
    parser.add_argument("--lakehouse", required=True, help="Lakehouse name")
    parser.add_argument("--tables", help="Comma-separated table names (default: all)")
    args = parser.parse_args()

    tables = args.tables.split(",") if args.tables else None

    async def run():
        from postgres_client import close_pool
        try:
            results = await sync_all(args.workspace, args.lakehouse, tables)
            print(f"\nSync results: {json.dumps(results, indent=2)}")
        finally:
            await close_pool()

    asyncio.run(run())


if __name__ == "__main__":
    main()
