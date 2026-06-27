"""create job_matches table and HNSW index on jobs.embedding

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "680fa3a8317e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("ats_score", sa.Float(), nullable=True),
        sa.Column("skill_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("new", "saved", "applied", "dismissed", name="matchstatus"),
            nullable=False,
            server_default="new",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
    )
    op.create_index("ix_job_matches_user_id", "job_matches", ["user_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])
    op.create_index("ix_job_matches_score", "job_matches", ["score"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS jobs_embedding_hnsw ON jobs "
        "USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS jobs_embedding_hnsw")
    op.drop_index("ix_job_matches_score", table_name="job_matches")
    op.drop_index("ix_job_matches_job_id", table_name="job_matches")
    op.drop_index("ix_job_matches_user_id", table_name="job_matches")
    op.drop_table("job_matches")
    op.execute("DROP TYPE IF EXISTS matchstatus")
