import os
import tempfile
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.core.models  # noqa: F401 — registers models on Base.metadata before create_all
from app.core.db import Base

CLASSIFIER_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "ml", "classifier.joblib")
)


@pytest.fixture
def mock_classifier():
    clf = MagicMock()
    clf.predict.return_value = ["Culture"]
    clf.predict_proba.return_value = [[0.05, 0.05, 0.7, 0.05, 0.1, 0.05]]
    clf.classes_ = ["Adventure", "Budget", "Culture", "Family", "Luxury", "Relaxation"]
    return clf


@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [AIMessage(content="Paris is a wonderful destination!")]
    }
    agent.checkpointer = AsyncMock()
    # Return non-None so _build_messages skips history injection
    agent.checkpointer.aget.return_value = {"state": "warm"}
    return agent


@pytest.fixture
async def sqlite_engine():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create tables synchronously before any async engine touches the file —
    # aiosqlite's per-thread model can make the first async create_all invisible
    # to subsequent connections in the same test's event loop.
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    yield engine
    await engine.dispose()
    os.unlink(db_path)


@pytest.fixture
async def http_client(sqlite_engine, mock_agent, mock_classifier):
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.core.deps import get_agent, get_classifier, get_db

    # Build a session factory bound to the test's SQLite engine
    factory = async_sessionmaker(sqlite_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    # Override dependencies — cleaner than touching app.state directly
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_classifier] = lambda: mock_classifier

    # app.state still needed for anything that reads it outside Depends()
    app.state.engine = sqlite_engine
    app.state.openai = AsyncMock()
    app.state.classifier = mock_classifier
    app.state.agent = mock_agent

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    for key in ("engine", "openai", "classifier", "agent"):
        app.state._state.pop(key, None)
