import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

# Authentication

class UserCreate(BaseModel):
    # username field in OAuth2 form maps to email
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    created_at: dt.datetime

    # from_attributes allows building from a SQLAlchemy model instance
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    # Extracted from JWT; only the user_id is stored in the token
    user_id: uuid.UUID


# Chat

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None  # UUID string — None means start a new session


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    tool_calls: list[dict]
