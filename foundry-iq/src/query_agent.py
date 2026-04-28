"""Query a grounded AI agent using Azure OpenAI + Azure AI Search (RAG pattern).

Searches the AI Search index for relevant context, then sends it with the user
question to a chat completion model. Optionally writes insights to PostgreSQL.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from openai import AzureOpenAI

# Allow importing shared module
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_PG_ENABLED = bool(os.environ.get("POSTGRES_HOST") or os.environ.get("POSTGRES_CONNECTION_STRING"))

SYSTEM_PROMPT = (
    "You are an e-commerce analytics advisor grounded in Brazilian E-Commerce data (Olist). "
    "Use the provided search results to answer questions about products, reviews, and customer behaviour. "
    "Always cite data sources in your answer. When analytical insights from Fabric are available, "
    "incorporate them to provide richer answers. Be concise and data-driven."
)


def _search_context(question: str, top: int = 10) -> str:
    """Retrieve relevant documents from AI Search."""
    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME", "microsoft-iq-products")
    credential = DefaultAzureCredential()

    client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
    results = client.search(search_text=question, top=top)

    context_parts = []
    for doc in results:
        context_parts.append(
            f"[{doc['doc_type']}] {doc['title']} | category={doc.get('category', 'N/A')} | "
            f"score={doc.get('score', 'N/A')}\n{doc['content']}"
        )

    return "\n---\n".join(context_parts) if context_parts else "No relevant documents found."


def query_agent(question: str) -> str:
    """Send a question grounded with AI Search context to the LLM."""
    endpoint = os.environ["AZURE_AI_FOUNDRY_ENDPOINT"]
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "deepseek-v3-1")
    credential = DefaultAzureCredential()

    # Retrieve grounding context from AI Search
    print("Searching knowledge base...")
    context = _search_context(question)

    # Check for unconsumed analytical results to enrich context
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

    # Build the grounded prompt
    user_message = (
        f"## Search Results (Knowledge Base)\n\n{context}\n\n"
        f"{enrichment}"
        f"## User Question\n\n{question}"
    )

    # Call the model via Azure OpenAI-compatible endpoint
    from azure.identity import get_bearer_token_provider
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-12-01-preview",
    )

    print(f"Querying model: {deployment}...")
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    answer = response.choices[0].message.content or ""

    # Write insight to PostgreSQL (transactional → analytical bridge)
    if answer and _PG_ENABLED:
        try:
            from postgres_client import write_insight
            row_id = asyncio.run(write_insight(
                agent_name="microsoft-iq-agent",
                question=question,
                answer=answer,
                metadata={"model": deployment, "enriched": bool(enrichment)},
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
    print(f"\nAnswer:\n{answer}")


if __name__ == "__main__":
    main()
