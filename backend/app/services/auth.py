import datetime as dt
import hashlib
import uuid

import bcrypt
from jose import jwt

from app.core.config import get_settings

ACCESS_TOKEN_EXPIRE_HOURS = 24


def _prepare(password: str) -> bytes:
    # SHA-256 pre-hash → 32 bytes, always within bcrypt's 72-byte limit
    return hashlib.sha256(password.encode()).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(_prepare(plain), hashed.encode())


def create_access_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algo)


def decode_token(token: str) -> uuid.UUID:
    # Raises JWTError if token is invalid or expired — caught in get_current_user
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algo])
    return uuid.UUID(payload["sub"])
