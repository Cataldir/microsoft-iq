# Microsoft IQ — Architecture

## System Overview

Microsoft IQ is a three-module demo walkthrough that demonstrates how to build intelligent applications using Azure AI Foundry, Microsoft Fabric, and MCP (Model Context Protocol). Each module is self-contained and can be run independently.

```
┌─────────────────────────────────────────────────────────────┐
│                      Microsoft IQ                           │
├───────────────────┬───────────────────┬─────────────────────┤
│   Foundry IQ      │    Work IQ        │    Fabric IQ        │
│                   │                   │                     │
│  Azure AI Foundry │  MCP Server       │  Fabric REST API    │
│  + AI Search      │  + Dataverse      │  + Lakehouse        │
│  + Blob Storage   │  + Copilot CLI    │  + Eventstream      │
│  + Local Chat UI  │  + Signal Engine  │  + Fabric Agent     │
└───────────────────┴───────────────────┴─────────────────────┘
```

## Module Architectures

### Foundry IQ

Deploys a knowledge-grounded AI agent using Azure AI Foundry portal and code-first Bicep.

```
Sample Docs (.md)
    │
    ▼
Azure Blob Storage ◄── Managed Identity ──► Azure AI Search
    │                                           │
    │  indexer + data source                    │
    └───────────────────────────────────────────┘
                        │
                        ▼
              Azure AI Foundry Agent
              (Knowledge Base: AI Search)
                        │
                        ▼
                Local Chat UI (HTML/JS)
                        │
                  api_server.py (HTTP)
                        │
                  query_agent.py (SDK)
```

**Infrastructure (Bicep):**
- Storage Account with `knowledge-docs` container
- AI Search service (Basic tier, SystemAssigned identity)
- AI Services account (API key auth disabled)
- Role assignments: Cognitive Services User, Storage Blob Data Reader

**Authentication:** Managed identity chain — AI Search authenticates to Blob Storage, Foundry authenticates to AI Search, all without API keys.

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

Builds a data pipeline that ingests retail data into a Lakehouse and creates a Fabric Agent for natural-language analytics.

```
Sample Data Generator
    │ (1,000 sales + 50 products)
    ▼
Eventstream ──► Lakehouse (Delta Tables)
                    │
                    ├── sales_transactions
                    ├── products
                    ├── sales_summary (derived)
                    └── top_products (derived)
                    │
                    ▼
            Fabric Notebook (PySpark)
            (aggregation, ranking)
                    │
                    ▼
            Fabric Agent (DataAgent)
            "What are top products by revenue?"
```

**Data Flow:**
1. `pipeline_orchestrator.py` generates synthetic retail data (deterministic seed)
2. Data is loaded into Lakehouse tables via the Fabric REST API
3. PySpark notebook creates derived summary and ranking tables
4. Fabric Agent (DataAgent item) connects to the Lakehouse for NL queries

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
| `azure-search-documents` | Foundry IQ |
| `azure-storage-blob` | Foundry IQ |
| `azure-ai-projects` | Foundry IQ |
| `httpx` | All modules (HTTP client) |
| `mcp` | Work IQ (MCP server) |
| `pydantic` | Work IQ (data models) |
| `python-dotenv` | All modules |

Fabric IQ additionally uses PySpark (provided by the Fabric runtime).

### Security

- No API keys stored in code or committed to the repository
- Managed identity preferred over key-based auth
- Synthetic/mock data for all public demos
- `.env` file excluded via `.gitignore`
- No internal data, email content, or business records included

### Local Development

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your resource values

# Run any module
cd foundry-iq && python src/api_server.py     # Local chat UI
cd work-iq && python src/server.py             # MCP server
cd fabric-iq && python src/fabric_client.py    # Fabric API
```
