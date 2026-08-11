from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.modules.auth.models import Session as SessionModel
from app.modules.users.models import User
from app.shared.mixins import utcnow

settings = get_settings()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User) -> str:
    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
    )
    user.last_login_at = utcnow()
    db.add(session)
    db.add(user)
    db.commit()
    return token


def get_user_by_session_token(db: Session, token: str) -> User | None:
    token_hash = hash_session_token(token)
    session = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    if session is None or session.revoked_at is not None:
        return None
    if session.expires_at < utcnow():
        return None
    return db.get(User, session.user_id)


def revoke_session(db: Session, token: str) -> None:
    token_hash = hash_session_token(token)
    session = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    if session is not None:
        session.revoked_at = utcnow()
        db.add(session)
        db.commit()
