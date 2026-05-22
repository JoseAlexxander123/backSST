"""Split users.name into first_name and last_name

Revision ID: 20260521_01
Revises: 20260519_01
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260521_01"
down_revision = "20260519_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE users
        SET
          first_name = COALESCE(NULLIF(split_part(trim(name), ' ', 1), ''), 'Usuario'),
          last_name = CASE
            WHEN strpos(trim(name), ' ') > 0
              THEN trim(substr(trim(name), strpos(trim(name), ' ') + 1))
            ELSE ''
          END;
        """
    )

    op.alter_column("users", "first_name", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "last_name", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("users", "name")


def downgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE users
        SET name = trim(concat_ws(' ', NULLIF(first_name, ''), NULLIF(last_name, '')));
        """
    )

    op.alter_column("users", "name", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
