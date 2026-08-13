"""add A1 A2 C2 to difficulty enum

Revision ID: 11659f8715cf
Revises: 4a1b09e6902a
Create Date: 2026-08-11 22:50:29.887016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '11659f8715cf'
down_revision: Union[str, None] = '4a1b09e6902a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE difficulty ADD VALUE IF NOT EXISTS 'A1' BEFORE 'B1'")
    op.execute("ALTER TYPE difficulty ADD VALUE IF NOT EXISTS 'A2' BEFORE 'B1'")
    op.execute("ALTER TYPE difficulty ADD VALUE IF NOT EXISTS 'C2' AFTER 'C1'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enum types; removing A1/A2/C2 would
    # require rebuilding the type and is not supported by this migration.
    raise NotImplementedError("Cannot downgrade: Postgres cannot drop enum values")
