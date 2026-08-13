import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.users.models import User, UserRole


def create_user(db: Session, email: str, password: str, role: UserRole = UserRole.USER) -> User:
    user = User(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def set_user_active(
    db: Session, user_id: uuid.UUID, active: bool, *, acting_user_id: uuid.UUID | None = None
) -> User:
    if not active and user_id == acting_user_id:
        raise ValueError("You cannot disable your own account")
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    user.is_active = active
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def bootstrap_admin(db: Session, email: str, password: str) -> User:
    existing = get_user_by_email(db, email)
    if existing is not None:
        return existing
    return create_user(db, email, password, role=UserRole.ADMIN)
