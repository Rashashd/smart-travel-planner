import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict

# ── Auth ──────────────────────────────────────────────────────────────────────

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
    # Extracted from JWT — only the user_id is stored in the token
    user_id: uuid.UUID
