import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.schemas import (
    ImportBatchOut,
    TextDetailOut,
    TextSummaryOut,
    TextVersionOut,
    UpdateTextVersionIn,
    UserSummaryOut,
)
from app.modules.auth.dependencies import require_admin
from app.modules.imports.models import ImportBatch
from app.modules.texts import service as texts_service
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _text_detail(db: Session, text_id: uuid.UUID) -> TextDetailOut:
    result = texts_service.get_text_with_versions(db, text_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Text not found")
    text, versions = result
    current = next(v for v in versions if v.id == text.current_version_id)
    return TextDetailOut(
        id=text.id,
        enabled=text.enabled,
        current_version=TextVersionOut.model_validate(current),
        version_history=[TextVersionOut.model_validate(v) for v in versions],
    )


@router.get("/texts", response_model=list[TextSummaryOut])
def list_texts(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    texts = texts_service.list_texts(db, search=search)
    return [
        TextSummaryOut(
            id=t.id,
            french_text=t.current_version.french_text,
            difficulty=t.current_version.difficulty,
            exercise_type=t.current_version.exercise_type,
            enabled=t.enabled,
            created_at=t.created_at,
        )
        for t in texts
    ]


@router.get("/texts/{text_id}", response_model=TextDetailOut)
def text_detail(
    text_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    return _text_detail(db, text_id)


@router.patch("/texts/{text_id}/disable", response_model=TextDetailOut)
def disable_text(
    text_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    try:
        texts_service.set_text_enabled(db, text_id, False)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _text_detail(db, text_id)


@router.patch("/texts/{text_id}/enable", response_model=TextDetailOut)
def enable_text(
    text_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    try:
        texts_service.set_text_enabled(db, text_id, True)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _text_detail(db, text_id)


@router.post(
    "/texts/{text_id}/versions", response_model=TextDetailOut, status_code=status.HTTP_201_CREATED
)
def edit_text(
    text_id: uuid.UUID,
    payload: UpdateTextVersionIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        texts_service.create_new_version(db, text_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _text_detail(db, text_id)


@router.get("/import-batches", response_model=list[ImportBatchOut])
def list_import_batches(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    batches = db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc())).all()
    return [ImportBatchOut.model_validate(b) for b in batches]


@router.get("/users", response_model=list[UserSummaryOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    return [UserSummaryOut.model_validate(u) for u in users]
