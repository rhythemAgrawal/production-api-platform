from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from argon2 import PasswordHasher

from backend.app.database import get_db
from backend.app.models import Item, User
from backend.app.schemas import ItemCreate, ItemRead, UserRead, UserCreate

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

@router.post("/login", response_model=UserRead)
def login(user: UserCreate, db: Session = Depends(get_db)) -> User:
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
    
    return db_user