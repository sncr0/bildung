"""Entity tables for works, authors, collections, streams, series.

Revision ID: 002
Revises: 001
Create Date: 2026-04-28
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Entity tables ---

    op.create_table(
        "authors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("birth_year", sa.INTEGER(), nullable=True),
        sa.Column("death_year", sa.INTEGER(), nullable=True),
        sa.Column("nationality", sa.VARCHAR(), nullable=True),
        sa.Column("primary_language", sa.VARCHAR(), nullable=True),
        sa.Column("openlibrary_id", sa.VARCHAR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "works",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.TEXT(), nullable=False),
        sa.Column("status", sa.VARCHAR(), nullable=False, server_default="to_read"),
        sa.Column("language_read_in", sa.VARCHAR(), nullable=True),
        sa.Column("date_read", sa.VARCHAR(), nullable=True),
        sa.Column("density_rating", sa.VARCHAR(), nullable=True),
        sa.Column("source_type", sa.VARCHAR(), nullable=False, server_default="fiction"),
        sa.Column("personal_note", sa.TEXT(), nullable=True),
        sa.Column("edition_note", sa.TEXT(), nullable=True),
        sa.Column("significance", sa.VARCHAR(), nullable=True),
        sa.Column("page_count", sa.INTEGER(), nullable=True),
        sa.Column("year_published", sa.INTEGER(), nullable=True),
        sa.Column("original_language", sa.VARCHAR(), nullable=True),
        sa.Column("original_title", sa.TEXT(), nullable=True),
        sa.Column("openlibrary_id", sa.VARCHAR(), nullable=True),
        sa.Column("isbn", sa.VARCHAR(), nullable=True),
        sa.Column("cover_url", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("type", sa.VARCHAR(), nullable=False, server_default="anthology"),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "streams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("color", sa.VARCHAR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "series",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Junction tables ---

    op.create_table(
        "work_authors",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.PrimaryKeyConstraint("work_id", "author_id"),
    )

    op.create_table(
        "work_collections",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"]),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"]),
        sa.PrimaryKeyConstraint("work_id", "collection_id"),
    )

    op.create_table(
        "work_streams",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stream_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"]),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"]),
        sa.PrimaryKeyConstraint("work_id", "stream_id"),
    )

    op.create_table(
        "collection_streams",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stream_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"]),
        sa.ForeignKeyConstraint(["stream_id"], ["streams.id"]),
        sa.PrimaryKeyConstraint("collection_id", "stream_id"),
    )

    op.create_table(
        "work_series",
        sa.Column("work_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("series_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order", sa.INTEGER(), nullable=True),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"]),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"]),
        sa.PrimaryKeyConstraint("work_id", "series_id"),
    )

    # --- Indexes ---

    op.create_index("idx_works_status", "works", ["status"])
    op.create_index("idx_works_title", "works", ["title"])
    op.create_index("idx_authors_name", "authors", ["name"])
    op.create_index("idx_collections_type", "collections", ["type"])
    op.create_index("idx_collections_author", "collections", ["author_id"])


def downgrade() -> None:
    op.drop_index("idx_collections_author", table_name="collections")
    op.drop_index("idx_collections_type", table_name="collections")
    op.drop_index("idx_authors_name", table_name="authors")
    op.drop_index("idx_works_title", table_name="works")
    op.drop_index("idx_works_status", table_name="works")

    op.drop_table("work_series")
    op.drop_table("collection_streams")
    op.drop_table("work_streams")
    op.drop_table("work_collections")
    op.drop_table("work_authors")
    op.drop_table("series")
    op.drop_table("streams")
    op.drop_table("collections")
    op.drop_table("works")
    op.drop_table("authors")
