from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.deps import CurrentUserDep, DBDep
from app.core.models import User
from app.core.schemas import Token, UserCreate, UserOut
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: UserCreate, db: DBDep):
    # Reject duplicate emails
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBDep):
    # OAuth2 form uses 'username' field — we treat it as email
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUserDep):
    # get_current_user in deps.py already validates the token and fetches the user
    return current_user


@router.delete("/me", status_code=204)
async def delete_account(current_user: CurrentUserDep, db: DBDep):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Anonymize instead of delete — frees the email for re-registration, data stays for analytics
    user.email = f"deleted_{user.id}@deleted"
    user.hashed_password = ""
    user.is_active = False
    await db.commit()
