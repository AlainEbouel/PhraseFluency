import uuid

import pytest

from app.modules.users.models import UserRole
from app.modules.users.service import (
    create_user,
    get_user_by_email,
    set_user_active,
    update_preferences,
)


class TestCreateUser:
    def test_new_user_is_active_by_default(self, db_session):
        user = create_user(db_session, "new.user@example.com", "password123")

        assert user.is_active is True
        assert user.role == UserRole.USER

    def test_role_can_be_set_at_creation(self, db_session):
        user = create_user(db_session, "admin2@example.com", "password123", role=UserRole.ADMIN)

        assert user.role == UserRole.ADMIN

    def test_can_be_looked_up_by_email_afterwards(self, db_session):
        create_user(db_session, "lookup@example.com", "password123")

        found = get_user_by_email(db_session, "lookup@example.com")

        assert found is not None
        assert found.email == "lookup@example.com"


class TestSetUserActive:
    def test_disables_an_active_user(self, db_session):
        user = create_user(db_session, "target@example.com", "password123")

        updated = set_user_active(db_session, user.id, False)

        assert updated.is_active is False

    def test_reenables_a_disabled_user(self, db_session):
        user = create_user(db_session, "target2@example.com", "password123")
        set_user_active(db_session, user.id, False)

        updated = set_user_active(db_session, user.id, True)

        assert updated.is_active is True

    def test_raises_for_an_unknown_user(self, db_session):
        with pytest.raises(ValueError):
            set_user_active(db_session, uuid.uuid4(), False)

    def test_admin_cannot_disable_their_own_account(self, db_session):
        admin = create_user(db_session, "self@example.com", "password123", role=UserRole.ADMIN)

        with pytest.raises(ValueError):
            set_user_active(db_session, admin.id, False, acting_user_id=admin.id)

    def test_admin_can_disable_a_different_account(self, db_session):
        admin = create_user(db_session, "admin3@example.com", "password123", role=UserRole.ADMIN)
        other = create_user(db_session, "other@example.com", "password123")

        updated = set_user_active(db_session, other.id, False, acting_user_id=admin.id)

        assert updated.is_active is False


class TestUpdatePreferences:
    def test_sets_a_new_key(self, db_session):
        user = create_user(db_session, "prefs1@example.com", "password123")

        updated = update_preferences(db_session, user.id, {"dictation_enabled": True})

        assert updated.preferences["dictation_enabled"] is True

    def test_partial_update_preserves_other_keys(self, db_session):
        user = create_user(db_session, "prefs2@example.com", "password123")
        update_preferences(db_session, user.id, {"sound_effects_enabled": False})

        updated = update_preferences(db_session, user.id, {"dictation_enabled": True})

        assert updated.preferences["sound_effects_enabled"] is False
        assert updated.preferences["dictation_enabled"] is True

    def test_rejects_disabling_both_exercise_modes(self, db_session):
        user = create_user(db_session, "prefs3@example.com", "password123")

        with pytest.raises(ValueError):
            update_preferences(
                db_session, user.id, {"translation_enabled": False, "dictation_enabled": False}
            )

    def test_disabling_translation_is_fine_if_dictation_is_on(self, db_session):
        user = create_user(db_session, "prefs4@example.com", "password123")

        updated = update_preferences(
            db_session, user.id, {"translation_enabled": False, "dictation_enabled": True}
        )

        assert updated.preferences["translation_enabled"] is False

    def test_raises_for_an_unknown_user(self, db_session):
        with pytest.raises(ValueError):
            update_preferences(db_session, uuid.uuid4(), {"dictation_enabled": True})
