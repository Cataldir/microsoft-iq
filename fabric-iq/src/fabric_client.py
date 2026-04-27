"""Fabric REST API client for workspace and Lakehouse management.

Provides programmatic access to Microsoft Fabric resources using the
REST API with DefaultAzureCredential authentication.

Usage:
    python src/fabric_client.py --action create-workspace --name "my-workspace"
    python src/fabric_client.py --action create-lakehouse --workspace "my-workspace" --name "my-lakehouse"
    python src/fabric_client.py --action upload-notebook --workspace "my-workspace" --path notebooks/ingest_and_analyze.py
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricClient:
    """Client for the Microsoft Fabric REST API."""

    def __init__(self):
        self._credential = DefaultAzureCredential()

    def _headers(self) -> dict[str, str]:
        token = self._credential.get_token(FABRIC_SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

    # ── Workspace operations ──

    def list_workspaces(self) -> list[dict]:
        """List all accessible Fabric workspaces."""
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{FABRIC_API}/workspaces", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("value", [])

    def find_workspace(self, name: str) -> dict | None:
        """Find a workspace by display name."""
        workspaces = self.list_workspaces()
        return next((w for w in workspaces if w.get("displayName") == name), None)

    def create_workspace(self, name: str, description: str = "") -> dict:
        """Create a new Fabric workspace."""
        existing = self.find_workspace(name)
        if existing:
            print(f"Workspace '{name}' already exists (id: {existing['id']})")
            return existing

        body = {"displayName": name}
        if description:
            body["description"] = description

        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{FABRIC_API}/workspaces", headers=self._headers(), json=body)
            resp.raise_for_status()
            workspace = resp.json()
            print(f"Created workspace '{name}' (id: {workspace['id']})")
            return workspace

    # ── Lakehouse operations ──

    def list_lakehouses(self, workspace_id: str) -> list[dict]:
        """List Lakehouses in a workspace."""
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("value", [])

    def find_lakehouse(self, workspace_id: str, name: str) -> dict | None:
        """Find a Lakehouse by display name within a workspace."""
        lakehouses = self.list_lakehouses(workspace_id)
        return next((lh for lh in lakehouses if lh.get("displayName") == name), None)

    def create_lakehouse(self, workspace_id: str, name: str, description: str = "") -> dict:
        """Create a Lakehouse in the specified workspace."""
        existing = self.find_lakehouse(workspace_id, name)
        if existing:
            print(f"Lakehouse '{name}' already exists (id: {existing['id']})")
            return existing

        body = {"displayName": name}
        if description:
            body["description"] = description

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
                headers=self._headers(),
                json=body,
            )
            # 201 Created or 202 Accepted (long-running)
            if resp.status_code == 202:
                return self._poll_operation(resp, workspace_id, "Lakehouse", name)
            resp.raise_for_status()
            lakehouse = resp.json()
            print(f"Created Lakehouse '{name}' (id: {lakehouse['id']})")
            return lakehouse

    def list_tables(self, workspace_id: str, lakehouse_id: str) -> list[dict]:
        """List tables in a Lakehouse."""
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    # ── Notebook operations ──

    def upload_notebook(self, workspace_id: str, notebook_path: str) -> dict:
        """Upload a Python notebook file to a Fabric workspace."""
        path = Path(notebook_path)
        if not path.exists():
            raise FileNotFoundError(f"Notebook not found: {path}")

        content = path.read_text(encoding="utf-8")
        display_name = path.stem

        # Fabric expects notebook content as base64-encoded payload
        notebook_payload = {
            "cells": _python_to_notebook_cells(content),
            "metadata": {
                "language_info": {"name": "python"},
                "a]]365_lakehouse": {"default_lakehouse_workspace_id": workspace_id},
            },
        }
        encoded = base64.b64encode(json.dumps(notebook_payload).encode()).decode()

        body = {
            "displayName": display_name,
            "type": "Notebook",
            "definition": {
                "format": "ipynb",
                "parts": [
                    {
                        "path": "notebook-content.py",
                        "payload": encoded,
                        "payloadType": "InlineBase64",
                    }
                ],
            },
        }

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/items",
                headers=self._headers(),
                json=body,
            )
            if resp.status_code == 202:
                return self._poll_operation(resp, workspace_id, "Notebook", display_name)
            resp.raise_for_status()
            notebook = resp.json()
            print(f"Uploaded notebook '{display_name}' (id: {notebook['id']})")
            return notebook

    # ── Polling for long-running operations ──

    def _poll_operation(self, resp: httpx.Response, workspace_id: str, item_type: str, name: str) -> dict:
        """Poll a long-running operation until completion."""
        location = resp.headers.get("Location", "")
        retry_after = int(resp.headers.get("Retry-After", "5"))

        print(f"Creating {item_type} '{name}' (long-running operation)...")

        for _ in range(30):  # Max 150 seconds
            time.sleep(retry_after)
            with httpx.Client(timeout=30) as client:
                poll_resp = client.get(location, headers=self._headers())
                if poll_resp.status_code == 200:
                    result = poll_resp.json()
                    status = result.get("status", "")
                    if status in ("Succeeded", "succeeded"):
                        print(f"Created {item_type} '{name}' successfully")
                        return result
                    if status in ("Failed", "failed"):
                        raise RuntimeError(f"Failed to create {item_type} '{name}': {result}")

        raise TimeoutError(f"Timed out creating {item_type} '{name}'")


def _python_to_notebook_cells(content: str) -> list[dict]:
    """Split Python source into notebook cells separated by '# %%' markers."""
    sections = content.split("# %%")
    cells = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        cell_type = "markdown" if section.startswith('"""') else "code"
        if cell_type == "markdown":
            # Strip triple-quote markers for markdown cells
            section = section.strip('"\n ')

        cells.append({
            "cell_type": cell_type,
            "source": section.split("\n"),
            "metadata": {},
            "outputs": [],
        })

    return cells or [{"cell_type": "code", "source": content.split("\n"), "metadata": {}, "outputs": []}]


# ── CLI entry point ──

def main():
    parser = argparse.ArgumentParser(description="Fabric REST API client")
    parser.add_argument("--action", required=True, choices=["create-workspace", "create-lakehouse", "list-tables", "upload-notebook"])
    parser.add_argument("--name", help="Resource name")
    parser.add_argument("--workspace", help="Workspace display name")
    parser.add_argument("--path", help="File path (for notebook upload)")
    args = parser.parse_args()

    client = FabricClient()

    if args.action == "create-workspace":
        if not args.name:
            parser.error("--name required for create-workspace")
        result = client.create_workspace(args.name, description="Microsoft IQ demo workspace")
        print(json.dumps(result, indent=2))

    elif args.action == "create-lakehouse":
        if not args.workspace or not args.name:
            parser.error("--workspace and --name required for create-lakehouse")
        ws = client.find_workspace(args.workspace)
        if not ws:
            print(f"Workspace '{args.workspace}' not found")
            sys.exit(1)
        result = client.create_lakehouse(ws["id"], args.name, description="IQ demo Lakehouse")
        print(json.dumps(result, indent=2))

    elif args.action == "list-tables":
        if not args.workspace or not args.name:
            parser.error("--workspace and --name required for list-tables")
        ws = client.find_workspace(args.workspace)
        if not ws:
            print(f"Workspace '{args.workspace}' not found")
            sys.exit(1)
        lh = client.find_lakehouse(ws["id"], args.name)
        if not lh:
            print(f"Lakehouse '{args.name}' not found")
            sys.exit(1)
        tables = client.list_tables(ws["id"], lh["id"])
        print(json.dumps(tables, indent=2))

    elif args.action == "upload-notebook":
        if not args.workspace or not args.path:
            parser.error("--workspace and --path required for upload-notebook")
        ws = client.find_workspace(args.workspace)
        if not ws:
            print(f"Workspace '{args.workspace}' not found")
            sys.exit(1)
        result = client.upload_notebook(ws["id"], args.path)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
