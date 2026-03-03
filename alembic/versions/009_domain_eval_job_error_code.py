"""Add error_code to domain_eval_job.

Revision ID: 009_domain_eval_job_error_code
Revises: 008_domain_ingest_job
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_domain_eval_job_error_code"
down_revision: Union[str, None] = "008_domain_ingest_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("domain_eval_job", sa.Column("error_code", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("domain_eval_job", "error_code")
