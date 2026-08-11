import pytest
from sqlalchemy.orm import Session

from app.core import model_registry  # noqa: F401 registers every model on Base.metadata
from app.core.database import engine


@pytest.fixture()
def db_session():
    """A session bound to a savepoint-backed transaction.

    Service functions under test call db.commit() themselves (reference
    generation, grammar explanation caching); join_transaction_mode
    ensures those commits only release a SAVEPOINT, so the whole test's
    writes are undone by the outer rollback below.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
