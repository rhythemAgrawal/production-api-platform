from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import Depends

from backend.app.database import get_db
from backend.app.models import User


def get_user_from_db(user_id, db: Session = Depends(get_db)):
    get_user_query = select(User).where(User.id == user_id)
    user = db.execute(get_user_query).scalars().all()

    return user[0] if user else None