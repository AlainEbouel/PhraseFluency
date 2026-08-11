from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import authenticate_user, create_session, revoke_session
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_session(db, user)
    _set_session_cookie(response, token)
    return user


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    if token is not None:
        revoke_session(db, token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
