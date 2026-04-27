# Microsoft IQ — Architecture

## System Overview

Microsoft IQ is a three-module demo walkthrough that demonstrates an end-to-end data cycle — **Transactional → Analytical → Transactional** — using Azure AI Foundry, Microsoft Fabric, and PostgreSQL. Data originates from the Kaggle Brazilian E-Commerce dataset (Olist) and flows through both AI agents.

```
Kaggle (Olist Brazilian E-Commerce)
    │
    ├──► Blob Storage ──► AI Search Index ──► Foundry Agent
    │                                              │
    │                                         insights ──► PostgreSQL
    │                                                         │
    └──► PostgreSQL (orders, items, payments)                  │
              │                                                │
              └──► Fabric Lakehouse ◄──────────────────────────┘
                        │
                   Fabric Notebook (PySpark)
                        │
                   Fabric Agent
                        │
                   analytical_results ──► PostgreSQL ──► Foundry Agent
                                          (cycle complete)
```

## Data Cycle

| Phase | Direction | What Happens |
|-------|-----------|-------------|
| 1. Ingest | Kaggle → Blob + Postgres | CSVs uploaded to blob, orders loaded into Postgres |
| 2. Index | Blob → AI Search | Products and reviews indexed for Foundry knowledge base |
| 3. Transactional | Foundry Agent → Postgres | Each agent Q&A writes an `agent_insight` row |
| 4. Sync | Postgres → Fabric Lakehouse | Orders + insights exported as CSV, loaded into Delta tables |
| 5. Analytical | Fabric Notebook → Lakehouse | Derived tables: sales_summary, delivery_performance, top_products |
| 6. Analytical Query | Fabric Agent → Postgres | Analytical results written as `analytical_result` rows |
| 7. Enrichment | Postgres → Foundry Agent | Foundry reads unconsumed results to enrich future answers |

## Module Architectures

### Foundry IQ

Deploys a knowledge-grounded AI agent using Azure AI Foundry, backed by Kaggle e-commerce data indexed in AI Search.

```
Kaggle CSVs (products, reviews)
    │
    ▼
Azure Blob Storage ◄── Managed Identity ──► Azure AI Search
    │                                           │
    │  scripts/index_blob_data.py               │
    └───────────────────────────────────────────┘
                        │
                        ▼
              Azure AI Foundry Agent
              (Knowledge Base: AI Search)
                        │
               ┌────────┴────────┐
               ▼                 ▼
         Local Chat UI     PostgreSQL
         (HTML/JS)       (agent_insights)
                               │
                               ▼
                     Fabric Lakehouse (sync)
```

**Infrastructure (Bicep):**
- Storage Account with `kaggle-data` container
- AI Search service (Basic tier, SystemAssigned identity)
- AI Services account (API key auth disabled)
- Role assignments: Cognitive Services User, Storage Blob Data Reader

**Transactional Bridge:** After each query, `query_agent.py` writes the Q&A pair to `agent_insights` in PostgreSQL. Before answering, it checks for unconsumed `analytical_results` from Fabric to enrich responses.

### Work IQ

Extracts work intelligence through an MCP server that queries Dataverse CRM data and classifies signals.

```
Copilot CLI
    │
    ▼ (stdio transport)
MCP Server (server.py)
    ├── query_opportunities ──► Dataverse Web API ──► CRM Data
    │                                                  (or synthetic)
    ├── classify_signals ──► Signal Engine (signals.py)
    │                        ├── wins / losses
    │                        ├── escalations / compete
    │                        ├── products / ip
    │                        └── people / others
    │
    └── generate_digest ──► Full Pipeline
                            (query → classify → summarize)
```

**Authentication:** `DefaultAzureCredential` for Dataverse Web API. Falls back to synthetic data when no credentials are available (demo mode).

**Signal Classification:** Rule-based keyword classifier with 8 categories. Each opportunity or free-text input is matched against keyword patterns and assigned a confidence score.

### Fabric IQ

Builds an analytical pipeline over real e-commerce data synced from PostgreSQL, then writes insights back to complete the data cycle.

```
PostgreSQL (orders, items, payments, agent_insights)
    │
    │  scripts/sync_to_fabric.py (CSV export → REST API load)
    ▼
Lakehouse (Delta Tables)
    ├── orders
    ├── order_items
    ├── order_payments
    ├── agent_insights
    ├── sales_summary (derived)
    ├── delivery_performance (derived)
    ├── payment_analysis (derived)
    ├── top_products (derived)
    └── top_sellers (derived)
    │
    ▼
Fabric Notebook (PySpark)
(aggregation, delivery SLA, payment trends)
    │
    ▼
Fabric Agent (DataAgent)
"What are the delivery trends?"
    │
    ▼
PostgreSQL (analytical_results) ──► Foundry Agent reads on next query
```

**Data Flow:**
1. `scripts/sync_to_fabric.py` exports Postgres tables to CSV and loads into Lakehouse via REST API
2. PySpark notebook creates derived summary, delivery performance, and ranking tables
3. Fabric Agent (DataAgent item) queries the Lakehouse for NL analytics
4. Each Fabric Agent query writes an `analytical_result` back to PostgreSQL
5. Foundry Agent reads these results on its next invocation (completing the cycle)

## Cross-Cutting Concerns

### Authentication

All modules use `DefaultAzureCredential` from `azure-identity`, supporting:
- `az login` for local development
- Managed identity for deployed scenarios
- Service principal via environment variables

### Dependencies

Managed via a single `pyproject.toml` at the repo root:

| Package | Used By |
|---------|---------|
| `azure-identity` | All modules |
| `azure-search-documents` | Foundry IQ, scripts |
| `azure-storage-blob` | Foundry IQ, scripts |
| `azure-ai-projects` | Foundry IQ |
| `asyncpg` | Shared Postgres client |
| `httpx` | All modules (HTTP client) |
| `kaggle` | Scripts (data download) |
| `mcp` | Work IQ (MCP server) |
| `pydantic` | Work IQ (data models) |
| `python-dotenv` | All modules |

Fabric IQ additionally uses PySpark (provided by the Fabric runtime).

### Security

- No API keys stored in code or committed to the repository
- Managed identity preferred over key-based auth
- Kaggle dataset is publicly available (Olist Brazilian E-Commerce — MIT licensed)
- No internal data, email content, or business records included
- `.env` file excluded via `.gitignore`
- PostgreSQL credentials via environment variables, never hardcoded

### Local Development

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your resource values

# Start PostgreSQL (local or Docker)
docker run -d --name iq-postgres -e POSTGRES_USER=iqadmin -e POSTGRES_PASSWORD=localdev -e POSTGRES_DB=microsoftiq -p 5432:5432 postgres:16

# Initialize schema and load Kaggle data
python shared/postgres_client.py --action init
python scripts/download_kaggle.py
python scripts/upload_to_blob.py
python scripts/index_blob_data.py
python shared/postgres_client.py --action load-kaggle

# Run Foundry IQ (transactional)
cd foundry-iq && python src/api_server.py

# Sync to Fabric (analytical)
python scripts/sync_to_fabric.py --workspace microsoft-iq-demo --lakehouse iq-lakehouse

# Query Fabric Agent (writes back to Postgres)
cd fabric-iq && python src/fabric_agent.py --action query --workspace microsoft-iq-demo --name iq-analyst --question "delivery trends?"
```
