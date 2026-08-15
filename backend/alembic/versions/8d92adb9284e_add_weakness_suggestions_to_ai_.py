"""add WEAKNESS_SUGGESTIONS to ai_operation enum

Revision ID: 8d92adb9284e
Revises: ca7622b7d34f
Create Date: 2026-08-14 21:54:58.152452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8d92adb9284e'
down_revision: Union[str, None] = 'ca7622b7d34f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_operation ADD VALUE IF NOT EXISTS 'WEAKNESS_SUGGESTIONS'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enum types; removing this value
    # would require rebuilding the type and is not supported here.
    raise NotImplementedError("Cannot downgrade: Postgres cannot drop enum values")
