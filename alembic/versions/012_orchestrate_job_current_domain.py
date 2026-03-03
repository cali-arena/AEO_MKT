"""Add current_domain to domain_orchestrate_job for EVALUATING status.

Revision ID: 012_orchestrate_job_current_domain
Revises: 011_domain_orchestrate_job
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_orchestrate_job_current_domain"
down_revision: Union[str, None] = "011_domain_orchestrate_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domain_orchestrate_job",
        sa.Column("current_domain", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domain_orchestrate_job", "current_domain")
