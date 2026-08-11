from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.users.schemas import UserCreate, UserOut
from app.modules.users.service import create_user, get_user_by_email

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return create_user(db, payload.email, payload.password, payload.role)
