import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import make_session_factory
from app.core.models import User
from app.services.auth import decode_token

# opens new AsyncSession, closes on response done
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    # Opens a session for the request and closes it when the response is sent
    factory = make_session_factory(request.app.state.engine)
    async with factory() as session:
        yield session


def get_openai(request: Request) -> AsyncOpenAI:
    return request.app.state.openai


def get_classifier(request: Request) -> object:
    return request.app.state.classifier

# returns agent from app state, which is initialized at startup and shared across requests
def get_agent(request: Request) -> object:
    return request.app.state.agent


# OAuth2 scheme: reads the Bearer token from the Authorization header
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# this dep, reads jwt of user then looks him up in the db
async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    # Decode the JWT, look up the user, raise 401 on any failure
    try:
        user_id: uuid.UUID = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")

    return user


# Convenience type aliases for route signatures so that they don't have to repeat the Depends() everywhere
SettingsDep = Annotated[Settings, Depends(get_settings)]
DBDep = Annotated[AsyncSession, Depends(get_db)]
OpenAIDep = Annotated[AsyncOpenAI, Depends(get_openai)]
ClassifierDep = Annotated[object, Depends(get_classifier)]
AgentDep = Annotated[object, Depends(get_agent)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
