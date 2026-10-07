from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from datetime import datetime, timedelta, timezone
import secrets
import hashlib

from backend.app.database import get_db
from backend.app.models import Item, User, RefreshToken
from backend.app.schemas import ItemCreate, ItemRead, UserRead, UserCreate, LoginResponse
from backend.app.auth import get_current_user, create_access_token
from backend.app.observability.instruments import login_attempts

router = APIRouter()


def build_login_response(db_user: User, db: Session, status_code: int = 200) -> JSONResponse:
    """
    Issues an access token in the body and a new refresh token in an
    HttpOnly cookie. Adds the refresh token row to the session; the caller
    commits.
    """
    content = UserRead.model_validate(db_user).model_dump()
    content.update({
        "access_token": create_access_token(db_user.id),
        "token_type": "bearer"
    })

    response = JSONResponse(content=content, status_code=status_code)
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

    return response


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/items", response_model=ItemRead, status_code=201)
def create_item(item: ItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Item:
    db_item = Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/items", response_model=list[ItemRead])
def list_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Item]:
    return db.query(Item).order_by(Item.id.desc()).all()


@router.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Item:
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")

    db.refresh(db_user)

    response = build_login_response(db_user, db, status_code=201)
    db.commit()

    return response

@router.post("/login", response_model=LoginResponse)
def login(user: UserCreate, db: Session = Depends(get_db)) -> JSONResponse:
    get_user_query = select(User).where(User.username==user.username)
    db_user = db.execute(get_user_query).scalars().first()

    if not db_user:
        login_attempts.add(1, {"outcome": "failure"})
        raise HTTPException(status_code=401, detail="Invalid username or password")

    ph = PasswordHasher()

    try:
        ph.verify(db_user.hashed_password, user.password)
    except (VerificationError, InvalidHashError):
        login_attempts.add(1, {"outcome": "failure"})
        raise HTTPException(status_code=401, detail="Invalid username or password")

    login_attempts.add(1, {"outcome": "success"})

    if ph.check_needs_rehash(db_user.hashed_password):
        new_hashed_password = ph.hash(user.password)
        db_user.hashed_password = new_hashed_password

    response = build_login_response(db_user, db)
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
def refresh(response: Response, refresh_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(get_db)) -> JSONResponse:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    hashed_refresh_token = hashlib.sha256(refresh_token.encode()).hexdigest()
    token_query = select(RefreshToken).where(RefreshToken.hashed_token == hashed_refresh_token)
    results = db.execute(token_query).scalars().all()

    if not results:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    db_token = results[0]
    db_user = db_token.user

    if db_token.revoked or db_token.expires_at < datetime.now(timezone.utc):
        revoke_query = update(RefreshToken)\
            .where(RefreshToken.user_id == db_user.id)\
            .values(revoked=True)
        db.execute(revoke_query)
        db.commit()

        # Returned, not raised: cookies set on a response are dropped when an
        # HTTPException is raised.
        response = JSONResponse(status_code=401, content={"detail": "Refresh token expired"})
        response.delete_cookie("refresh_token")
        return response

    response = build_login_response(db_user, db)
    db_token.revoked = True
    db.commit()

    return response
