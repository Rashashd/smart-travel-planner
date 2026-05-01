import asyncio

import structlog
from duckduckgo_search import DDGS
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.tools.live_tool import ToolError

log = structlog.get_logger(__name__)

_DDGS_TIMEOUT = 8.0  # seconds before we give up on a DDGS call


class SearchInput(BaseModel):
    query: str = Field(..., min_length=3, description="Search query, e.g. 'flights Paris from Beirut June 2025'")
    max_results: int = Field(default=5, ge=1, le=10)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _ddgs_search(query: str, max_results: int) -> list[dict]:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return [{"title": r["title"], "snippet": r["body"], "url": r["href"]} for r in results]


async def _web_search(query: str, max_results: int = 5) -> list[dict] | ToolError:
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_ddgs_search, query, max_results),
            timeout=_DDGS_TIMEOUT,
        )
        log.info("search_tool.results", query=query, count=len(results))
        return results
    except TimeoutError:
        log.error("search_tool.timeout", query=query, timeout=_DDGS_TIMEOUT)
        return ToolError(error="Web search timed out", retryable=True)
    except Exception:
        log.exception("search_tool.failure", query=query)
        return ToolError(error="Web search failed", retryable=True)


def make_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_web_search,
        name="web_search",
        description=(
            "Search the web for real-time information: flight prices, visa requirements, "
            "travel advisories, hotel prices, or anything not in the knowledge base."
        ),
        args_schema=SearchInput,
    )
