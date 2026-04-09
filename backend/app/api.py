from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Item
from backend.app.schemas import ItemCreate, ItemRead

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
