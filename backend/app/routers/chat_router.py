import asyncio
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent import build_messages, extract_tool_calls
from app.core.callbacks import CostTracker, ToolTimingCallback
from app.core.config import get_settings
from app.core.deps import AgentDep, CurrentUserDep, DBDep
from app.core.models import AgentRun, ChatMessage, ChatSession, ToolCall
from app.core.schemas import ChatRequest, ChatResponse
from app.services.webhook import TripPlanEvent, deliver_trip_plan

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: CurrentUserDep,
    db: DBDep,
    agent: AgentDep,
):
    # Get or create session 
    if req.session_id:
        result = await db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(req.session_id)))
        session = result.scalar_one_or_none()
        if not session or session.user_id != user.id:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(user_id=user.id, title=req.question[:50])
        db.add(session)
        await db.flush()  # flush to get session.id before using it
        # Flushing tells the database to process the insert and return the generated ID without committing, so if something goes wrong later, the whole thing can still be rolled back cleanly

    # insert user message into db before invoking agent
    db.add(ChatMessage(session_id=session.id, role="user", content=req.question))

    # Invoke agent and go to function build messages
    config = {"configurable": {"thread_id": str(session.id)}} # LangGraph requires a string key. Passing a UUID object directly causes a runtime error
    messages_to_send = await build_messages(agent, config, session.id, req.question, db)

    # callbacks from langchain
    timing_cb = ToolTimingCallback()
    cost_cb = CostTracker()
    start = time.perf_counter()


    result = await agent.ainvoke(
        {"messages": messages_to_send},
        config={**config, "callbacks": [timing_cb, cost_cb]},
    )

    duration = time.perf_counter() - start
    answer = result["messages"][-1].content

    # Persist assistant message to db
    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))

    # Persist AgentRun + ToolCalls
    tool_calls_data = extract_tool_calls(result["messages"])

    agent_run = AgentRun(
        session_id=session.id,
        input=req.question,
        output=answer,
        duration_s=round(duration, 3),
        cost_usd=cost_cb.cost_usd,
        prompt_tokens=cost_cb.prompt_tokens,
        completion_tokens=cost_cb.completion_tokens,
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

    # Slack webhook: fire and forget, never awaited on the critical path
    s = get_settings()
    # create task to send to the user's slack without delaying the http response
    asyncio.create_task(deliver_trip_plan(s.slack_webhook_url, TripPlanEvent(user_email=user.email, plan=answer)))

    log.info("chat.complete", session_id=str(session.id), duration_s=duration, cost_usd=cost_cb.cost_usd)

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
