"""Query a Foundry agent grounded with a knowledge base via the Azure AI Projects SDK.

After each query, the agent insight (question + answer) is written to PostgreSQL
so the analytical layer (Fabric IQ) can aggregate interaction patterns.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentsApiResponseFormatMode
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Allow importing shared module
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_PG_ENABLED = bool(os.environ.get("POSTGRES_HOST") or os.environ.get("POSTGRES_CONNECTION_STRING"))


def query_agent(question: str) -> str:
    """Send a question to the Foundry agent and return the grounded answer."""
    endpoint = os.environ["AZURE_AI_FOUNDRY_ENDPOINT"]
    credential = DefaultAzureCredential()

    client = AIProjectClient(endpoint=endpoint, credential=credential)

    # Check for unconsumed analytical results to enrich agent context
    enrichment = ""
    if _PG_ENABLED:
        try:
            from postgres_client import get_unconsumed_results, mark_results_consumed
            results = asyncio.run(get_unconsumed_results(limit=5))
            if results:
                enrichment = "\n\nRecent analytical insights from Fabric:\n"
                for r in results:
                    enrichment += f"- [{r['analysis_type']}] {r['result_summary']}\n"
                asyncio.run(mark_results_consumed([r["id"] for r in results]))
        except Exception as exc:
            print(f"Note: Could not fetch analytical results: {exc}", file=sys.stderr)

    # List available agents (or create one if needed)
    agents = client.agents.list_agents()
    if not agents.data:
        print("No agents found. Creating a demo agent...")
        agent = client.agents.create_agent(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
            name="microsoft-iq-agent",
            instructions=(
                "You are an e-commerce analytics advisor grounded in Brazilian E-Commerce data (Olist). "
                "Use the knowledge base to answer questions about products, reviews, and customer behaviour. "
                "Always cite data sources in your answer. When analytical insights from Fabric are available, "
                "incorporate them to provide richer answers."
            ),
        )
    else:
        agent = agents.data[0]

    print(f"Using agent: {agent.name} (id: {agent.id})")

    # Create a thread and send the question (with analytical enrichment if available)
    thread = client.agents.create_thread()
    full_question = question + enrichment if enrichment else question
    client.agents.create_message(thread_id=thread.id, role="user", content=full_question)

    # Run the agent
    run = client.agents.create_and_process_run(
        thread_id=thread.id,
        agent_id=agent.id,
        response_format=AgentsApiResponseFormatMode.AUTO,
    )

    if run.status == "failed":
        print(f"Agent run failed: {run.last_error}", file=sys.stderr)
        return ""

    # Get the response
    answer = ""
    messages = client.agents.list_messages(thread_id=thread.id)
    for msg in reversed(messages.data):
        if msg.role == "assistant":
            for block in msg.content:
                if hasattr(block, "text"):
                    answer = block.text.value
                    break

    # Write insight to PostgreSQL (transactional → analytical bridge)
    if answer and _PG_ENABLED:
        try:
            from postgres_client import write_insight
            row_id = asyncio.run(write_insight(
                agent_name=agent.name,
                question=question,
                answer=answer,
                metadata={"agent_id": agent.id, "enriched": bool(enrichment)},
            ))
            print(f"Insight #{row_id} written to PostgreSQL")
        except Exception as exc:
            print(f"Note: Could not write insight to PostgreSQL: {exc}", file=sys.stderr)

    return answer


def main() -> None:
    """CLI entry point: pass a question as argument or use the default."""
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What are the most common product categories?"

    print(f"\nQuestion: {question}\n")
    answer = query_agent(question)
    print(f"Answer:\n{answer}")


if __name__ == "__main__":
    main()
