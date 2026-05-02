from collections.abc import Callable

import structlog
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import make_session_factory

log = structlog.get_logger(__name__)

# this file is responsible for retrieving relevant documents from the database given a query, used by rag_tool in agent.py
async def _embed_query(client: AsyncOpenAI, query: str) -> list[float]:
    # Use the same model as ingest.py — dimension mismatch otherwise
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=[query],
    )
    return response.data[0].embedding


async def _search(
    engine: AsyncEngine,
    openai_client: AsyncOpenAI,
    query: str,
    k: int = 4,
) -> list[dict]:
    embedding = await _embed_query(openai_client, query)

    factory = make_session_factory(engine)
    async with factory() as session:
        rows = await session.execute(
            text("""
                SELECT destination, content,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM documents
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :k
            """),
            {"embedding": str(embedding), "k": k},
        )
        results = [
            {"destination": r.destination, "content": r.content, "similarity": round(r.similarity, 4)}
            for r in rows
        ]

    log.info("retriever.search", query=query, k=k, results=len(results))
    return results


def make_retriever(engine: AsyncEngine, openai_client: AsyncOpenAI) -> Callable:
    # Returns a closure with engine + client baked in — called by rag_tool
    async def retrieve(query: str, k: int = 4) -> list[dict]:
        return await _search(engine, openai_client, query, k)

    return retrieve
