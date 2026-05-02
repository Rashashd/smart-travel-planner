from openai import AsyncOpenAI
from sqlalchemy import text

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


def chunk_text(content: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(content):
        end = start + size
        chunks.append(content[start:end])
        start += size - overlap
    return chunks


async def embed(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


async def store_chunks(conn, destination: str, chunks: list[str], embeddings: list[list[float]]):
    for chunk, embedding in zip(chunks, embeddings):
        await conn.execute(
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
