import uuid

from sqlalchemy import select

from app.modules.imports.engine import ImportRow
from app.modules.imports.service import confirm_import, existing_normalized_texts
from app.modules.texts.models import Text, TextVersion
from app.modules.users.models import User, UserRole


def make_admin(db_session) -> User:
    admin = User(email=f"{uuid.uuid4()}@phrasefluency.app", password_hash="x", role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.flush()
    return admin


class TestConfirmImport:
    def test_imports_valid_rows_and_reports_counts(self, db_session):
        admin = make_admin(db_session)
        rows = [
            ImportRow(french_text="Bonjour le monde"),
            ImportRow(french_text="  BONJOUR LE MONDE  "),  # duplicate within batch
            ImportRow(french_text=""),  # invalid
        ]

        batch = confirm_import(db_session, filename="test.csv", rows=rows, imported_by=admin.id)

        assert batch.total_rows == 3
        assert batch.imported_count == 1
        assert batch.duplicate_count == 1
        assert batch.rejected_count == 1

        created = db_session.scalars(
            select(TextVersion).where(TextVersion.french_text == "Bonjour le monde")
        ).all()
        assert len(created) == 1

    def test_created_text_has_current_version_set(self, db_session):
        admin = make_admin(db_session)
        confirm_import(
            db_session, filename="t.csv", rows=[ImportRow(french_text="Salut")], imported_by=admin.id
        )

        text = db_session.scalar(select(Text).join(TextVersion, Text.current_version_id == TextVersion.id))
        assert text is not None
        assert text.current_version.french_text == "Salut"

    def test_second_import_dedupes_against_first(self, db_session):
        admin = make_admin(db_session)
        confirm_import(
            db_session, filename="t.csv", rows=[ImportRow(french_text="Bonjour")], imported_by=admin.id
        )
        second = confirm_import(
            db_session, filename="t2.csv", rows=[ImportRow(french_text="bonjour")], imported_by=admin.id
        )

        assert second.imported_count == 0
        assert second.duplicate_count == 1


class TestExistingNormalizedTexts:
    def test_only_includes_enabled_texts(self, db_session):
        admin = make_admin(db_session)
        confirm_import(
            db_session, filename="t.csv", rows=[ImportRow(french_text="Bonjour")], imported_by=admin.id
        )
        text = db_session.scalar(select(Text))
        text.enabled = False
        db_session.flush()

        assert "bonjour" not in existing_normalized_texts(db_session)
