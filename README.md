# Microsoft IQ — Intelligent Knowledge for Agents, Work, and Data

Three hands-on demos showcasing how Microsoft's AI platform makes knowledge accessible to agents, workers, and data pipelines — connected through an end-to-end data cycle.

## What You'll Build

| Module | What It Demonstrates | Key Services |
|--------|---------------------|--------------|
| **[Foundry IQ](foundry-iq/)** | Knowledge bases grounded in Kaggle e-commerce data; writes agent insights to Postgres | Azure AI Foundry, Blob Storage, AI Search, PostgreSQL |
| **[Work IQ](work-iq/)** | Extract work intelligence with Copilot CLI + MCP servers | Copilot CLI, Dataverse, MCP Protocol |
| **[Fabric IQ](fabric-iq/)** | Analyze e-commerce data from Postgres in Lakehouse; write results back | Microsoft Fabric, Lakehouse, PostgreSQL |

## End-to-End Data Cycle

Data flows from Kaggle through three stages — **Transactional → Analytical → Transactional** — with PostgreSQL as the bridge:

```
                    ┌──────────────────────────────────────────────┐
                    │          END-TO-END DATA CYCLE                │
                    │                                              │
   Kaggle           │   TRANSACTIONAL        ANALYTICAL            │
   (Olist)          │                                              │
     │              │   ┌──────────┐        ┌──────────┐           │
     ├──► Blob ──►  │   │ AI Search│        │ Fabric   │           │
     │   Storage    │   │  Index   │        │ Lakehouse│           │
     │              │   └────┬─────┘        └────┬─────┘           │
     │              │        │                   │                 │
     │              │   ┌────▼─────┐        ┌────▼─────┐           │
     │              │   │ Foundry  │        │ Fabric   │           │
     │              │   │  Agent   │        │  Agent   │           │
     │              │   └────┬─────┘        └────┬─────┘           │
     │              │        │                   │                 │
     │              │        ▼                   ▼                 │
     └──► Postgres ◄┼── insights ──►    ◄── results ──►           │
          (orders,  │  (agent writes)     (agent writes)           │
           items,   │        │                   │                 │
           payments)│        └───► sync ◄────────┘                 │
                    │         (Postgres → Fabric Lakehouse)        │
                    └──────────────────────────────────────────────┘
```

### Data Flow Steps

1. **Kaggle → Blob Storage**: Download Brazilian E-Commerce dataset, upload CSVs to Azure Blob
2. **Blob → AI Search**: Index products and reviews for Foundry agent knowledge base
3. **Kaggle → PostgreSQL**: Load orders, items, and payments into transactional tables
4. **Foundry Agent** answers questions grounded in indexed data; writes each Q&A as an `agent_insight` to Postgres
5. **Postgres → Fabric Lakehouse**: Sync orders + insights to Lakehouse via REST API
6. **Fabric Notebook**: Creates derived tables (sales_summary, delivery_performance, top_products)
7. **Fabric Agent** queries analytical tables; writes `analytical_result` back to Postgres
8. **Foundry Agent** reads unconsumed analytical results from Postgres to enrich future answers

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) package manager
- **Azure CLI** (`az`) authenticated to your subscription
- **Azure subscription** with:
  - Azure AI Foundry access
  - Azure Blob Storage
  - Azure AI Search
- **PostgreSQL 15+** (local or Azure Database for PostgreSQL)
- **Kaggle account** with API credentials (`~/.kaggle/kaggle.json`)
- **Copilot CLI** installed (for Work IQ module)
- **Microsoft Fabric** capacity (for Fabric IQ module)

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Cataldir/microsoft-iq.git
cd microsoft-iq

# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your Azure + Postgres + Kaggle credentials

# ── Step 1: Download Kaggle dataset ──
python scripts/download_kaggle.py

# ── Step 2: Upload to Blob Storage ──
python scripts/upload_to_blob.py

# ── Step 3: Index products/reviews into AI Search (Foundry IQ) ──
python scripts/index_blob_data.py

# ── Step 4: Initialize Postgres and load order data ──
python shared/postgres_client.py --action init
python shared/postgres_client.py --action load-kaggle --data-dir data/raw

# ── Step 5: Query Foundry Agent (writes insights to Postgres) ──
cd foundry-iq && python src/api_server.py  # or: python src/query_agent.py "top product categories?"

# ── Step 6: Sync Postgres → Fabric Lakehouse ──
python scripts/sync_to_fabric.py --workspace microsoft-iq-demo --lakehouse iq-lakehouse

# ── Step 7: Run Fabric notebook + query Fabric Agent ──
cd fabric-iq
python src/fabric_agent.py --action query --workspace microsoft-iq-demo --name iq-analyst \
    --question "What are the delivery performance trends?"
# → writes analytical result back to Postgres (completing the cycle)
```

## Module Details

### 1. Foundry IQ — Knowledge Bases for Agents

Demonstrates creating knowledge bases in Azure AI Foundry grounded in real e-commerce data from Kaggle (Olist Brazilian E-Commerce). Products and reviews are indexed in AI Search; the agent writes every Q&A interaction to PostgreSQL as a transactional insight that feeds Fabric IQ.

**Key highlights:**
- Portal walkthrough: knowledge base creation, model selection, retrieval configuration
- Kaggle data pipeline: download → blob upload → AI Search indexing
- Foundry agent grounded in products and customer reviews
- Transactional writeback: agent insights → PostgreSQL → Fabric Lakehouse
- Local HTML/CSS/JS demo UI

### 2. Work IQ — Work Intelligence with Copilot CLI

Demonstrates extracting work signals using the MCP server pattern connected to Dataverse. Shows how to build a minimal MCP server, query CRM opportunities, classify signals, and generate daily work digests — all sanitized with synthetic data for public demonstration.

**Key highlights:**
- MCP server tool registration and dispatch
- Dataverse Web API integration for CRM data
- Signal classification (wins, losses, escalations, compete signals)
- Copilot CLI prompt templates for daily digests

### 3. Fabric IQ — Data Pipeline Agents

Demonstrates orchestrating analytical pipelines with Microsoft Fabric using real e-commerce data synced from PostgreSQL. The Fabric Agent reasons over Lakehouse tables and writes analytical results back to PostgreSQL, completing the Transactional → Analytical → Transactional cycle.

**Key highlights:**
- Kaggle e-commerce data flows: orders, items, payments, agent insights
- PostgreSQL → Fabric Lakehouse sync via REST API
- PySpark notebook: delivery performance, payment analysis, revenue rankings
- Fabric Agent for natural-language analytics over Lakehouse
- Analytical writeback: Fabric results → PostgreSQL → Foundry Agent enrichment

## License

MIT

## Author

Ricardo Cataldi — Sao Paulo, Brazil
