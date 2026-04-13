from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated
from argon2 import PasswordHasher
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
import jwt
import secrets
import hashlib

from backend.app.database import get_db
from backend.app.models import Item, User, RefreshToken
from backend.app.schemas import ItemCreate, ItemRead, UserRead, UserCreate, LoginResponse
from backend.config import settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/items", response_model=ItemRead, status_code=201)
def create_item(item: ItemCreate, db: Session = Depends(get_db)) -> Item:
    db_item = Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/items", response_model=list[ItemRead])
def list_items(db: Session = Depends(get_db)) -> list[Item]:
    return db.query(Item).order_by(Item.id.desc()).all()


@router.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/signup", response_model=LoginResponse, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> JSONResponse:
    ph = PasswordHasher()
    hashed_password = ph.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    content = UserRead.model_validate(db_user).model_dump()
    
    payload = {
        "sub": str(db_user.id),
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.jwt_access_token_expires_seconds
    }

    private_key = Path(settings.jwt_private_key_path).read_text()
    token = jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)
    content.update({
        "access_token": token,
        "token_type": "bearer"
    })

    response = JSONResponse(content=content)
    refresh_token = secrets.token_urlsafe(32)
    hashed_refresh_token = hashlib.sha256(refresh_token.encode()).hexdigest()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    db_refresh_token = RefreshToken(
        user_id=db_user.id,
        hashed_token=hashed_refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
        revoked=False
    )

    db.add(db_refresh_token)
    db.commit()
    
    return response

@router.post("/login", response_model=LoginResponse)
def login(user: UserCreate, db: Session = Depends(get_db)) -> JSONResponse:
    get_user_query = select(User).where(User.username==user.username)
    db_user = db.execute(get_user_query).scalars().all()[0]

    if not db_user:
        raise

    ph = PasswordHasher()
    ph.verify(db_user.hashed_password, user.password)

    if ph.check_needs_rehash(db_user.hashed_password):
        new_hashed_password = ph.hash(user.password)
        db_user.hashed_password = new_hashed_password

        db.commit()

    content = UserRead.model_validate(db_user).model_dump()

    payload = {
        "sub": str(db_user.id),
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.jwt_access_token_expires_seconds
    }

    private_key = Path(settings.jwt_private_key_path).read_text()
    token = jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)
    content.update({
        "access_token": token,
        "token_type": "bearer"
    })

    response = JSONResponse(content=content)
    refresh_token = secrets.token_urlsafe(32)
    hashed_refresh_token = hashlib.sha256(refresh_token.encode()).hexdigest()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    db_refresh_token = RefreshToken(
        user_id=db_user.id,
        hashed_token=hashed_refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
        revoked=False
    )

    db.add(db_refresh_token)
    db.commit()
    
    return response

@router.post("/logout", status_code=204)
def logout(response: Response, refresh_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(get_db)):
    if not refresh_token:
        return

    hashed_refresh_token = hashlib.sha256(refresh_token.encode()).hexdigest()
    token_query = select(RefreshToken).where(RefreshToken.hashed_token == hashed_refresh_token)
    results = db.execute(token_query).scalars().all()

    if not results:
        return
    
    db_token = results[0]
    db_token.revoked = True
    db.commit()

    response.delete_cookie("refresh_token")

    return

@router.post("/refresh", response_model=LoginResponse)
def refresh(refresh_token: Annotated[str | None, Cookie()]):
    