import json
from collections.abc import Callable
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from sqlalchemy import select

from app.core.callbacks import _TokenLogger
from app.core.config import Settings
from app.core.models import ChatMessage
from app.prompts import TRAVEL_AGENT_SYSTEM_PROMPT
from app.tools.classifier_tool import make_classifier_tool
from app.tools.live_tool import make_live_tool
from app.tools.rag_tool import make_rag_tool
from app.tools.search_tool import make_search_tool

log = structlog.get_logger(__name__)


async def build_messages(agent: Any, config: dict, session_id: Any, question: str, db: Any) -> list:
    """Return messages to send to the agent.

    Warm (checkpointer has state): send only the new message.
    Cold (server restarted): replay DB history first, then append the new message.
    """
    checkpoint = await agent.checkpointer.aget(config)
    if checkpoint is not None:
        return [HumanMessage(content=question)]

    hist_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history = hist_result.scalars().all()

    messages: list = []
    for msg in history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=question))
    return messages


def extract_tool_calls(messages: list) -> list[dict]:
    """Parse LangGraph message list into a flat list of tool call dicts."""
    by_id: dict[str, dict] = {}
    ordered: list[dict] = []

    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                entry = {
                    "tool_name": tc["name"],
                    "input_json": json.dumps(tc["args"]),
                    "output_json": None,
                    "error": None,
                }
                by_id[tc["id"]] = entry
                ordered.append(entry)

        if msg.__class__.__name__ == "ToolMessage":
            entry = by_id.get(getattr(msg, "tool_call_id", ""))
            if entry:
                output = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
                entry["output_json"] = output
                try:
                    parsed = json.loads(output)
                    if "error" in parsed and "retryable" in parsed:
                        entry["error"] = parsed["error"]
                except (json.JSONDecodeError, TypeError):
                    pass

    return ordered


def build_agent(settings: Settings, classifier: object, retriever: Callable) -> object:
    token_logger = _TokenLogger()

    cheap_llm = ChatOpenAI(
        model=settings.cheap_model,
        temperature=0,
        api_key=settings.openai_api_key,
        callbacks=[token_logger],
    )

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
