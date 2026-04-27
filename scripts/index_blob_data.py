"""Index Kaggle CSV data from Blob Storage into Azure AI Search.

Reads product and review CSVs from blob storage, creates a rich search index
with product descriptions, review text, and metadata, then bulk-loads documents.

This replaces the generic markdown indexer with structured e-commerce data
that the Foundry agent can reason over.

Usage:
    python scripts/index_blob_data.py
    python scripts/index_blob_data.py --container kaggle-data --index ecommerce-knowledge
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _read_csv_from_blob(blob_service: BlobServiceClient, container: str, blob_name: str) -> list[dict]:
    """Download a CSV blob and parse it into a list of dicts."""
    container_client = blob_service.get_container_client(container)
    blob_client = container_client.get_blob_client(blob_name)
    data = blob_client.download_blob().readall().decode("utf-8")
    reader = csv.DictReader(io.StringIO(data))
    return list(reader)


def _stable_id(*parts: str) -> str:
    """Generate a stable document ID from concatenated parts."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_index(search_endpoint: str, index_name: str, credential) -> None:
    """Create or update the AI Search index for e-commerce data."""
    client = SearchIndexClient(endpoint=search_endpoint, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True, sortable=True),
        SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="score", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True),
    ]

    index = SearchIndex(name=index_name, fields=fields)
    client.create_or_update_index(index)
    print(f"Index created/updated: {index_name}")


def index_products(
    blob_service: BlobServiceClient,
    search_client: SearchClient,
    container: str,
    translations: dict[str, str],
) -> int:
    """Index product records as search documents."""
    products = _read_csv_from_blob(blob_service, container, "olist_products_dataset.csv")

    docs = []
    for p in products:
        product_id = p.get("product_id", "")
        cat_raw = p.get("product_category_name", "unknown")
        category = translations.get(cat_raw, cat_raw)

        # Build a rich text description from available fields
        name_length = p.get("product_name_lenght", "0")
        desc_length = p.get("product_description_lenght", "0")
        weight = p.get("product_weight_g", "0")
        photos = p.get("product_photos_qty", "0")

        content = (
            f"Product in category: {category}. "
            f"Name length: {name_length} chars, description length: {desc_length} chars. "
            f"Weight: {weight}g. Photos: {photos}. "
            f"Dimensions: {p.get('product_length_cm', '?')}x{p.get('product_width_cm', '?')}x{p.get('product_height_cm', '?')} cm."
        )

        docs.append({
            "id": _stable_id("product", product_id),
            "content": content,
            "title": f"Product {product_id[:8]} — {category}",
            "doc_type": "product",
            "category": category,
            "score": 0.0,
            "source_file": "olist_products_dataset.csv",
        })

    # Batch upload in chunks of 1000
    total = 0
    for i in range(0, len(docs), 1000):
        batch = docs[i : i + 1000]
        search_client.upload_documents(documents=batch)
        total += len(batch)
        print(f"  Products indexed: {total}/{len(docs)}")

    return total


def index_reviews(
    blob_service: BlobServiceClient,
    search_client: SearchClient,
    container: str,
) -> int:
    """Index review records as search documents."""
    reviews = _read_csv_from_blob(blob_service, container, "olist_order_reviews_dataset.csv")

    docs = []
    for r in reviews:
        review_id = r.get("review_id", "")
        title = r.get("review_comment_title", "") or "No title"
        message = r.get("review_comment_message", "") or "No comment"
        score = float(r.get("review_score", "0") or "0")

        if not message or message == "No comment":
            continue  # Skip reviews without text

        content = f"Review (score {score}/5): {title}. {message}"

        docs.append({
            "id": _stable_id("review", review_id, r.get("order_id", "")),
            "content": content,
            "title": title[:200],
            "doc_type": "review",
            "category": "review",
            "score": score,
            "source_file": "olist_order_reviews_dataset.csv",
        })

    total = 0
    for i in range(0, len(docs), 1000):
        batch = docs[i : i + 1000]
        search_client.upload_documents(documents=batch)
        total += len(batch)
        print(f"  Reviews indexed: {total}/{len(docs)}")

    return total


def main():
    parser = argparse.ArgumentParser(description="Index Kaggle CSV data into AI Search")
    parser.add_argument("--container", default="kaggle-data", help="Blob container with CSV files")
    parser.add_argument("--index", default="ecommerce-knowledge", help="AI Search index name")
    args = parser.parse_args()

    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    storage_account = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
    credential = DefaultAzureCredential()

    blob_service = BlobServiceClient(
        account_url=f"https://{storage_account}.blob.core.windows.net",
        credential=credential,
    )

    # Load category translations
    try:
        translations_raw = _read_csv_from_blob(blob_service, args.container, "product_category_name_translation.csv")
        translations = {
            row["product_category_name"]: row["product_category_name_english"]
            for row in translations_raw
        }
        print(f"Loaded {len(translations)} category translations")
    except Exception:
        translations = {}
        print("Category translations not found — using raw names")

    # Create index
    create_index(search_endpoint, args.index, credential)

    # Index documents
    search_client = SearchClient(endpoint=search_endpoint, index_name=args.index, credential=credential)

    products_count = index_products(blob_service, search_client, args.container, translations)
    reviews_count = index_reviews(blob_service, search_client, args.container)

    print(f"\nIndexing complete: {products_count} products + {reviews_count} reviews in '{args.index}'")


if __name__ == "__main__":
    main()
