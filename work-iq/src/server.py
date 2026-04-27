"""Work IQ — MCP server for work intelligence extraction.

Exposes tools for querying Dataverse opportunities, classifying work signals,
and generating daily work digests. Designed for use with Copilot CLI via
stdio transport.

Usage:
    python src/server.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from dataverse_client import DataverseClient
from signals import build_signal_report

server = Server("work-iq")
dv_client = DataverseClient()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_opportunities",
            description=(
                "Query CRM opportunities from Dataverse. Returns structured records "
                "with account, stage, status, value, and contact information. "
                "Uses synthetic data when Dataverse credentials are not configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "won", "lost", "all"],
                        "default": "open",
                        "description": "Filter by opportunity status",
                    },
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by account names",
                    },
                    "top": {
                        "type": "integer",
                        "default": 50,
                        "maximum": 100,
                        "description": "Maximum number of results",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="classify_signals",
            description=(
                "Classify work data into 8 signal types: wins, losses, escalations, "
                "compete, products, ip, people, others. Accepts opportunities and "
                "free-text inputs (emails, chat messages, transcripts)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "opportunities": {
                        "type": "array",
                        "items": {"type": "object"},
                        "default": [],
                        "description": "CRM opportunity records to classify",
                    },
                    "texts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "source": {"type": "string"},
                            },
                        },
                        "default": [],
                        "description": "Free-text items to classify (emails, chats, etc.)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_digest",
            description=(
                "Generate a structured daily work digest from classified signals. "
                "Queries opportunities and classifies them into a summary report."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Reference date (YYYY-MM-DD). Default: today.",
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    args = arguments or {}

    if name == "query_opportunities":
        status = str(args.get("status", "open")).lower()
        if status not in {"open", "won", "lost", "all"}:
            return [TextContent(type="text", text="ERROR: status must be open, won, lost, or all")]

        accounts = args.get("accounts") or None
        top = min(int(args.get("top", 50)), 100)

        opportunities = await dv_client.query_opportunities(status=status, accounts=accounts, top=top)
        result = [o.to_dict() for o in opportunities]
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    if name == "classify_signals":
        opportunities = args.get("opportunities") or []
        texts = args.get("texts") or []

        report = build_signal_report(opportunities=opportunities, texts=texts)
        return [TextContent(type="text", text=json.dumps(report.to_dict(), indent=2, ensure_ascii=False))]

    if name == "generate_digest":
        ref_date = args.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

        # Fetch all opportunities
        all_opps = await dv_client.query_opportunities(status="all")
        opp_dicts = [o.to_dict() for o in all_opps]

        # Classify
        report = build_signal_report(opportunities=opp_dicts)

        # Build digest
        digest = {
            "date": ref_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_opportunities": len(all_opps),
                "open": sum(1 for o in all_opps if o.status == "open"),
                "won": sum(1 for o in all_opps if o.status == "won"),
                "lost": sum(1 for o in all_opps if o.status == "lost"),
                "total_pipeline_value": sum(o.estimated_value for o in all_opps if o.status == "open"),
            },
            "signal_report": report.to_dict(),
            "top_actions": _extract_top_actions(report),
        }

        return [TextContent(type="text", text=json.dumps(digest, indent=2, ensure_ascii=False))]

    return [TextContent(type="text", text=f"ERROR: Unknown tool '{name}'")]


def _extract_top_actions(report) -> list[dict]:
    """Extract top-priority action items from a signal report."""
    actions = []

    # Escalations are highest priority
    for sig in report.signals:
        if sig.type.value == "escalations":
            actions.append({"priority": "high", "action": f"Address escalation: {sig.summary}", "source": sig.source})

    # Competitive signals
    for sig in report.signals:
        if sig.type.value == "compete":
            actions.append({"priority": "medium", "action": f"Review competitive signal: {sig.summary}", "source": sig.source})

    # Wins to celebrate / losses to learn from
    for sig in report.signals:
        if sig.type.value == "wins":
            actions.append({"priority": "low", "action": f"Celebrate win: {sig.summary}", "source": sig.source})
        elif sig.type.value == "losses":
            actions.append({"priority": "medium", "action": f"Post-mortem: {sig.summary}", "source": sig.source})

    return actions[:10]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
