"""Provision Azure AI Search index with a data source connected to Blob Storage."""

from __future__ import annotations

import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexer,
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SimpleField,
)
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def provision_search_index() -> None:
    """Create an AI Search index, data source, and indexer pointing at Blob Storage."""
    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "microsoft-iq-products")
    storage_account = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "knowledge-docs")

    credential = DefaultAzureCredential()

    # ── Create the search index ──────────────────
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SimpleField(
            name="metadata_storage_path",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
    ]

    index = SearchIndex(name=index_name, fields=fields)
    result = index_client.create_or_update_index(index)
    print(f"Index created/updated: {result.name}")

    # ── Create data source connection ────────────
    indexer_client = SearchIndexerClient(endpoint=search_endpoint, credential=credential)

    # Use managed identity connection string (no keys)
    connection_string = (
        f"ResourceId=/subscriptions/{os.environ['AZURE_SUBSCRIPTION_ID']}"
        f"/resourceGroups/{os.environ['AZURE_RESOURCE_GROUP']}"
        f"/providers/Microsoft.Storage/storageAccounts/{storage_account};"
    )

    data_source = SearchIndexerDataSourceConnection(
        name=f"{index_name}-datasource",
        type="azureblob",
        connection_string=connection_string,
        container=SearchIndexerDataContainer(name=container_name),
    )
    result = indexer_client.create_or_update_data_source_connection(data_source)
    print(f"Data source created/updated: {result.name}")

    # ── Create indexer ───────────────────────────
    indexer = SearchIndexer(
        name=f"{index_name}-indexer",
        data_source_name=data_source.name,
        target_index_name=index_name,
        field_mappings=[],
    )
    result = indexer_client.create_or_update_indexer(indexer)
    print(f"Indexer created/updated: {result.name}")

    # Run the indexer
    indexer_client.run_indexer(indexer.name)
    print(f"Indexer '{indexer.name}' started. Documents will be indexed shortly.")


if __name__ == "__main__":
    provision_search_index()
