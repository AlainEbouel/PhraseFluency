import uuid

from app.modules.texts.models import Difficulty, ExerciseType, Text, TextVersion
from app.modules.texts.service import (
    create_new_version,
    find_duplicate_texts,
    get_text_with_versions,
    list_texts,
    set_text_enabled,
)


def make_text(db_session, french_text=None, difficulty=Difficulty.B2) -> Text:
    text = Text(source="test")
    db_session.add(text)
    db_session.flush()
    version = TextVersion(
        text_id=text.id,
        french_text=french_text or f"Texte {uuid.uuid4()}",
        exercise_type=ExerciseType.TRANSLATION,
        difficulty=difficulty,
        contexts=[],
    )
    db_session.add(version)
    db_session.flush()
    text.current_version_id = version.id
    db_session.add(text)
    db_session.flush()
    return text


class TestListTexts:
    def test_search_filters_by_current_version_french_text(self, db_session):
        make_text(db_session, french_text="Bonjour le monde")
        make_text(db_session, french_text="Il fait beau")

        results = list_texts(db_session, search="bonjour")

        assert len(results) == 1
        assert results[0].current_version.french_text == "Bonjour le monde"

    def test_no_search_returns_all(self, db_session):
        make_text(db_session)
        make_text(db_session)

        results = list_texts(db_session)

        assert len(results) == 2


class TestSetTextEnabled:
    def test_disable_then_enable(self, db_session):
        text = make_text(db_session)

        disabled = set_text_enabled(db_session, text.id, False)
        assert disabled.enabled is False

        enabled = set_text_enabled(db_session, text.id, True)
        assert enabled.enabled is True

    def test_missing_text_raises(self, db_session):
        try:
            set_text_enabled(db_session, uuid.uuid4(), False)
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestCreateNewVersion:
    def test_creates_version_and_updates_current_pointer(self, db_session):
        text = make_text(db_session, french_text="Old text")
        old_version_id = text.current_version_id

        new_version = create_new_version(
            db_session, text.id, french_text="New corrected text", difficulty=Difficulty.C1,
        )

        db_session.refresh(text)
        assert text.current_version_id == new_version.id
        assert text.current_version_id != old_version_id

    def test_old_version_still_exists_for_history(self, db_session):
        text = make_text(db_session, french_text="Old text")
        old_version_id = text.current_version_id

        create_new_version(db_session, text.id, french_text="New text", difficulty=Difficulty.B1)

        _, versions = get_text_with_versions(db_session, text.id)
        version_ids = [v.id for v in versions]
        assert old_version_id in version_ids
        assert len(versions) == 2

    def test_missing_text_raises(self, db_session):
        try:
            create_new_version(db_session, uuid.uuid4(), french_text="x", difficulty=Difficulty.B1)
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestFindDuplicateTexts:
    def test_scopes_to_the_requested_difficulty(self, db_session):
        make_text(db_session, french_text="Bonjour le monde", difficulty=Difficulty.B2)
        make_text(db_session, french_text="Bonjour le monde", difficulty=Difficulty.C1)

        groups = find_duplicate_texts(db_session, Difficulty.B2)

        assert groups == []

    def test_a_single_text_is_not_a_duplicate_of_itself(self, db_session):
        make_text(db_session, french_text="Bonjour le monde")

        assert find_duplicate_texts(db_session, Difficulty.B2) == []

    def test_ignores_disabled_texts(self, db_session):
        survivor = make_text(db_session, french_text="Bonjour le monde")
        dupe = make_text(db_session, french_text="bonjour   le monde")
        set_text_enabled(db_session, dupe.id, False)

        assert find_duplicate_texts(db_session, Difficulty.B2) == []
        assert survivor.enabled is True

    def test_groups_normalized_duplicates_keeping_the_oldest_as_survivor(self, db_session):
        survivor = make_text(db_session, french_text="Bonjour le monde")
        dupe = make_text(db_session, french_text="  BONJOUR   le monde  ")

        groups = find_duplicate_texts(db_session, Difficulty.B2)

        assert len(groups) == 1
        assert groups[0].survivor_id == survivor.id
        assert groups[0].duplicate_ids == [dupe.id]
