from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
import time
import jwt
import secrets
import hashlib

from backend.app.database import get_db
from backend.app.models import Item, User
from backend.app.schemas import ItemCreate, ItemRead, UserRead, UserCreate, LoginResponse

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


@router.post("/signup", response_model=UserRead, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> User:
    ph = PasswordHasher()
    hashed_password = ph.hash(user.password)
    db_user = User(name=user.username, hashed_password=hashed_password)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=LoginResponse)
def login(user: UserCreate, db: Session = Depends(get_db)) -> JSONResponse:
    db_user = db.get(User, user.username)

    if not db_user:
        raise

    ph = PasswordHasher()
    ph.verify(db_user.hashed_password, user.password)

    if ph.check_needs_rehash(db_user.hashed_password):
        new_hashed_password = ph.hash(user.password)
        db_user.hashed_password = new_hashed_password

        db.add(db_user)
        db.commit()
    
    content = UserRead.model_validate(db_user).model_dump()
    
    payload = {
        "sub": db_user.id,
        "iat": time.time(),
        "exp": time.time() + 600
    }

    private_key = "private_key"
    token = jwt.encode(payload, private_key, algorithm="RS256")
    content.update({
        "access_token": token,
        "token_type": "bearer"
    })

    response = JSONResponse(content=content)
    refresh_token = secrets.token_urlsafe(32)
    hashed_refresh_token = hashlib.sha256(refresh_token.encode()).hexdigest

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict"
    )
    
    return response