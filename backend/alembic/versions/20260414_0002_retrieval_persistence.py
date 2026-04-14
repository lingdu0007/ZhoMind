"""add document_chunks and bm25_postings for retrieval persistence

Revision ID: 20260414_0002
Revises: 20260413_0001
Create Date: 2026-04-14 00:02:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260414_0002"
down_revision = "20260413_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Internal fields added for retrieval persistence and index lifecycle tracking.
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("generated_questions", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("retrieval_text", sa.Text(), nullable=False),
        sa.Column("tokens", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("index_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index"),
        sa.CheckConstraint("version >= 1", name="ck_document_chunks_version"),
        sa.CheckConstraint(
            "index_status IN ('pending','indexing','indexed','failed')",
            name="ck_document_chunks_index_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_chunk_id", "document_chunks", ["chunk_id"], unique=True)
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)
    op.create_index("ix_document_chunks_version", "document_chunks", ["version"], unique=False)
    op.create_index("ix_document_chunks_index_status", "document_chunks", ["index_status"], unique=False)

    op.create_table(
        "bm25_postings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("term", sa.String(length=128), nullable=False),
        sa.Column("tf", sa.Integer(), nullable=False),
        sa.Column("doc_len", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tf >= 1", name="ck_bm25_postings_tf"),
        sa.CheckConstraint("doc_len >= 1", name="ck_bm25_postings_doc_len"),
        sa.CheckConstraint("version >= 1", name="ck_bm25_postings_version"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.chunk_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bm25_postings_chunk_id", "bm25_postings", ["chunk_id"], unique=False)
    op.create_index("ix_bm25_postings_document_id", "bm25_postings", ["document_id"], unique=False)
    op.create_index("ix_bm25_postings_term", "bm25_postings", ["term"], unique=False)
    op.create_index("ix_bm25_postings_version", "bm25_postings", ["version"], unique=False)
    op.create_index(
        "ix_bm25_postings_term_version",
        "bm25_postings",
        ["term", "version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bm25_postings_term_version", table_name="bm25_postings")
    op.drop_index("ix_bm25_postings_version", table_name="bm25_postings")
    op.drop_index("ix_bm25_postings_term", table_name="bm25_postings")
    op.drop_index("ix_bm25_postings_document_id", table_name="bm25_postings")
    op.drop_index("ix_bm25_postings_chunk_id", table_name="bm25_postings")
    op.drop_table("bm25_postings")

    op.drop_index("ix_document_chunks_index_status", table_name="document_chunks")
    op.drop_index("ix_document_chunks_version", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_chunk_id", table_name="document_chunks")
    op.drop_table("document_chunks")
