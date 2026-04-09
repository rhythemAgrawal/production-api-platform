from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemRead(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}

class UserRead(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}

class UserCreate(BaseModel):
    username: str
    password: str

