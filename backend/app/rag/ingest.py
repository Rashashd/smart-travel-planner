import asyncio

import httpx
import structlog
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.rag.chunks import chunk_text, embed, store_chunks
from app.rag.fetcher import DESTINATIONS, fetch_wikivoyage

log = structlog.get_logger(__name__)

async def setup_table(engine):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                destination TEXT NOT NULL,
                content     TEXT NOT NULL,
                embedding   vector(1536),
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 10)
        """))


async def main():
    settings = get_settings()

    engine = create_async_engine(settings.database_url)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    await setup_table(engine)
    log.info("table ready")

    async with httpx.AsyncClient() as http_client:
        for destination in DESTINATIONS:
            log.info("processing destination", destination=destination)

            try:
                raw_text = await fetch_wikivoyage(http_client, destination)
                if not raw_text:
                    log.warning("no content found, skipping", destination=destination)
                    continue

                chunks = chunk_text(raw_text)
                log.info("chunks created", destination=destination, count=len(chunks))

                embeddings = await embed(openai_client, chunks)
                log.info("embeddings created", destination=destination, count=len(embeddings))

                async with engine.begin() as conn:
                    await store_chunks(conn, destination, chunks, embeddings)
                log.info("stored in db", destination=destination)

            except Exception:
                log.exception("failed to process destination", destination=destination)

    await engine.dispose()
    log.info("ingest complete")


if __name__ == "__main__":
    asyncio.run(main())
