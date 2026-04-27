"""Download a Kaggle dataset and extract it to a local directory.

Uses the Kaggle API (requires ~/.kaggle/kaggle.json or KAGGLE_USERNAME + KAGGLE_KEY env vars).

Default dataset: Brazilian E-Commerce by Olist (olistbr/brazilian-ecommerce)
  - olist_orders_dataset.csv
  - olist_order_items_dataset.csv
  - olist_order_payments_dataset.csv
  - olist_order_reviews_dataset.csv
  - olist_products_dataset.csv
  - olist_customers_dataset.csv
  - olist_sellers_dataset.csv
  - product_category_name_translation.csv

Usage:
    python scripts/download_kaggle.py
    python scripts/download_kaggle.py --dataset olistbr/brazilian-ecommerce --output data/raw
"""

from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

DEFAULT_DATASET = "olistbr/brazilian-ecommerce"
DEFAULT_OUTPUT = "data/raw"


def download_dataset(dataset: str, output_dir: str) -> list[str]:
    """Download and extract a Kaggle dataset."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        raise SystemExit(
            "kaggle package not installed. Run: uv pip install kaggle\n"
            "Also ensure ~/.kaggle/kaggle.json exists or set KAGGLE_USERNAME + KAGGLE_KEY env vars."
        )

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()

    print(f"Downloading dataset: {dataset}")
    api.dataset_download_files(dataset, path=str(out), unzip=True)

    files = sorted(str(f.relative_to(out)) for f in out.rglob("*.csv"))
    print(f"Extracted {len(files)} CSV files to {out}/")
    for f in files:
        print(f"  {f}")

    return files


def main():
    parser = argparse.ArgumentParser(description="Download Kaggle dataset")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Kaggle dataset slug (owner/name)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output directory")
    args = parser.parse_args()

    download_dataset(args.dataset, args.output)


if __name__ == "__main__":
    main()
