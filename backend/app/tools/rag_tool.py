from collections.abc import Callable

import structlog
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.prompts import RAG_QUERY_REWRITE_PROMPT
from app.tools.live_tool import ToolError

log = structlog.get_logger(__name__)


class RAGInput(BaseModel):
    query: str = Field(..., min_length=3)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _rewrite_query(raw: str, cheap_llm: ChatOpenAI) -> str:
    result = await cheap_llm.ainvoke(RAG_QUERY_REWRITE_PROMPT.format(query=raw))
    return result.content.strip()


def make_rag_tool(cheap_llm: ChatOpenAI, retriever: Callable) -> StructuredTool:
    async def _rag_search(query: str) -> list[dict] | ToolError:
        try:
            clean_query = await _rewrite_query(query, cheap_llm)
            log.info("rag_tool.query_rewritten", original=query, rewritten=clean_query)
            return await retriever(clean_query, k=4)
        except Exception:
            log.exception("rag_tool.failure", query=query)
            return ToolError(error="RAG retrieval failed", retryable=False)

    return StructuredTool.from_function(
        coroutine=_rag_search,
        name="search_destination_knowledge",
        description="Search the travel knowledge base for destination information.",
        args_schema=RAGInput,
    )
