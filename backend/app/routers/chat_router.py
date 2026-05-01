import asyncio
import json
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import AgentDep, CurrentUserDep, DBDep
from app.core.models import AgentRun, ChatMessage, ChatSession, ToolCall
from app.services.webhook import TripPlanEvent, deliver_trip_plan

log = structlog.get_logger(__name__)
router = APIRouter()


class ToolTimingCallback(BaseCallbackHandler):
    """Records how long each tool call takes and whether it errored."""

    def __init__(self):
        self._starts: dict[str, float] = {}  # run_id -> start time
        self.durations: list[float | None] = []  # one entry per tool call, in order
        self.errors: list[str | None] = []       # matching error messages (or None)

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        self._starts[str(run_id)] = time.perf_counter()
        self.errors.append(None)

    def on_tool_end(self, output, *, run_id, **kwargs):
        start = self._starts.pop(str(run_id), None)
        self.durations.append(round(time.perf_counter() - start, 3) if start else None)

    def on_tool_error(self, error, *, run_id, **kwargs):
        start = self._starts.pop(str(run_id), None)
        self.durations.append(round(time.perf_counter() - start, 3) if start else None)
        if self.errors:
            self.errors[-1] = str(error)


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None  # UUID string — None means start a new session


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    tool_calls: list[dict]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: CurrentUserDep,
    db: DBDep,
    agent: AgentDep,
):
    # ── Get or create session ────────────────────────────────────────────────
    if req.session_id:
        result = await db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(req.session_id)))
        session = result.scalar_one_or_none()
        if not session or session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(user_id=user.id, title=req.question[:50])
        db.add(session)
        await db.flush()  # flush to get session.id before using it

    # ── Persist user message ─────────────────────────────────────────────────
    db.add(ChatMessage(session_id=session.id, role="user", content=req.question))

    # ── Invoke agent ─────────────────────────────────────────────────────────
    # thread_id = session.id — same session = same LangGraph memory
    config = {"configurable": {"thread_id": str(session.id)}}

    # MemorySaver is in-memory only — if the server restarted, the checkpointer
    # has no state for this thread. Inject DB history so the agent has context.
    messages_to_send = await _build_messages(agent, config, session.id, req.question, db)

    timing_cb = ToolTimingCallback()
    start = time.perf_counter()

    result = await agent.ainvoke(
        {"messages": messages_to_send},
        config={**config, "callbacks": [timing_cb]},
    )

    duration = time.perf_counter() - start
    answer = result["messages"][-1].content

    # ── Persist assistant message ────────────────────────────────────────────
    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))

    # ── Persist AgentRun + ToolCalls ─────────────────────────────────────────
    tool_calls_data = _extract_tool_calls(result["messages"])

    agent_run = AgentRun(
        session_id=session.id,
        input=req.question,
        output=answer,
        duration_s=round(duration, 3),
    )
    db.add(agent_run)
    await db.flush()

    for i, tc in enumerate(tool_calls_data):
        db.add(ToolCall(
            agent_run_id=agent_run.id,
            tool_name=tc["tool_name"],
            input_json=tc["input_json"],
            output_json=tc["output_json"],
            error=timing_cb.errors[i] if i < len(timing_cb.errors) else None,
            duration_s=timing_cb.durations[i] if i < len(timing_cb.durations) else None,
        ))

    await db.commit()

    # ── Slack webhook — fire and forget, never awaited on the critical path ──
    s = get_settings()
    asyncio.create_task(deliver_trip_plan(s.slack_webhook_url, TripPlanEvent(user_email=user.email, plan=answer)))

    log.info("chat.complete", session_id=str(session.id), duration_s=duration)

    return ChatResponse(
        answer=answer,
        session_id=str(session.id),
        tool_calls=tool_calls_data,
    )


@router.get("/sessions")
async def list_sessions(user: CurrentUserDep, db: DBDep):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [{"id": str(s.id), "title": s.title, "created_at": s.created_at} for s in sessions]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, user: CurrentUserDep, db: DBDep):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == uuid.UUID(session_id))
        .options(
            selectinload(ChatSession.messages),
            selectinload(ChatSession.agent_runs).selectinload(AgentRun.tool_calls),
        )
    )
    session = result.scalar_one_or_none()

    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Pair assistant messages with their agent run tool calls by creation order
    agent_runs_sorted = sorted(session.agent_runs, key=lambda r: r.created_at)
    assistant_run_iter = iter(agent_runs_sorted)

    messages = []
    for m in session.messages:
        entry: dict = {"role": m.role, "content": m.content, "created_at": m.created_at}
        if m.role == "assistant":
            run = next(assistant_run_iter, None)
            if run and run.tool_calls:
                entry["tool_calls"] = [
                    {
                        "tool_name": tc.tool_name,
                        "input_json": tc.input_json,
                        "output_json": tc.output_json,
                    }
                    for tc in run.tool_calls
                ]
        messages.append(entry)

    return messages


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: CurrentUserDep, db: DBDep):
    result = await db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(session_id)))
    session = result.scalar_one_or_none()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()


async def _build_messages(
    agent: object,
    config: dict,
    session_id: object,
    question: str,
    db: object,
) -> list:
    """Return messages to send to the agent.

    If the checkpointer already has state for this thread (warm — same server
    session), just send the new HumanMessage and let LangGraph append it.
    If not (cold — server restarted), inject the full DB history first so the
    agent has context, then append the new message.
    """
    checkpoint = await agent.checkpointer.aget(config)
    if checkpoint is not None:
        return [HumanMessage(content=question)]

    # Cold start — load history from DB and replay it
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


def _extract_tool_calls(messages: list) -> list[dict]:
    # Index tool calls by their ID, then fill in outputs from ToolMessages
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

        # ToolMessage.tool_call_id matches the originating tool call
        if msg.__class__.__name__ == "ToolMessage":
            entry = by_id.get(getattr(msg, "tool_call_id", None))
            if entry:
                output = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
                entry["output_json"] = output
                # If the tool returned a ToolError, surface it in the error field
                try:
                    parsed = json.loads(output)
                    if "error" in parsed and "retryable" in parsed:
                        entry["error"] = parsed["error"]
                except (json.JSONDecodeError, TypeError):
                    pass

    return ordered
