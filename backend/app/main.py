from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before any langchain import, LangSmith reads os.environ at import time. if it runs after, LangSmith never sees your env vars and tracing is silent

import asyncio  # noqa: E402

import joblib  # noqa: E402
import structlog  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

import app.core.models  # noqa: E402, F401 — registers models on Base.metadata at import time
from app.agent import build_agent  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, make_engine  # noqa: E402
from app.services.retriever import make_retriever  # noqa: E402

logger = structlog.get_logger(__name__)

# defining the the app's startup and shutdown logic
@asynccontextmanager
async def lifespan(app: FastAPI):
    # reading .env into settings
    s = get_settings()

    app.state.engine = make_engine(s.database_url)
    # create all tables if they dont exist
    async with app.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.openai = AsyncOpenAI(api_key=s.openai_api_key.get_secret_value())
    
    # loading classifier, asyncio because joblib is not async safe it may block i/o
    app.state.classifier = await asyncio.to_thread(joblib.load, s.classifier_path)

    retriever = make_retriever(app.state.engine, app.state.openai)
    app.state.agent = build_agent(s, app.state.classifier, retriever)

    logger.info("startup complete", classifier_path=s.classifier_path)
    yield

    await app.state.engine.dispose()
    logger.info("shutdown complete")

# All these go into app.state: FastAPI's official way to share singletons across requests where deps.py reads them via request.app.state.

app = FastAPI(title="Smart Travel Planner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers.auth_router import router as auth_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["auth"])

from app.routers.chat_router import router as chat_router  # noqa: E402

app.include_router(chat_router, tags=["chat"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
