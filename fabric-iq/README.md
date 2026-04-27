# Fabric IQ — Data Pipeline Agents

This module demonstrates building an end-to-end data pipeline in Microsoft Fabric that ingests data, processes it through a Lakehouse, and creates a Fabric Agent that reasons over the ingested data — all via code-first approach using the Fabric REST API.

## What You'll Learn

1. **Fabric REST API**: Create workspaces, Lakehouses, and Eventstreams programmatically
2. **Real-time ingestion**: Configure Eventstream to ingest sample data into a Lakehouse
3. **Data processing**: Use a Fabric notebook to transform and analyze ingested data
4. **Fabric Agent**: Create an agent that queries Lakehouse tables and answers natural-language questions

## Architecture

```
Sample Data
    │
    ▼
Eventstream ──→ Lakehouse ──→ Fabric Agent
                    │
                    ▼
              Notebook (ETL)
```

### Components

| Component | Purpose |
|-----------|---------|
| Fabric Workspace | Container for all pipeline artifacts |
| Eventstream | Real-time data ingestion from external sources |
| Lakehouse | Unified analytics store (Delta Lake tables + files) |
| Notebook | Data transformation and exploratory analysis |
| Fabric Agent | Natural-language reasoning over Lakehouse data |

## Prerequisites

- Microsoft Fabric capacity (F2+ or trial)
- Azure CLI authenticated (`az login`)
- Python 3.11+ with `uv` or `pip`

## Quick Start

### Step 1 — Create Workspace and Lakehouse

```bash
cd fabric-iq
python src/fabric_client.py --action create-workspace --name "microsoft-iq-demo"
python src/fabric_client.py --action create-lakehouse --workspace "microsoft-iq-demo" --name "iq-lakehouse"
```

### Step 2 — Configure Eventstream

```bash
python src/pipeline_orchestrator.py --action create-eventstream \
    --workspace "microsoft-iq-demo" \
    --name "iq-eventstream" \
    --lakehouse "iq-lakehouse"
```

### Step 3 — Ingest Sample Data

```bash
python src/pipeline_orchestrator.py --action ingest-sample \
    --workspace "microsoft-iq-demo" \
    --lakehouse "iq-lakehouse"
```

### Step 4 — Process Data with Notebook

Upload and run the notebook in the Fabric workspace:

```bash
python src/fabric_client.py --action upload-notebook \
    --workspace "microsoft-iq-demo" \
    --path notebooks/ingest_and_analyze.py
```

### Step 5 — Create Fabric Agent

```bash
python src/fabric_agent.py --action create \
    --workspace "microsoft-iq-demo" \
    --lakehouse "iq-lakehouse" \
    --name "iq-analyst"
```

### Step 6 — Query the Agent

```bash
python src/fabric_agent.py --action query \
    --workspace "microsoft-iq-demo" \
    --name "iq-analyst" \
    --question "What are the top 5 products by revenue this quarter?"
```

## Sample Data

The demo uses a synthetic retail dataset with:
- **Products** — 50 items across 5 categories (electronics, clothing, food, sports, home)
- **Sales transactions** — 1,000 records over 90 days with quantity, price, region
- **Customer segments** — 4 tiers (bronze, silver, gold, platinum)

No real business data is included.

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
| `POST /v1/workspaces/{id}/eventstreams` | Create Eventstream |
| `POST /v1/workspaces/{id}/notebooks` | Upload notebook |
| `POST /v1/workspaces/{id}/items` | Create Fabric Agent |
| `GET /v1/workspaces/{id}/lakehouses/{id}/tables` | List Lakehouse tables |
