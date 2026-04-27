"""Shared PostgreSQL client for the transactional store.

Manages the schema and provides async read/write operations for:
  - agent_insights: Foundry agent Q&A insights written during query processing
  - analytical_results: Fabric agent analytical outputs written back to the transactional layer

Uses asyncpg for async operations and psycopg for sync bootstrap.

Usage:
    # Initialize schema
    python shared/postgres_client.py --action init

    # Show recent insights
    python shared/postgres_client.py --action show-insights --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _conn_str() -> str:
    """Build a PostgreSQL connection string from environment."""
    return os.environ.get(
        "POSTGRES_CONNECTION_STRING",
        "postgresql://{user}:{password}@{host}:{port}/{dbname}".format(
            user=os.environ.get("POSTGRES_USER", "iqadmin"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            dbname=os.environ.get("POSTGRES_DB", "microsoftiq"),
        ),
    )


# ── Schema DDL ──

SCHEMA_DDL = """
-- Transactional store for agent insights (written by Foundry IQ)
CREATE TABLE IF NOT EXISTS agent_insights (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent_name      TEXT NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    source_docs     JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    synced_to_fabric BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_insights_created ON agent_insights (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_synced ON agent_insights (synced_to_fabric) WHERE NOT synced_to_fabric;

-- Analytical results written back from Fabric IQ
CREATE TABLE IF NOT EXISTS analytical_results (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    analysis_type   TEXT NOT NULL,
    result_summary  TEXT NOT NULL,
    result_data     JSONB NOT NULL,
    fabric_workspace TEXT,
    consumed        BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_results_type ON analytical_results (analysis_type);
CREATE INDEX IF NOT EXISTS idx_results_consumed ON analytical_results (consumed) WHERE NOT consumed;

-- Orders loaded from Kaggle (transactional source for Fabric)
CREATE TABLE IF NOT EXISTS orders (
    order_id                TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL,
    order_status            TEXT NOT NULL,
    order_purchase_timestamp TIMESTAMPTZ,
    order_approved_at       TIMESTAMPTZ,
    order_delivered_timestamp TIMESTAMPTZ,
    order_estimated_delivery TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (order_status);
CREATE INDEX IF NOT EXISTS idx_orders_purchase ON orders (order_purchase_timestamp DESC);

-- Order items (joins orders ↔ products)
CREATE TABLE IF NOT EXISTS order_items (
    id              SERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    product_id      TEXT NOT NULL,
    seller_id       TEXT NOT NULL,
    price           NUMERIC(10, 2) NOT NULL,
    freight_value   NUMERIC(10, 2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_items_order ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_items_product ON order_items (product_id);

-- Payments
CREATE TABLE IF NOT EXISTS order_payments (
    id              SERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    payment_type    TEXT NOT NULL,
    payment_installments INTEGER DEFAULT 1,
    payment_value   NUMERIC(10, 2) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_order ON order_payments (order_id);
"""


# ── Async pool management ──

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_conn_str(), min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ── Schema bootstrap ──

async def init_schema() -> None:
    """Create all tables and indexes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_DDL)
    print("Schema initialized successfully")


# ── Agent insights (Foundry IQ → Postgres) ──

async def write_insight(
    agent_name: str,
    question: str,
    answer: str,
    source_docs: list[str] | None = None,
    metadata: dict | None = None,
) -> int:
    """Write an agent insight record and return the row id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """
            INSERT INTO agent_insights (agent_name, question, answer, source_docs, metadata)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            RETURNING id
            """,
            agent_name,
            question,
            answer,
            json.dumps(source_docs or []),
            json.dumps(metadata or {}),
        )
    return row_id


async def get_unsynced_insights(limit: int = 500) -> list[dict]:
    """Fetch insights not yet synced to Fabric."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, agent_name, question, answer, source_docs, metadata
            FROM agent_insights
            WHERE NOT synced_to_fabric
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


async def mark_insights_synced(ids: list[int]) -> None:
    """Mark insights as synced to Fabric."""
    if not ids:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_insights SET synced_to_fabric = TRUE WHERE id = ANY($1::int[])",
            ids,
        )


# ── Analytical results (Fabric IQ → Postgres) ──

async def write_analytical_result(
    analysis_type: str,
    result_summary: str,
    result_data: dict,
    fabric_workspace: str = "",
) -> int:
    """Write an analytical result back to the transactional store."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """
            INSERT INTO analytical_results (analysis_type, result_summary, result_data, fabric_workspace)
            VALUES ($1, $2, $3::jsonb, $4)
            RETURNING id
            """,
            analysis_type,
            result_summary,
            json.dumps(result_data),
            fabric_workspace,
        )
    return row_id


async def get_unconsumed_results(analysis_type: str = "", limit: int = 100) -> list[dict]:
    """Fetch analytical results not yet consumed by the transactional layer."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if analysis_type:
            rows = await conn.fetch(
                """
                SELECT id, created_at, analysis_type, result_summary, result_data, fabric_workspace
                FROM analytical_results
                WHERE NOT consumed AND analysis_type = $1
                ORDER BY created_at DESC LIMIT $2
                """,
                analysis_type,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, created_at, analysis_type, result_summary, result_data, fabric_workspace
                FROM analytical_results
                WHERE NOT consumed
                ORDER BY created_at DESC LIMIT $1
                """,
                limit,
            )
    return [dict(r) for r in rows]


async def mark_results_consumed(ids: list[int]) -> None:
    """Mark analytical results as consumed."""
    if not ids:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE analytical_results SET consumed = TRUE WHERE id = ANY($1::int[])",
            ids,
        )


# ── Kaggle order data loading ──

async def load_orders_from_csv(orders_csv: str, items_csv: str, payments_csv: str) -> dict[str, int]:
    """Load Kaggle e-commerce CSVs into PostgreSQL tables."""
    import csv

    pool = await get_pool()
    counts = {}

    # Load orders
    with open(orders_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE orders CASCADE")
        for row in rows:
            await conn.execute(
                """
                INSERT INTO orders (order_id, customer_id, order_status,
                    order_purchase_timestamp, order_approved_at,
                    order_delivered_timestamp, order_estimated_delivery)
                VALUES ($1, $2, $3, $4::timestamptz, $5::timestamptz, $6::timestamptz, $7::timestamptz)
                ON CONFLICT (order_id) DO NOTHING
                """,
                row["order_id"],
                row["customer_id"],
                row["order_status"],
                row.get("order_purchase_timestamp") or None,
                row.get("order_approved_at") or None,
                row.get("order_delivered_carrier_date") or None,
                row.get("order_estimated_delivery_date") or None,
            )
    counts["orders"] = len(rows)
    print(f"  Loaded {len(rows)} orders")

    # Load order items
    with open(items_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE order_items CASCADE")
        for row in rows:
            await conn.execute(
                """
                INSERT INTO order_items (order_id, product_id, seller_id, price, freight_value)
                VALUES ($1, $2, $3, $4, $5)
                """,
                row["order_id"],
                row["product_id"],
                row["seller_id"],
                float(row.get("price", 0)),
                float(row.get("freight_value", 0)),
            )
    counts["order_items"] = len(rows)
    print(f"  Loaded {len(rows)} order items")

    # Load payments
    with open(payments_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE order_payments CASCADE")
        for row in rows:
            await conn.execute(
                """
                INSERT INTO order_payments (order_id, payment_type, payment_installments, payment_value)
                VALUES ($1, $2, $3, $4)
                """,
                row["order_id"],
                row["payment_type"],
                int(row.get("payment_installments", 1)),
                float(row.get("payment_value", 0)),
            )
    counts["order_payments"] = len(rows)
    print(f"  Loaded {len(rows)} payments")

    return counts


# ── CLI ──

async def _show_insights(limit: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, created_at, agent_name, question, synced_to_fabric FROM agent_insights ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    if not rows:
        print("No insights found")
        return
    print(f"{'ID':>5} {'Created':>20} {'Agent':>20} {'Synced':>6}  Question")
    print("-" * 100)
    for r in rows:
        print(f"{r['id']:>5} {str(r['created_at'])[:19]:>20} {r['agent_name']:>20} {str(r['synced_to_fabric']):>6}  {r['question'][:50]}")


async def _show_results(limit: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, created_at, analysis_type, result_summary, consumed FROM analytical_results ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    if not rows:
        print("No analytical results found")
        return
    print(f"{'ID':>5} {'Created':>20} {'Type':>25} {'Consumed':>8}  Summary")
    print("-" * 110)
    for r in rows:
        print(f"{r['id']:>5} {str(r['created_at'])[:19]:>20} {r['analysis_type']:>25} {str(r['consumed']):>8}  {r['result_summary'][:50]}")


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL client for Microsoft IQ")
    parser.add_argument("--action", required=True, choices=["init", "show-insights", "show-results", "load-kaggle"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--data-dir", default="data/raw", help="Directory with Kaggle CSVs (for load-kaggle)")
    args = parser.parse_args()

    async def run():
        try:
            if args.action == "init":
                await init_schema()
            elif args.action == "show-insights":
                await _show_insights(args.limit)
            elif args.action == "show-results":
                await _show_results(args.limit)
            elif args.action == "load-kaggle":
                d = Path(args.data_dir)
                counts = await load_orders_from_csv(
                    str(d / "olist_orders_dataset.csv"),
                    str(d / "olist_order_items_dataset.csv"),
                    str(d / "olist_order_payments_dataset.csv"),
                )
                print(f"\nLoaded: {counts}")
        finally:
            await close_pool()

    asyncio.run(run())


if __name__ == "__main__":
    main()
