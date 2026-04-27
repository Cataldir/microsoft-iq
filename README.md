# Microsoft IQ — Intelligent Knowledge for Agents, Work, and Data

Three hands-on demos showcasing how Microsoft's AI platform makes knowledge accessible to agents, workers, and data pipelines.

## What You'll Build

| Module | What It Demonstrates | Key Services |
|--------|---------------------|--------------|
| **[Foundry IQ](foundry-iq/)** | Create knowledge bases for AI agents via portal and code | Azure AI Foundry, Blob Storage, AI Search |
| **[Work IQ](work-iq/)** | Extract work intelligence with Copilot CLI + MCP servers | Copilot CLI, Dataverse, MCP Protocol |
| **[Fabric IQ](fabric-iq/)** | Orchestrate data pipelines and create reasoning agents | Microsoft Fabric, Eventstream, Lakehouse |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Microsoft IQ Demos                          │
├──────────────────┬──────────────────┬──────────────────────────────┤
│   Foundry IQ     │    Work IQ       │       Fabric IQ              │
│                  │                  │                              │
│  ┌────────────┐  │  ┌────────────┐  │  ┌────────────┐             │
│  │ AI Foundry │  │  │ Copilot CLI│  │  │ Fabric API │             │
│  │   Portal   │  │  │            │  │  │            │             │
│  └─────┬──────┘  │  └─────┬──────┘  │  └─────┬──────┘             │
│        │         │        │         │        │                    │
│  ┌─────▼──────┐  │  ┌─────▼──────┐  │  ┌─────▼──────┐             │
│  │ Knowledge  │  │  │    MCP     │  │  │ Eventstream│             │
│  │   Base     │  │  │  Servers   │  │  │            │             │
│  └─────┬──────┘  │  └─────┬──────┘  │  └─────┬──────┘             │
│        │         │        │         │        │                    │
│  ┌─────▼──────┐  │  ┌─────▼──────┐  │  ┌─────▼──────┐             │
│  │ Blob + AI  │  │  │ Dataverse  │  │  │ Lakehouse  │             │
│  │  Search    │  │  │   + M365   │  │  │            │             │
│  └─────┬──────┘  │  └─────┬──────┘  │  └─────┬──────┘             │
│        │         │        │         │        │                    │
│  ┌─────▼──────┐  │  ┌─────▼──────┐  │  ┌─────▼──────┐             │
│  │  Local UI  │  │  │   Daily    │  │  │  Fabric    │             │
│  │  (Demo)    │  │  │  Digest    │  │  │   Agent    │             │
│  └────────────┘  │  └────────────┘  │  └────────────┘             │
└──────────────────┴──────────────────┴──────────────────────────────┘
```

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) package manager
- **Azure CLI** (`az`) authenticated to your subscription
- **Azure subscription** with:
  - Azure AI Foundry access
  - Azure Blob Storage
  - Azure AI Search
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
# Edit .env with your Azure credentials

# Run any module
cd foundry-iq && python src/provision_datasources.py
cd work-iq && python src/server.py
cd fabric-iq && python src/pipeline_orchestrator.py
```

## Module Details

### 1. Foundry IQ — Knowledge Bases for Agents

Demonstrates creating knowledge bases in Azure AI Foundry, both through the portal UI and programmatically. Shows how to provision Blob Storage and AI Search as knowledge sources, upload documents, and query a grounded agent through a local web interface.

**Key highlights:**
- Portal walkthrough: knowledge base creation, model selection, retrieval configuration
- All knowledge source types: AI Search, Blob Storage, Web (Bing), SharePoint, OneLake
- Code-first: Bicep infrastructure + Python SDK for provisioning and querying
- Local HTML/CSS/JS demo UI

### 2. Work IQ — Work Intelligence with Copilot CLI

Demonstrates extracting work signals using the MCP server pattern connected to Dataverse. Shows how to build a minimal MCP server, query CRM opportunities, classify signals, and generate daily work digests — all sanitized with synthetic data for public demonstration.

**Key highlights:**
- MCP server tool registration and dispatch
- Dataverse Web API integration for CRM data
- Signal classification (wins, losses, escalations, compete signals)
- Copilot CLI prompt templates for daily digests

### 3. Fabric IQ — Data Pipeline Agents

Demonstrates orchestrating data pipelines with Microsoft Fabric and creating agents that reason over ingested data. Uses the Fabric REST API for code-first workspace management, Eventstream for real-time ingestion, and Lakehouse for unified analytics.

**Key highlights:**
- Fabric REST API for programmatic workspace management
- Eventstream configuration for real-time data flow
- Lakehouse as the unified storage layer
- Fabric Agent for reasoning over structured data
- KQL for time-series analytics

## License

MIT

## Author

Ricardo Cataldi — Sao Paulo, Brazil
