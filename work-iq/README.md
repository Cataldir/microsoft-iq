# Work IQ — Work Intelligence with Copilot CLI

This module demonstrates extracting work intelligence using the MCP (Model Context Protocol) server pattern connected to Microsoft Dataverse and M365 signals. It mirrors the architecture used in real-world operational automation — sanitized for public demonstration with synthetic data.

## What You'll Learn

1. **MCP server pattern**: Build a minimal MCP server that registers tools for querying work data
2. **Dataverse integration**: Query CRM opportunities, account data, and pipeline status via Web API
3. **Signal classification**: Categorize raw work data into actionable signal types
4. **Prompt-driven digests**: Use Copilot CLI prompt templates to generate daily work summaries

## Architecture

```
Copilot CLI ──→ MCP Server ──→ Dataverse Web API ──→ CRM Data
                    │
                    ├──→ Signal Classifier ──→ Structured Signals
                    │
                    └──→ Daily Digest Generator ──→ Work Summary
```

## How It Works

### 1. MCP Server (`src/server.py`)

A lightweight MCP server that exposes tools:
- `query_opportunities` — Query Dataverse CRM opportunities with filters
- `classify_signals` — Categorize work data into signal types
- `generate_digest` — Produce a structured daily work summary

### 2. Dataverse Client (`src/dataverse_client.py`)

Authenticated client for the Dataverse Web API:
- Uses `DefaultAzureCredential` for managed identity / `az login` auth
- Queries the `opportunity` table with OData filters
- Returns structured opportunity records with account, stage, and contact info

### 3. Signal Classifier (`src/signals.py`)

Categorizes raw work signals into 8 types:
- **wins** — Closed-won deals, successful deployments
- **losses** — Lost opportunities, churn signals
- **escalations** — Issues requiring management attention
- **compete** — Competitive intelligence signals
- **products** — Product feedback, feature requests
- **ip** — Intellectual property contributions
- **people** — Team updates, collaboration signals
- **others** — Uncategorized signals

### 4. Prompt Templates (`prompts/`)

Copilot CLI prompt files that orchestrate the MCP tools:
- `daily-work-digest.prompt.md` — Full daily work intelligence pipeline
- `work-signals.prompt.md` — Signal extraction and classification

## Quick Start

```bash
# Start the MCP server
cd work-iq
python src/server.py

# Or use with Copilot CLI (requires MCP config)
# The server registers on stdio transport
```

### Using with Copilot CLI

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "work-iq": {
      "command": "python",
      "args": ["src/server.py"],
      "cwd": "work-iq"
    }
  }
}
```

## Demo Mode

When `DATAVERSE_ENVIRONMENT_URL` is not set, the server automatically uses **synthetic data** that demonstrates the full pipeline without requiring any Azure/Dataverse credentials. This is the default for public demonstrations.

## Privacy Notice

This demo uses **only synthetic/mock data**. No real CRM records, email content, meeting transcripts, or internal business data is included in this repository.
