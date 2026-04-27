"""Query a Foundry agent grounded with a knowledge base via the Azure AI Projects SDK."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentsApiResponseFormatMode
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def query_agent(question: str) -> str:
    """Send a question to the Foundry agent and return the grounded answer."""
    endpoint = os.environ["AZURE_AI_FOUNDRY_ENDPOINT"]
    credential = DefaultAzureCredential()

    client = AIProjectClient(endpoint=endpoint, credential=credential)

    # List available agents (or create one if needed)
    agents = client.agents.list_agents()
    if not agents.data:
        print("No agents found. Creating a demo agent...")
        agent = client.agents.create_agent(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
            name="microsoft-iq-agent",
            instructions=(
                "You are a product advisor for Microsoft Azure services. "
                "Use the knowledge base to find the best-fit products based on the user's needs. "
                "Always cite which product document your answer comes from."
            ),
        )
    else:
        agent = agents.data[0]

    print(f"Using agent: {agent.name} (id: {agent.id})")

    # Create a thread and send the question
    thread = client.agents.create_thread()
    client.agents.create_message(thread_id=thread.id, role="user", content=question)

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
    messages = client.agents.list_messages(thread_id=thread.id)
    for msg in reversed(messages.data):
        if msg.role == "assistant":
            for block in msg.content:
                if hasattr(block, "text"):
                    return block.text.value

    return ""


def main() -> None:
    """CLI entry point: pass a question as argument or use the default."""
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What products support real-time analytics?"

    print(f"\nQuestion: {question}\n")
    answer = query_agent(question)
    print(f"Answer:\n{answer}")


if __name__ == "__main__":
    main()
