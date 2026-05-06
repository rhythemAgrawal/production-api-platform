from pathlib import Path
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from backend.config import settings
from backend.app.services import get_user_from_db
from backend.app.database import get_db
from backend.app.models import User

security = HTTPBearer()

def get_current_user(credentials = Depends(security), db : Session = Depends(get_db)) -> User:
    token = credentials.credentials
    public_key = Path(settings.jwt_public_key_path).read_text()

    try:
        payload = jwt.decode(token, public_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = get_user_from_db(user_id, db)

        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user
    
def extract_identity(request):
    auth = request.headers.get("Authorization")
    token = None

    if auth and auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
    
    if not token:
        return "anonymous"

    public_key = Path(settings.jwt_public_key_path).read_text()

    try:
        payload = jwt.decode(token, public_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub", "anonymous")
    except:
        user_id = "anonymous"
    
    return user_id