from app.modules.auth.service import authenticate_user, create_session, get_user_by_session_token
from app.modules.users.service import create_user, set_user_active


class TestAuthenticateUser:
    def test_succeeds_for_an_active_user_with_correct_password(self, db_session):
        create_user(db_session, "active@example.com", "correct-password")

        user = authenticate_user(db_session, "active@example.com", "correct-password")

        assert user is not None
        assert user.email == "active@example.com"

    def test_fails_for_the_wrong_password(self, db_session):
        create_user(db_session, "active2@example.com", "correct-password")

        user = authenticate_user(db_session, "active2@example.com", "wrong-password")

        assert user is None

    def test_fails_for_a_disabled_user_even_with_correct_password(self, db_session):
        disabled = create_user(db_session, "disabled@example.com", "correct-password")
        set_user_active(db_session, disabled.id, False)

        user = authenticate_user(db_session, "disabled@example.com", "correct-password")

        assert user is None


class TestGetUserBySessionToken:
    def test_resolves_an_active_user_from_a_valid_token(self, db_session):
        user = create_user(db_session, "sess@example.com", "password123")
        token = create_session(db_session, user)

        resolved = get_user_by_session_token(db_session, token)

        assert resolved is not None
        assert resolved.id == user.id

    def test_disabling_a_user_invalidates_their_existing_session(self, db_session):
        user = create_user(db_session, "sess2@example.com", "password123")
        token = create_session(db_session, user)
        assert get_user_by_session_token(db_session, token) is not None

        set_user_active(db_session, user.id, False)

        assert get_user_by_session_token(db_session, token) is None
