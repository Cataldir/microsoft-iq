"""Upload sample documents to Azure Blob Storage for the Foundry IQ knowledge base."""

from __future__ import annotations

import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SAMPLE_DOCUMENTS = [
    {
        "name": "product-ai-search.md",
        "content": (
            "# Azure AI Search\n\n"
            "Azure AI Search is an enterprise-scale search service for app development. "
            "It provides vector search, semantic ranking, and hybrid retrieval over structured "
            "and unstructured data. Key capabilities include:\n\n"
            "- **Vector search**: Embed documents and queries into vector space for semantic similarity.\n"
            "- **Hybrid search**: Combine keyword (BM25) and vector search for best-of-both retrieval.\n"
            "- **Semantic ranker**: Re-rank results using a cross-encoder model for higher relevance.\n"
            "- **Integrated vectorization**: Built-in skills to chunk, embed, and index documents.\n"
            "- **Knowledge store**: Project enriched data into tables and blob projections.\n\n"
            "Pricing starts at the Basic tier (~$75/month) with 2 GB storage and 15 GB bandwidth.\n\n"
            "Best for: RAG applications, e-commerce search, document discovery, knowledge bases."
        ),
    },
    {
        "name": "product-blob-storage.md",
        "content": (
            "# Azure Blob Storage\n\n"
            "Azure Blob Storage provides massively scalable object storage for unstructured data. "
            "It supports hot, cool, cold, and archive access tiers for cost optimization.\n\n"
            "Key features:\n"
            "- **Lifecycle management**: Automatically transition blobs between tiers based on age or access.\n"
            "- **Immutable storage**: WORM (Write Once, Read Many) for compliance.\n"
            "- **Versioning**: Track and restore previous versions of blobs.\n"
            "- **Soft delete**: Recover accidentally deleted blobs within a retention period.\n"
            "- **Data Lake Storage Gen2**: Hierarchical namespace for analytics workloads.\n\n"
            "Pricing: Hot tier ~$0.018/GB/month, Cool ~$0.01/GB/month, Archive ~$0.00099/GB/month.\n\n"
            "Best for: Media storage, backups, data lake, document repositories, knowledge base sources."
        ),
    },
    {
        "name": "product-ai-foundry.md",
        "content": (
            "# Azure AI Foundry\n\n"
            "Azure AI Foundry is the unified platform for building, evaluating, and deploying "
            "AI applications and agents. It combines model catalog access, prompt engineering, "
            "agent orchestration, and knowledge base management.\n\n"
            "Key capabilities:\n"
            "- **Model catalog**: Access 11,000+ models including GPT-4o, GPT-5, Phi, Llama, and more.\n"
            "- **Agent builder**: Create agents with tools, knowledge bases, and code interpreters.\n"
            "- **Knowledge bases**: Ground agents with data from Blob Storage, AI Search, SharePoint, OneLake, and the web.\n"
            "- **Evaluation**: Built-in metrics for groundedness, relevance, coherence, and safety.\n"
            "- **Prompt flow**: Visual orchestration for complex AI workflows.\n\n"
            "Knowledge base sources supported:\n"
            "1. Azure AI Search Index — enterprise-scale search\n"
            "2. Azure Blob Storage — documents and files\n"
            "3. Web (Bing) — real-time internet grounding\n"
            "4. Microsoft SharePoint (Remote) — M365 governance-compliant\n"
            "5. Microsoft SharePoint (Indexed) — custom search pipelines\n"
            "6. Microsoft OneLake — unstructured Fabric data\n\n"
            "Best for: AI agent development, RAG applications, enterprise AI platforms."
        ),
    },
    {
        "name": "product-fabric.md",
        "content": (
            "# Microsoft Fabric\n\n"
            "Microsoft Fabric is a unified analytics platform that combines data engineering, "
            "data science, real-time analytics, and business intelligence.\n\n"
            "Key components:\n"
            "- **Lakehouse**: Unified storage combining data lake flexibility with warehouse structure.\n"
            "- **Eventstream**: Real-time data ingestion from Event Hubs, Kafka, IoT Hub, and CDC.\n"
            "- **KQL Database / Eventhouse**: High-velocity time-series analytics with Kusto Query Language.\n"
            "- **Data Activator**: Trigger-based automation for real-time alerts and actions.\n"
            "- **Fabric Agent**: AI agent that reasons over Lakehouse and warehouse data.\n"
            "- **Notebooks**: PySpark and SQL notebooks for data transformation.\n\n"
            "Best for: Enterprise analytics, real-time dashboards, data pipeline orchestration, AI agents over data."
        ),
    },
    {
        "name": "product-copilot-cli.md",
        "content": (
            "# GitHub Copilot CLI\n\n"
            "GitHub Copilot CLI brings AI assistance to the terminal. It can explain commands, "
            "suggest completions, and execute complex workflows via natural language.\n\n"
            "Key capabilities:\n"
            "- **Command suggestion**: Describe what you want, get the exact command.\n"
            "- **MCP integration**: Connect to Model Context Protocol servers for tool access.\n"
            "- **Workflow execution**: Run multi-step operations with structured prompts.\n"
            "- **Context awareness**: Understands your current directory, git state, and environment.\n\n"
            "The MCP server pattern allows Copilot CLI to:\n"
            "1. Query Dataverse CRM data\n"
            "2. Extract M365 signals (emails, meetings, chats)\n"
            "3. Collect GitHub contributions\n"
            "4. Classify work signals into actionable categories\n\n"
            "Best for: Developer productivity, work intelligence extraction, operational automation."
        ),
    },
]


def upload_documents() -> None:
    """Upload sample product documents to Azure Blob Storage."""
    account_name = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "knowledge-docs")

    credential = DefaultAzureCredential()
    blob_service = BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=credential,
    )

    container_client = blob_service.get_container_client(container_name)
    try:
        container_client.get_container_properties()
    except Exception:
        container_client.create_container()
        print(f"Created container: {container_name}")

    for doc in SAMPLE_DOCUMENTS:
        blob_client = container_client.get_blob_client(doc["name"])
        blob_client.upload_blob(doc["content"].encode("utf-8"), overwrite=True)
        print(f"Uploaded: {doc['name']}")

    print(f"\n{len(SAMPLE_DOCUMENTS)} documents uploaded to {account_name}/{container_name}")


if __name__ == "__main__":
    upload_documents()
