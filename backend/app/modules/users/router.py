from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import PreferencesIn, UserOut

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch("/me/preferences", response_model=UserOut)
def update_my_preferences(
    payload: PreferencesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        updated = service.update_preferences(
            db, user.id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return updated
