# Fabric IQ — Data Pipeline Agents

This module demonstrates building an analytical pipeline in Microsoft Fabric that processes real e-commerce data (Olist / Kaggle) synced from PostgreSQL, creates derived analytical tables, and writes insights back to complete the **Transactional → Analytical → Transactional** data cycle.

## What You'll Learn

1. **Fabric REST API**: Create workspaces, Lakehouses, and items programmatically
2. **PostgreSQL → Lakehouse sync**: Export transactional data to Fabric via REST API
3. **PySpark analytics**: Delivery performance, payment trends, revenue rankings
4. **Fabric Agent**: Natural-language queries over Lakehouse data
5. **Analytical writeback**: Fabric Agent results flow back to PostgreSQL for Foundry IQ

## Architecture

```
PostgreSQL (orders, items, payments, agent_insights)
    │
    │  scripts/sync_to_fabric.py
    ▼
Lakehouse (Delta Tables) ──→ Fabric Agent ──→ PostgreSQL
    │                                         (analytical_results)
    ▼
Notebook (PySpark ETL)
    ├── sales_summary
    ├── delivery_performance
    ├── payment_analysis
    ├── top_products
    └── top_sellers
```

### Components

| Component | Purpose |
|-----------|---------|
| Fabric Workspace | Container for all pipeline artifacts |
| Lakehouse | Unified analytics store (Delta Lake tables + files) |
| Notebook | PySpark data transformation and derived table creation |
| Fabric Agent | Natural-language reasoning over Lakehouse data |
| PostgreSQL | Transactional store — source of orders, sink for analytical results |

## Prerequisites

- Microsoft Fabric capacity (F2+ or trial)
- Azure CLI authenticated (`az login`)
- PostgreSQL with data loaded (see root README)
- Python 3.11+ with `uv` or `pip`

## Quick Start

### Step 1 — Create Workspace and Lakehouse

```bash
cd fabric-iq
python src/fabric_client.py --action create-workspace --name "microsoft-iq-demo"
python src/fabric_client.py --action create-lakehouse --workspace "microsoft-iq-demo" --name "iq-lakehouse"
```

### Step 2 — Sync PostgreSQL Data to Lakehouse

```bash
# From repo root — exports orders, items, payments, and agent insights
python scripts/sync_to_fabric.py --workspace microsoft-iq-demo --lakehouse iq-lakehouse
```

### Step 3 — Upload and Run Notebook

```bash
python src/fabric_client.py --action upload-notebook \
    --workspace "microsoft-iq-demo" \
    --path notebooks/ingest_and_analyze.py
```

### Step 4 — Create Fabric Agent

```bash
python src/fabric_agent.py --action create \
    --workspace "microsoft-iq-demo" \
    --lakehouse "iq-lakehouse" \
    --name "iq-analyst"
```

### Step 5 — Query the Agent (writes back to Postgres)

```bash
python src/fabric_agent.py --action query \
    --workspace "microsoft-iq-demo" \
    --name "iq-analyst" \
    --question "What are the delivery performance trends by month?"
# → Writes analytical_result to PostgreSQL, which Foundry Agent reads next time
```

## Data Source

Data comes from the **Olist Brazilian E-Commerce** Kaggle dataset, loaded into PostgreSQL via `shared/postgres_client.py --action load-kaggle` and synced to Fabric via `scripts/sync_to_fabric.py`.

### Lakehouse Tables

| Table | Source | Description |
|-------|--------|-------------|
| `orders` | Postgres sync | 99K+ order records with status and timestamps |
| `order_items` | Postgres sync | Line items with product, seller, price, freight |
| `order_payments` | Postgres sync | Payment records with type and installments |
| `agent_insights` | Postgres sync | Foundry agent Q&A interactions |
| `sales_summary` | Derived (notebook) | Daily/monthly revenue by status |
| `delivery_performance` | Derived (notebook) | Monthly delivery SLA and timing |
| `payment_analysis` | Derived (notebook) | Payment method distribution |
| `top_products` | Derived (notebook) | Products ranked by revenue |
| `top_sellers` | Derived (notebook) | Sellers ranked by revenue |

## Code-First Philosophy

Every resource is created via the Fabric REST API rather than through the portal UI. This enables:
- Repeatable deployments
- Version-controlled pipeline definitions
- CI/CD integration for data engineering workflows
- Cross-environment promotion (dev → staging → prod)

## Key Fabric REST API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/workspaces` | Create workspace |
| `POST /v1/workspaces/{id}/lakehouses` | Create Lakehouse |
| `POST /v1/workspaces/{id}/notebooks` | Upload notebook |
| `POST /v1/workspaces/{id}/items` | Create Fabric Agent |
| `GET /v1/workspaces/{id}/lakehouses/{id}/tables` | List Lakehouse tables |
| `POST .../tables/{name}/load` | Load CSV data into table |
