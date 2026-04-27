"""Fabric Agent — Create and query a Fabric Agent over Lakehouse data.

Uses the Fabric REST API to create a Fabric Agent item that connects to
a Lakehouse and answers natural-language questions about the data.

Usage:
    python src/fabric_agent.py --action create --workspace "my-workspace" --lakehouse "my-lakehouse" --name "my-agent"
    python src/fabric_agent.py --action query --workspace "my-workspace" --name "my-agent" --question "Top products?"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import httpx
from azure.identity import DefaultAzureCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


class FabricAgentManager:
    """Manages Fabric Agent creation and queries."""

    def __init__(self):
        self._credential = DefaultAzureCredential()

    def _headers(self) -> dict[str, str]:
        token = self._credential.get_token(FABRIC_SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

    def _find_workspace(self, name: str) -> dict | None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{FABRIC_API}/workspaces", headers=self._headers())
            resp.raise_for_status()
            workspaces = resp.json().get("value", [])
        return next((w for w in workspaces if w.get("displayName") == name), None)

    def _find_lakehouse(self, workspace_id: str, name: str) -> dict | None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
                headers=self._headers(),
            )
            resp.raise_for_status()
            lakehouses = resp.json().get("value", [])
        return next((lh for lh in lakehouses if lh.get("displayName") == name), None)

    def _find_item(self, workspace_id: str, name: str, item_type: str = "DataAgent") -> dict | None:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{workspace_id}/items",
                headers=self._headers(),
                params={"type": item_type},
            )
            resp.raise_for_status()
            items = resp.json().get("value", [])
        return next((i for i in items if i.get("displayName") == name), None)

    def create_agent(
        self,
        workspace_id: str,
        lakehouse_id: str,
        name: str,
        instructions: str = "",
    ) -> dict:
        """Create a Fabric Agent (DataAgent item) connected to a Lakehouse."""
        existing = self._find_item(workspace_id, name, "DataAgent")
        if existing:
            print(f"Agent '{name}' already exists (id: {existing['id']})")
            return existing

        if not instructions:
            instructions = (
                "You are an analytics assistant. Answer questions about retail sales data "
                "in the connected Lakehouse. Use the sales_transactions and products tables. "
                "Provide specific numbers, trends, and comparisons. Format responses with "
                "bullet points and tables when presenting multiple data points."
            )

        body = {
            "displayName": name,
            "type": "DataAgent",
            "description": "IQ demo agent for Lakehouse analytics",
            "definition": {
                "parts": [
                    {
                        "path": "agent-config.json",
                        "payload": json.dumps({
                            "instructions": instructions,
                            "dataSources": [
                                {
                                    "type": "Lakehouse",
                                    "itemId": lakehouse_id,
                                    "workspaceId": workspace_id,
                                }
                            ],
                        }),
                        "payloadType": "InlineBase64",
                    }
                ],
            },
        }

        # Encode the config payload as base64
        import base64
        config_json = json.dumps({
            "instructions": instructions,
            "dataSources": [
                {
                    "type": "Lakehouse",
                    "itemId": lakehouse_id,
                    "workspaceId": workspace_id,
                }
            ],
        })
        body["definition"]["parts"][0]["payload"] = base64.b64encode(config_json.encode()).decode()

        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/items",
                headers=self._headers(),
                json=body,
            )
            if resp.status_code == 202:
                return self._poll_operation(resp, name)
            resp.raise_for_status()
            agent = resp.json()
            print(f"Created Fabric Agent '{name}' (id: {agent['id']})")
            return agent

    def query_agent(self, workspace_id: str, agent_id: str, question: str) -> dict:
        """Send a question to a Fabric Agent and return the response."""
        body = {
            "messages": [
                {"role": "user", "content": question}
            ],
        }

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{FABRIC_API}/workspaces/{workspace_id}/items/{agent_id}/jobs/instances",
                headers=self._headers(),
                json={"executionData": body},
            )

            if resp.status_code == 202:
                # Long-running — poll for result
                return self._poll_query(resp)

            resp.raise_for_status()
            return resp.json()

    def _poll_operation(self, resp: httpx.Response, name: str) -> dict:
        """Poll a long-running operation."""
        location = resp.headers.get("Location", "")
        retry_after = int(resp.headers.get("Retry-After", "5"))

        print(f"Creating agent '{name}' (long-running)...")
        for _ in range(30):
            time.sleep(retry_after)
            with httpx.Client(timeout=30) as client:
                poll = client.get(location, headers=self._headers())
                if poll.status_code == 200:
                    result = poll.json()
                    if result.get("status") in ("Succeeded", "succeeded"):
                        print(f"Agent '{name}' created successfully")
                        return result
                    if result.get("status") in ("Failed", "failed"):
                        raise RuntimeError(f"Agent creation failed: {result}")

        raise TimeoutError(f"Timed out creating agent '{name}'")

    def _poll_query(self, resp: httpx.Response) -> dict:
        """Poll a long-running query job."""
        location = resp.headers.get("Location", "")
        retry_after = int(resp.headers.get("Retry-After", "3"))

        for _ in range(40):
            time.sleep(retry_after)
            with httpx.Client(timeout=30) as client:
                poll = client.get(location, headers=self._headers())
                if poll.status_code == 200:
                    result = poll.json()
                    if result.get("status") in ("Succeeded", "succeeded"):
                        return result
                    if result.get("status") in ("Failed", "failed"):
                        return {"error": "Query failed", "detail": result}

        return {"error": "Query timed out"}


# ── CLI entry point ──

def main():
    parser = argparse.ArgumentParser(description="Fabric Agent manager")
    parser.add_argument("--action", required=True, choices=["create", "query", "list"])
    parser.add_argument("--workspace", required=True, help="Workspace display name")
    parser.add_argument("--lakehouse", help="Lakehouse display name (for create)")
    parser.add_argument("--name", help="Agent display name")
    parser.add_argument("--question", help="Question to ask the agent (for query)")
    parser.add_argument("--instructions", help="Custom agent instructions (for create)")
    args = parser.parse_args()

    mgr = FabricAgentManager()

    ws = mgr._find_workspace(args.workspace)
    if not ws:
        print(f"Workspace '{args.workspace}' not found")
        sys.exit(1)

    if args.action == "create":
        if not args.lakehouse or not args.name:
            parser.error("--lakehouse and --name required for create")
        lh = mgr._find_lakehouse(ws["id"], args.lakehouse)
        if not lh:
            print(f"Lakehouse '{args.lakehouse}' not found")
            sys.exit(1)
        result = mgr.create_agent(ws["id"], lh["id"], args.name, instructions=args.instructions or "")
        print(json.dumps(result, indent=2))

    elif args.action == "query":
        if not args.name or not args.question:
            parser.error("--name and --question required for query")
        agent = mgr._find_item(ws["id"], args.name, "DataAgent")
        if not agent:
            print(f"Agent '{args.name}' not found")
            sys.exit(1)
        result = mgr.query_agent(ws["id"], agent["id"], args.question)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.action == "list":
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{FABRIC_API}/workspaces/{ws['id']}/items",
                headers=mgr._headers(),
                params={"type": "DataAgent"},
            )
            resp.raise_for_status()
            agents = resp.json().get("value", [])
        if agents:
            for a in agents:
                print(f"  {a['displayName']} (id: {a['id']})")
        else:
            print("No Fabric Agents found in this workspace")


if __name__ == "__main__":
    main()
