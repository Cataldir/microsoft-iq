# Foundry IQ — Knowledge Bases for AI Agents

This module demonstrates how to create knowledge bases in Azure AI Foundry that ground agents with real data from Blob Storage, AI Search, and other sources.

## What You'll Learn

1. **Portal experience**: Create a knowledge base directly in Azure AI Foundry portal
2. **Knowledge sources**: All supported types — AI Search, Blob Storage, Web (Bing), SharePoint Remote, SharePoint Indexed, OneLake
3. **Code-first provisioning**: Deploy infrastructure with Bicep and populate with Python
4. **Query an agent**: Use the grounded agent through SDK and a local web UI

## Prerequisites

- Azure subscription with AI Foundry deployed
- Azure CLI authenticated (`az login`)
- Python 3.11+ with dependencies installed

## Portal Walkthrough

### Step 1: Create a Knowledge Base

1. Navigate to your Azure AI Foundry project in the portal
2. Go to **Knowledge Bases** → **Create**
3. Configure:
   - **Name**: `knowledgebase-products` (or any descriptive name)
   - **Chat completions model**: `gpt-5-nano` (or your preferred model)
   - **Retrieval reasoning effort**: `Minimal` (for extractive lookups) or `High` (for complex queries)
   - **Output mode**: `Extractive data` (returns verbatim chunks) or `Generated` (synthesizes answers)
   - **Retrieval instructions**: Describe what the knowledge base contains and how to use it

### Step 2: Add Knowledge Sources

Click **Create new** to add data sources. Available types:

| Source Type | Best For | Notes |
|-------------|----------|-------|
| **Azure AI Search Index** | Enterprise-scale search over structured/unstructured data | Recommended for production workloads |
| **Azure Blob Storage** | Documents and files (PDF, DOCX, TXT, MD) | Auto-indexed into AI Search |
| **Web** | Real-time web content via Bing | Grounding with live internet data |
| **Microsoft SharePoint (Remote)** | M365 governance-compliant content retrieval | Content retrieved without re-indexing |
| **Microsoft SharePoint (Indexed)** | Custom pipelines over SharePoint content | Indexed into AI Search for custom search |
| **Microsoft OneLake** | Unstructured data from Fabric OneLake | Bridge between Fabric and Foundry |

### Step 3: Authentication

When API key authentication is disabled (recommended for production):
- The search service uses **managed identity** to authenticate
- Ensure the search service's managed identity has the **Cognitive Services User** role on the AI Foundry resource

## Code-First Experience

### Deploy Infrastructure

```bash
# Deploy Blob Storage + AI Search + AI Foundry resources
az deployment group create \
  --resource-group $AZURE_RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

### Provision and Upload

```bash
# Upload sample documents to Blob Storage
python src/upload_documents.py

# Create and populate AI Search index
python src/provision_datasources.py
```

### Query the Agent

```bash
# Query via CLI
python src/query_agent.py "What products support real-time analytics?"

# Or run the local web UI
cd ui && python -m http.server 8080
# Open http://localhost:8080
```

## Architecture

```
Azure Blob Storage          Azure AI Search
  (documents)          →     (search index)
                                    │
                                    ▼
                          Azure AI Foundry
                          (knowledge base)
                                    │
                                    ▼
                            Foundry Agent
                          (grounded answers)
                                    │
                                    ▼
                            Local Web UI
```
