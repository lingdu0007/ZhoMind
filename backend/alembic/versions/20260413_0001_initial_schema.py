"""initial schema for users/sessions/messages/documents/document_jobs

Revision ID: 20260413_0001
Revises: 
Create Date: 2026-04-13 00:00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260413_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('admin','user')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("message_count >= 0", name="ck_sessions_message_count"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_session_id", "sessions", ["session_id"], unique=True)
    op.create_index("ix_sessions_updated_at", "sessions", ["updated_at"], unique=False)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rag_trace", sa.JSON(), nullable=True),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_message_id", "messages", ["message_id"], unique=True)
    op.create_index("ix_messages_session_id", "messages", ["session_id"], unique=False)
    op.create_index("ix_messages_timestamp", "messages", ["timestamp"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("chunk_strategy", sa.String(length=16), nullable=False, server_default="general"),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("file_size >= 0", name="ck_documents_file_size"),
        sa.CheckConstraint("chunk_count IS NULL OR chunk_count >= 0", name="ck_documents_chunk_count"),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','failed','deleting')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint(
            "chunk_strategy IN ('padding','general','book','paper','resume','table','qa')",
            name="ck_documents_chunk_strategy",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_document_id", "documents", ["document_id"], unique=True)
    op.create_index("ix_documents_filename", "documents", ["filename"], unique=False)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index("ix_documents_uploaded_at", "documents", ["uploaded_at"], unique=False)

    op.create_table(
        "document_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=16), nullable=False, server_default="uploaded"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_document_jobs_progress"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')",
            name="ck_document_jobs_status",
        ),
        sa.CheckConstraint(
            "stage IN ('uploaded','parsing','chunking','embedding','indexing','completed','failed')",
            name="ck_document_jobs_stage",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_jobs_job_id", "document_jobs", ["job_id"], unique=True)
    op.create_index("ix_document_jobs_document_id", "document_jobs", ["document_id"], unique=False)
    op.create_index("ix_document_jobs_status", "document_jobs", ["status"], unique=False)
    op.create_index("ix_document_jobs_created_at", "document_jobs", ["created_at"], unique=False)
    op.create_index("ix_document_jobs_updated_at", "document_jobs", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_jobs_updated_at", table_name="document_jobs")
    op.drop_index("ix_document_jobs_created_at", table_name="document_jobs")
    op.drop_index("ix_document_jobs_status", table_name="document_jobs")
    op.drop_index("ix_document_jobs_document_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_job_id", table_name="document_jobs")
    op.drop_table("document_jobs")

    op.drop_index("ix_documents_uploaded_at", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_filename", table_name="documents")
    op.drop_index("ix_documents_document_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_messages_timestamp", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_index("ix_messages_message_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_updated_at", table_name="sessions")
    op.drop_index("ix_sessions_session_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
