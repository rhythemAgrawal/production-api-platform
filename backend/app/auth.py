from pathlib import Path
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from backend.config import settings
from backend.app.services import get_user_from_db

security = HTTPBearer()

def get_current_user(credentials = Depends(security)):
    token = credentials.credentials
    public_key = Path(settings.jwt_public_key_path).read_text()

    try:
        payload = jwt.decode(token, public_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = get_user_from_db(user_id)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")