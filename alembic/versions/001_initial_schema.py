"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-13
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reading_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.VARCHAR(), nullable=False),
        sa.Column("event_date", sa.DATE(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "xp_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("xp_type", sa.VARCHAR(), nullable=False),
        sa.Column("amount", sa.DECIMAL(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.TEXT(), nullable=False),
        sa.Column("question_type", sa.VARCHAR(), nullable=False),
        sa.Column(
            "related_work_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column(
            "related_stream_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("difficulty", sa.INTEGER(), nullable=True),
        sa.Column("max_xp", sa.DECIMAL(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_text", sa.TEXT(), nullable=False),
        sa.Column("score", sa.DECIMAL(), nullable=False),
        sa.Column("xp_earned", sa.DECIMAL(), nullable=False),
        sa.Column("llm_feedback", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "srs_schedule",
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_due", sa.DATE(), nullable=False),
        sa.Column("interval_days", sa.INTEGER(), nullable=False, server_default="1"),
        sa.Column("ease_factor", sa.DECIMAL(), nullable=False, server_default="2.5"),
        sa.Column("consecutive_correct", sa.INTEGER(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"]),
        sa.PrimaryKeyConstraint("question_id"),
    )


def downgrade() -> None:
    op.drop_table("srs_schedule")
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_questions")
    op.drop_table("xp_ledger")
    op.drop_table("reading_events")
