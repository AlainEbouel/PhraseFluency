import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.engine import ImportRow, RowResult, normalize_french_text, validate_and_dedupe_rows
from app.modules.imports.models import ImportBatch
from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion


def existing_normalized_texts(db: Session) -> set[str]:
    rows = db.execute(
        select(TextVersion.french_text)
        .join(Text, Text.current_version_id == TextVersion.id)
        .where(Text.enabled.is_(True))
    ).scalars().all()
    return {normalize_french_text(text) for text in rows}


def preview_rows(db: Session, rows: list[ImportRow]) -> list[RowResult]:
    return validate_and_dedupe_rows(rows, existing_normalized_texts(db))


def confirm_import(
    db: Session, *, filename: str, rows: list[ImportRow], imported_by: uuid.UUID
) -> ImportBatch:
    results = validate_and_dedupe_rows(rows, existing_normalized_texts(db))

    imported_count = 0
    duplicate_count = 0
    rejected_count = 0

    for result in results:
        if result.status == "VALID":
            text = Text(source="import")
            db.add(text)
            db.flush()

            version = TextVersion(
                text_id=text.id,
                french_text=result.french_text,
                exercise_type=ExerciseType(result.exercise_type),
                difficulty=Difficulty(result.difficulty),
                contexts=result.contexts,
                grammar_concepts=result.grammar_concepts,
                skills=result.skills,
            )
            db.add(version)
            db.flush()

            text.current_version_id = version.id
            db.add(text)
            imported_count += 1
        elif result.status == "DUPLICATE":
            duplicate_count += 1
        else:
            rejected_count += 1

    batch = ImportBatch(
        filename=filename,
        imported_by=imported_by,
        total_rows=len(results),
        imported_count=imported_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch
