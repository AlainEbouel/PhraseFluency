import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.modules.users.models import UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    created_at: datetime
    last_login_at: datetime | None
    preferences: dict

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.USER
