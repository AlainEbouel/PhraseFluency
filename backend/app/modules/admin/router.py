import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin.schemas import (
    DuplicateGroupOut,
    DuplicatesPreviewOut,
    DuplicatesResolveOut,
    ImportBatchOut,
    SharedSentenceGroupOut,
    SharedSentenceTextOut,
    SharedSentencesPreviewOut,
    TextDetailOut,
    TextSummaryOut,
    TextVersionOut,
    UpdateTextVersionIn,
    UserSummaryOut,
    UserTextBankItemOut,
)
from app.modules.auth.dependencies import require_admin
from app.modules.imports.models import ImportBatch
from app.modules.learning import service as learning_service
from app.modules.learning.models import UserTextProgress
from app.modules.texts import service as texts_service
from app.modules.texts.models import Difficulty, Text
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserOut

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


@router.get("/texts/duplicates", response_model=DuplicatesPreviewOut)
def preview_duplicate_texts(
    difficulty: Difficulty,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    groups = texts_service.find_duplicate_texts(db, difficulty)
    out_groups = []
    for group in groups:
        affected_user_count = db.scalar(
            select(func.count())
            .select_from(UserTextProgress)
            .where(UserTextProgress.text_id.in_(group.duplicate_ids))
        )
        out_groups.append(
            DuplicateGroupOut(
                french_text=group.french_text,
                survivor_id=group.survivor_id,
                duplicate_count=len(group.duplicate_ids),
                affected_user_count=affected_user_count,
            )
        )
    return DuplicatesPreviewOut(difficulty=difficulty, groups=out_groups)


@router.post("/texts/duplicates/resolve", response_model=DuplicatesResolveOut)
def resolve_duplicate_texts(
    difficulty: Difficulty,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = learning_service.resolve_duplicate_texts(db, difficulty)
    return DuplicatesResolveOut(
        groups_resolved=result.groups_resolved,
        texts_disabled=result.texts_disabled,
        users_affected=result.users_affected,
    )


@router.get("/texts/shared-sentences", response_model=SharedSentencesPreviewOut)
def preview_shared_sentence_texts(
    difficulty: Difficulty,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    groups = texts_service.find_shared_sentence_texts(db, difficulty)
    out_groups = []
    for group in groups:
        texts_out = []
        for text_id in group.text_ids:
            text = db.get(Text, text_id)
            affected_user_count = db.scalar(
                select(func.count())
                .select_from(UserTextProgress)
                .where(UserTextProgress.text_id == text_id)
            )
            texts_out.append(
                SharedSentenceTextOut(
                    id=text.id,
                    french_text=text.current_version.french_text,
                    enabled=text.enabled,
                    affected_user_count=affected_user_count,
                )
            )
        out_groups.append(SharedSentenceGroupOut(sentence=group.sentence, texts=texts_out))
    return SharedSentencesPreviewOut(difficulty=difficulty, groups=out_groups)


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


@router.post("/texts/{text_id}/disable-everywhere", response_model=TextDetailOut)
def disable_text_everywhere(
    text_id: uuid.UUID, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    try:
        learning_service.disable_text_globally(db, text_id)
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


def _user_summary(user: User, active_text_count: int) -> UserSummaryOut:
    return UserSummaryOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        active_text_count=active_text_count,
    )


@router.get("/users", response_model=list[UserSummaryOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.scalars(select(User).order_by(User.created_at)).all()
    counts = learning_service.active_text_counts(db)
    return [_user_summary(u, counts.get(u.id, 0)) for u in users]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if users_service.get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return users_service.create_user(db, payload.email, payload.password, payload.role)


@router.patch("/users/{user_id}/disable", response_model=UserSummaryOut)
def disable_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if user_id == _admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot disable your own account")
    try:
        user = users_service.set_user_active(db, user_id, False, acting_user_id=_admin.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _user_summary(user, learning_service.active_text_counts(db).get(user.id, 0))


@router.patch("/users/{user_id}/enable", response_model=UserSummaryOut)
def enable_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        user = users_service.set_user_active(db, user_id, True)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _user_summary(user, learning_service.active_text_counts(db).get(user.id, 0))


def _bank_item(row: tuple) -> UserTextBankItemOut:
    text_id, french_text, status_, natural_count, incorrect_count, times_presented = row
    return UserTextBankItemOut(
        text_id=text_id,
        french_text=french_text,
        status=status_,
        natural_count=natural_count,
        incorrect_count=incorrect_count,
        times_presented=times_presented,
    )


@router.get("/users/{user_id}/texts", response_model=list[UserTextBankItemOut])
def get_user_text_bank(
    user_id: uuid.UUID,
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    rows = learning_service.list_user_text_bank(db, user_id, search=search)
    return [_bank_item(row) for row in rows]


@router.patch("/users/{user_id}/texts/{text_id}/disable", response_model=UserTextBankItemOut)
def disable_user_text(
    user_id: uuid.UUID,
    text_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    learning_service.disable_text_for_user(db, user_id, text_id)
    row = learning_service.get_user_text_bank_item(db, user_id, text_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Text not found")
    return _bank_item(row)
