"""Upload raw CSV files from Kaggle to Azure Blob Storage.

Uploads all CSV files from the local data/raw/ directory to a configured
blob container, organized by prefix for downstream consumption by both
AI Search (Foundry IQ) and Fabric IQ pipelines.

Usage:
    python scripts/upload_to_blob.py
    python scripts/upload_to_blob.py --source data/raw --container kaggle-data
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def upload_csvs(source_dir: str, container_name: str) -> dict[str, int]:
    """Upload all CSV files from source_dir to blob storage."""
    account_name = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
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

    source = Path(source_dir)
    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}. Run download_kaggle.py first.")

    uploaded = {}
    for csv_file in sorted(source.glob("*.csv")):
        blob_name = csv_file.name
        blob_client = container_client.get_blob_client(blob_name)

        file_size = csv_file.stat().st_size
        with csv_file.open("rb") as f:
            blob_client.upload_blob(f, overwrite=True)

        uploaded[blob_name] = file_size
        print(f"  Uploaded: {blob_name} ({file_size:,} bytes)")

    print(f"\n{len(uploaded)} files uploaded to {account_name}/{container_name}")
    return uploaded


def main():
    parser = argparse.ArgumentParser(description="Upload CSV files to Azure Blob Storage")
    parser.add_argument("--source", default="data/raw", help="Source directory with CSV files")
    parser.add_argument("--container", default="kaggle-data", help="Blob container name")
    args = parser.parse_args()

    upload_csvs(args.source, args.container)


if __name__ == "__main__":
    main()
