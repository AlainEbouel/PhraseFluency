from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.imports import parsing
from app.modules.imports.engine import ImportRow
from app.modules.imports.schemas import (
    ImportConfirmIn,
    ImportConfirmOut,
    ImportPreviewOut,
    ImportRowPreview,
)
from app.modules.imports.service import confirm_import, preview_rows
from app.modules.users.models import User

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@router.post("/preview", response_model=ImportPreviewOut)
async def preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ImportPreviewOut:
    content = await file.read()
    try:
        rows = parsing.parse_file(file.filename or "", content)
    except parsing.ImportParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    results = preview_rows(db, rows)
    return ImportPreviewOut(
        filename=file.filename or "",
        rows=[ImportRowPreview(**result.__dict__) for result in results],
        total_rows=len(results),
        valid_count=sum(1 for r in results if r.status == "VALID"),
        duplicate_count=sum(1 for r in results if r.status == "DUPLICATE"),
        invalid_count=sum(1 for r in results if r.status == "INVALID"),
    )


@router.post("/confirm", response_model=ImportConfirmOut)
def confirm(
    payload: ImportConfirmIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ImportConfirmOut:
    rows = [
        ImportRow(
            french_text=row.french_text,
            difficulty=row.difficulty,
            exercise_type=row.exercise_type,
            contexts=row.contexts,
            grammar_concepts=row.grammar_concepts,
            skills=row.skills,
        )
        for row in payload.rows
    ]
    batch = confirm_import(db, filename=payload.filename, rows=rows, imported_by=admin.id)
    return ImportConfirmOut(
        import_batch_id=batch.id,
        total_rows=batch.total_rows,
        imported_count=batch.imported_count,
        duplicate_count=batch.duplicate_count,
        rejected_count=batch.rejected_count,
    )
