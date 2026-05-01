from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.core.config import Settings
from app.prompts import TRAVEL_AGENT_SYSTEM_PROMPT
from app.tools.classifier_tool import make_classifier_tool
from app.tools.live_tool import make_live_tool
from app.tools.rag_tool import make_rag_tool
from app.tools.search_tool import make_search_tool

log = structlog.get_logger(__name__)


class _TokenLogger(BaseCallbackHandler):
    """Logs prompt + completion token counts after every LLM call."""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generation in response.generations:
            for g in generation:
                usage = getattr(g.message, "usage_metadata", None) or getattr(g, "generation_info", {})
                if not usage:
                    continue
                prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                model = getattr(g.message, "response_metadata", {}).get("model_name", "unknown")
                log.info(
                    "llm.tokens",
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )


def build_agent(settings: Settings, classifier: object, retriever: Callable) -> object:
    token_logger = _TokenLogger()

    # cheap model for query rewriting inside rag_tool — fast and cheap
    cheap_llm = ChatOpenAI(
        model=settings.cheap_model,
        temperature=0,
        api_key=settings.openai_api_key,
        callbacks=[token_logger],
    )

    # strong model for the agent itself — better reasoning for trip planning
    strong_llm = ChatOpenAI(
        model=settings.strong_model,
        temperature=0.2,
        api_key=settings.openai_api_key,
        callbacks=[token_logger],
    )

    tools = [
        make_live_tool(),
        make_rag_tool(cheap_llm, retriever),
        make_classifier_tool(classifier),
        make_search_tool(),
    ]

    memory = MemorySaver()

    return create_react_agent(
        model=strong_llm,
        tools=tools,
        checkpointer=memory,
        prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
    )
