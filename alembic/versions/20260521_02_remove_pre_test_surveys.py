"""Retire pre_test surveys and keep only post_test

Revision ID: 20260521_02
Revises: 20260521_01
Create Date: 2026-05-21
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260521_02"
down_revision = "20260521_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE survey_campaigns
        SET
          period_type = 'post_test',
          name = replace(name, 'Pre test', 'Post test')
        WHERE period_type = 'pre_test';
        """
    )

    op.execute(
        """
        DELETE FROM survey_campaigns sc
        WHERE sc.period_type = 'post_test'
          AND sc.status = 'draft'
          AND NOT EXISTS (
            SELECT 1 FROM survey_assignments sa WHERE sa.campaign_id = sc.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM survey_responses sr WHERE sr.campaign_id = sc.id
          );
        """
    )


def downgrade() -> None:
    # No destructive downgrade. The functional change intentionally retires pre_test.
    pass
