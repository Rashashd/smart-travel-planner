import asyncio

import httpx
import structlog
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings

log = structlog.get_logger(__name__)

DESTINATIONS = [
    'Paris', 'Tokyo', 'Bali', 'Reykjavík', 'Marrakech', 'Cuzco', 'Lisbon', 'Bangkok', 'Barcelona', 'Queenstown', 'Santorini', 'Beirut', 'Dubai', 'Istanbul'
]

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


# Fetch from Wikivoyage
async def fetch_wikivoyage(client: httpx.AsyncClient, destination: str) -> str:
    # MediaWiki Action API — more stable than rest_v1/mobile-sections (retired)
    # explaintext=1 returns plain text so no HTML stripping needed
    url = "https://en.wikivoyage.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "titles": destination,
        "format": "json",
        "explaintext": "1",
        "exsectionformat": "plain",
    }
    headers = {"User-Agent": "smart-travel-planner/1.0 (racha.chamseddine96@gmail.com)"}
    response = await client.get(url, params=params, timeout=15.0, headers=headers)
    response.raise_for_status()
    data = response.json()

    # The API returns a dict of pages keyed by page ID (-1 means not found)
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))
    return page.get("extract", "")


# Chunking
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    # Split text into overlapping chunks
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


# Embed
async def embed(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    # Embed a list of texts using text-embedding-3-small
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


# Store in pgvector
async def store_chunks(session, destination: str, chunks: list[str], embeddings: list[list[float]]):
    # Insert chunks and their embeddings into the documents table
    for chunk, embedding in zip(chunks, embeddings):
        await session.execute(
            text("""
                INSERT INTO documents (destination, content, embedding)
                VALUES (:destination, :content, CAST(:embedding AS vector))
            """),
            {
                "destination": destination,
                "content": chunk,
                # pgvector accepts '[x, y, ...]' string format via CAST
                "embedding": str(embedding),
            }
        )
    await session.commit()


# Setup DB table
async def setup_table(engine):
    # Create the documents table if it doesn't exist
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


# Main
async def main():
    settings = get_settings()

    engine = create_async_engine(settings.database_url)
    # async_sessionmaker is the async-native version of sessionmaker
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Create table
    await setup_table(engine)
    log.info("table ready")

    async with httpx.AsyncClient() as http_client:
        for destination in DESTINATIONS:
            log.info("processing destination", destination=destination)

            try:
                # Fetch
                raw_text = await fetch_wikivoyage(http_client, destination)
                if not raw_text:
                    log.warning("no content found, skipping", destination=destination)
                    continue

                # Chunk
                chunks = chunk_text(raw_text)
                log.info("chunks created", destination=destination, count=len(chunks))

                # Embed
                embeddings = await embed(openai_client, chunks)
                log.info("embeddings created", destination=destination, count=len(embeddings))

                # Store
                async with SessionLocal() as session:
                    await store_chunks(session, destination, chunks, embeddings)
                log.info("stored in db", destination=destination)

            except Exception:
                # log.exception captures the full traceback automatically
                log.exception("failed to process destination", destination=destination)

    await engine.dispose()
    log.info("ingest complete")


if __name__ == "__main__":
    asyncio.run(main())
