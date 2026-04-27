"""Pipeline orchestrator — Eventstream and sample data ingestion via Fabric REST API.

Creates Eventstreams and loads sample retail data into Lakehouse tables.

Usage:
    python src/pipeline_orchestrator.py --action create-eventstream --workspace "my-workspace" --name "my-stream" --lakehouse "my-lakehouse"
    python src/pipeline_orchestrator.py --action ingest-sample --workspace "my-workspace" --lakehouse "my-lakehouse"
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
from datetime import datetime, timedelta, timezone

import httpx
from azure.identity import DefaultAzureCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


# ── Sample data generation ──

CATEGORIES = ["electronics", "clothing", "food", "sports", "home"]

PRODUCTS = [
    ("Wireless Earbuds", "electronics", 79.99),
    ("Smart Watch Pro", "electronics", 249.99),
    ("USB-C Hub", "electronics", 49.99),
    ("4K Webcam", "electronics", 129.99),
    ("Portable Charger", "electronics", 39.99),
    ("Noise-Cancel Headphones", "electronics", 199.99),
    ("Bluetooth Speaker", "electronics", 89.99),
    ("Tablet Stand", "electronics", 29.99),
    ("LED Desk Lamp", "electronics", 59.99),
    ("Mechanical Keyboard", "electronics", 149.99),
    ("Running Shoes", "clothing", 119.99),
    ("Performance Jacket", "clothing", 89.99),
    ("Training Shorts", "clothing", 34.99),
    ("Compression Socks", "clothing", 19.99),
    ("Sport Sunglasses", "clothing", 69.99),
    ("Wool Sweater", "clothing", 79.99),
    ("Canvas Sneakers", "clothing", 54.99),
    ("Rain Jacket", "clothing", 99.99),
    ("Hiking Boots", "clothing", 149.99),
    ("Thermal Gloves", "clothing", 24.99),
    ("Organic Coffee Beans", "food", 18.99),
    ("Protein Bar Pack", "food", 24.99),
    ("Green Tea Set", "food", 15.99),
    ("Trail Mix", "food", 9.99),
    ("Energy Drink Case", "food", 29.99),
    ("Dark Chocolate Box", "food", 12.99),
    ("Granola Clusters", "food", 7.99),
    ("Coconut Water Pack", "food", 14.99),
    ("Dried Fruit Mix", "food", 11.99),
    ("Nut Butter Jar", "food", 8.99),
    ("Yoga Mat", "sports", 44.99),
    ("Resistance Bands", "sports", 19.99),
    ("Jump Rope", "sports", 14.99),
    ("Foam Roller", "sports", 29.99),
    ("Dumbbell Set", "sports", 89.99),
    ("Pull-Up Bar", "sports", 39.99),
    ("Ab Wheel", "sports", 24.99),
    ("Kettlebell", "sports", 49.99),
    ("Boxing Gloves", "sports", 59.99),
    ("Exercise Ball", "sports", 19.99),
    ("Scented Candle Set", "home", 34.99),
    ("Throw Blanket", "home", 49.99),
    ("Ceramic Vase", "home", 29.99),
    ("Wall Clock", "home", 39.99),
    ("Desk Organizer", "home", 24.99),
    ("Picture Frame Set", "home", 19.99),
    ("Plant Pot Trio", "home", 44.99),
    ("Aroma Diffuser", "home", 54.99),
    ("Coaster Set", "home", 14.99),
    ("Bookend Pair", "home", 22.99),
]

REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]
SEGMENTS = ["bronze", "silver", "gold", "platinum"]


def generate_sales_data(num_records: int = 1000, days: int = 90) -> list[dict]:
    """Generate synthetic retail sales transactions."""
    random.seed(42)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    transactions = []
    for i in range(num_records):
        product_name, category, base_price = random.choice(PRODUCTS)
        # Apply a small random price variation (±10%)
        price = round(base_price * random.uniform(0.90, 1.10), 2)
        quantity = random.randint(1, 10)
        sale_date = start_date + timedelta(seconds=random.randint(0, days * 86400))

        transactions.append({
            "transaction_id": f"TXN-{i + 1:05d}",
            "date": sale_date.strftime("%Y-%m-%d"),
            "product": product_name,
            "category": category,
            "quantity": quantity,
            "unit_price": price,
            "total": round(price * quantity, 2),
            "region": random.choice(REGIONS),
            "customer_segment": random.choice(SEGMENTS),
        })

    return transactions


def generate_products_table() -> list[dict]:
    """Generate the product dimension table."""
    return [
        {"product_id": f"PRD-{i + 1:03d}", "name": name, "category": cat, "base_price": price}
        for i, (name, cat, price) in enumerate(PRODUCTS)
    ]


def to_csv(records: list[dict]) -> str:
    """Convert records to CSV string."""
    if not records:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


# ── Fabric API operations ──

class PipelineOrchestrator:
    """Orchestrates Eventstream creation and data ingestion."""

    def __init__(self):
        self._credential = DefaultAzureCredential()

    def _headers(self) -> dict[str, str]:
        token = self._credential.get_token(FABRIC_SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

    def _find_workspace(self, name: str) -> dict | None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{FABRIC_API}/workspaces", headers=self._headers())
            resp.raise_for_status()
            workspaces = resp.json().get("value", [])
        return next((w for w in workspaces if w.get("displayName") == name), None)

    def _find_lakehouse(self, workspace_id: str, name: str) -> dict | None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
                headers=self._headers(),
            )
            resp.raise_for_status()
            lakehouses = resp.json().get("value", [])
        return next((lh for lh in lakehouses if lh.get("displayName") == name), None)

    def create_eventstream(self, workspace_id: str, name: str) -> dict:
        """Create an Eventstream in the workspace."""
        body = {
            "displayName": name,
            "type": "Eventstream",
            "description": "IQ demo real-time ingestion stream",
        }

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/items",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            result = resp.json()
            print(f"Created Eventstream '{name}' (id: {result.get('id', 'pending')})")
            return result

    def ingest_sample_data(self, workspace_id: str, lakehouse_id: str) -> dict:
        """Load sample CSV data into Lakehouse tables via the Tables API."""
        results = {}

        # Generate data
        sales = generate_sales_data(1000, 90)
        products = generate_products_table()

        # Upload sales table
        print(f"Ingesting {len(sales)} sales records...")
        sales_result = self._load_table(workspace_id, lakehouse_id, "sales_transactions", sales)
        results["sales_transactions"] = sales_result

        # Upload products table
        print(f"Ingesting {len(products)} product records...")
        products_result = self._load_table(workspace_id, lakehouse_id, "products", products)
        results["products"] = products_result

        print(f"Ingestion complete: {len(sales)} sales + {len(products)} products")
        return results

    def _load_table(self, workspace_id: str, lakehouse_id: str, table_name: str, records: list[dict]) -> dict:
        """Load records into a Lakehouse table."""
        csv_content = to_csv(records)

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables/{table_name}/load",
                headers={
                    **self._headers(),
                    "Content-Type": "text/csv",
                },
                content=csv_content.encode("utf-8"),
                params={
                    "mode": "overwrite",
                    "format": "csv",
                    "header": "true",
                },
            )
            if resp.status_code in (200, 202):
                print(f"  Table '{table_name}': loaded {len(records)} rows")
                return {"table": table_name, "rows": len(records), "status": "success"}
            else:
                print(f"  Table '{table_name}': HTTP {resp.status_code} — {resp.text[:200]}")
                return {"table": table_name, "rows": 0, "status": "error", "detail": resp.text[:500]}


# ── CLI entry point ──

def main():
    parser = argparse.ArgumentParser(description="Fabric pipeline orchestrator")
    parser.add_argument("--action", required=True, choices=["create-eventstream", "ingest-sample", "generate-csv"])
    parser.add_argument("--workspace", help="Workspace display name")
    parser.add_argument("--name", help="Eventstream name")
    parser.add_argument("--lakehouse", help="Lakehouse display name")
    parser.add_argument("--output", help="Output path (for generate-csv)")
    args = parser.parse_args()

    if args.action == "generate-csv":
        # Local-only: generate sample CSVs without hitting the API
        from pathlib import Path
        out_dir = Path(args.output or "sample-data")
        out_dir.mkdir(parents=True, exist_ok=True)

        sales = generate_sales_data(1000, 90)
        products = generate_products_table()

        (out_dir / "sales_transactions.csv").write_text(to_csv(sales), encoding="utf-8")
        (out_dir / "products.csv").write_text(to_csv(products), encoding="utf-8")
        print(f"Generated sample data in {out_dir}/")
        return

    orch = PipelineOrchestrator()

    ws = orch._find_workspace(args.workspace)
    if not ws:
        print(f"Workspace '{args.workspace}' not found")
        sys.exit(1)

    if args.action == "create-eventstream":
        if not args.name:
            parser.error("--name required for create-eventstream")
        result = orch.create_eventstream(ws["id"], args.name)
        print(json.dumps(result, indent=2))

    elif args.action == "ingest-sample":
        if not args.lakehouse:
            parser.error("--lakehouse required for ingest-sample")
        lh = orch._find_lakehouse(ws["id"], args.lakehouse)
        if not lh:
            print(f"Lakehouse '{args.lakehouse}' not found")
            sys.exit(1)
        result = orch.ingest_sample_data(ws["id"], lh["id"])
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
