"""Dataverse Web API client for querying CRM opportunity data.

Uses DefaultAzureCredential for authentication (supports az login, managed identity,
and service principal). Falls back to synthetic data when credentials are unavailable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATAVERSE_SCOPE = "https://dynamics.com/.default"


@dataclass
class Opportunity:
    """Represents a CRM opportunity record."""

    id: str
    name: str
    account: str
    stage: str
    status: str
    estimated_value: float
    close_date: str
    contacts: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "account": self.account,
            "stage": self.stage,
            "status": self.status,
            "estimated_value": self.estimated_value,
            "close_date": self.close_date,
            "contacts": self.contacts,
            "notes": self.notes,
        }


# ── Synthetic data for demo mode ─────────────

SYNTHETIC_OPPORTUNITIES = [
    Opportunity(
        id="opp-001",
        name="Contoso AI Platform Modernization",
        account="Contoso Ltd",
        stage="Proposal",
        status="open",
        estimated_value=450_000,
        close_date="2026-06-30",
        contacts=["Alex Johnson (CTO)", "Maria Santos (VP Engineering)"],
        notes="Customer evaluating Azure AI Foundry vs AWS Bedrock. Key differentiator: knowledge base integration with SharePoint.",
    ),
    Opportunity(
        id="opp-002",
        name="Fabrikam Real-Time Analytics",
        account="Fabrikam Inc",
        stage="Qualification",
        status="open",
        estimated_value=280_000,
        close_date="2026-08-15",
        contacts=["Chen Wei (Data Lead)", "Sarah O'Brien (Director Analytics)"],
        notes="Fabric Eventstream POC scheduled for next week. Competing with Databricks.",
    ),
    Opportunity(
        id="opp-003",
        name="Northwind Traders Copilot Rollout",
        account="Northwind Traders",
        stage="Closed Won",
        status="won",
        estimated_value=120_000,
        close_date="2026-04-15",
        contacts=["David Kim (IT Director)"],
        notes="M365 Copilot deployed to 500 users. Expansion opportunity for custom agents.",
    ),
    Opportunity(
        id="opp-004",
        name="Adventure Works IoT Platform",
        account="Adventure Works",
        stage="Negotiation",
        status="open",
        estimated_value=680_000,
        close_date="2026-07-30",
        contacts=["Lisa Park (Head of IoT)", "James Wright (CIO)"],
        notes="IoT device telemetry pipeline using Fabric + Eventstream. Customer concerned about latency SLA.",
    ),
    Opportunity(
        id="opp-005",
        name="Wide World Importers Data Migration",
        account="Wide World Importers",
        stage="Closed Lost",
        status="lost",
        estimated_value=350_000,
        close_date="2026-03-20",
        contacts=["Rachel Green (VP Operations)"],
        notes="Lost to GCP — customer cited lower BigQuery pricing and existing Google Workspace investment.",
    ),
]


class DataverseClient:
    """Client for querying Dataverse CRM opportunities."""

    def __init__(self):
        self._env_url = os.environ.get("DATAVERSE_ENVIRONMENT_URL", "")
        self._use_live = bool(self._env_url)

    async def query_opportunities(
        self,
        status: str = "open",
        accounts: list[str] | None = None,
        top: int = 50,
    ) -> list[Opportunity]:
        """Query opportunities from Dataverse or return synthetic data."""
        if not self._use_live:
            return self._filter_synthetic(status, accounts, top)

        return await self._query_live(status, accounts, top)

    def _filter_synthetic(
        self, status: str, accounts: list[str] | None, top: int
    ) -> list[Opportunity]:
        """Filter synthetic opportunities for demo mode."""
        results = SYNTHETIC_OPPORTUNITIES

        if status != "all":
            results = [o for o in results if o.status == status]

        if accounts:
            account_lower = {a.lower() for a in accounts}
            results = [o for o in results if o.account.lower() in account_lower]

        return results[:top]

    async def _query_live(
        self, status: str, accounts: list[str] | None, top: int
    ) -> list[Opportunity]:
        """Query live Dataverse Web API."""
        credential = DefaultAzureCredential()
        token = credential.get_token(DATAVERSE_SCOPE)

        url = f"{self._env_url}/api/data/v9.2/opportunities"
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }

        filters = []
        if status == "open":
            filters.append("statecode eq 0")
        elif status == "won":
            filters.append("statecode eq 1")
        elif status == "lost":
            filters.append("statecode eq 2")

        if accounts:
            account_filters = " or ".join(
                f"contains(_parentaccountid_value, '{a}')" for a in accounts
            )
            filters.append(f"({account_filters})")

        params = {
            "$top": str(top),
            "$select": "opportunityid,name,estimatedvalue,estimatedclosedate,stepname,statecode,statuscode",
            "$expand": "parentaccountid($select=name),opportunity_customer_contacts($select=fullname)",
            "$orderby": "estimatedclosedate asc",
        }
        if filters:
            params["$filter"] = " and ".join(filters)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        opportunities = []
        for record in data.get("value", []):
            status_map = {0: "open", 1: "won", 2: "lost"}
            opp = Opportunity(
                id=record.get("opportunityid", ""),
                name=record.get("name", ""),
                account=record.get("parentaccountid", {}).get("name", "Unknown"),
                stage=record.get("stepname", "Unknown"),
                status=status_map.get(record.get("statecode", 0), "open"),
                estimated_value=record.get("estimatedvalue", 0),
                close_date=record.get("estimatedclosedate", ""),
                contacts=[
                    c.get("fullname", "")
                    for c in record.get("opportunity_customer_contacts", [])
                ],
            )
            opportunities.append(opp)

        return opportunities
