from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("role IN ('admin','user')", name="ck_users_role"),)


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("message_count >= 0", name="ck_sessions_message_count"),)


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    rag_trace: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (CheckConstraint("role IN ('user','assistant')", name="ck_messages_role"),)


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(512), index=True)
    file_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    chunk_strategy: Mapped[str] = mapped_column(String(16), default="general")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("file_size >= 0", name="ck_documents_file_size"),
        CheckConstraint("chunk_count IS NULL OR chunk_count >= 0", name="ck_documents_chunk_count"),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed','deleting')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "chunk_strategy IN ('padding','general','book','paper','resume','table','qa')",
            name="ck_documents_chunk_strategy",
        ),
    )


class DocumentJobModel(Base):
    __tablename__ = "document_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(16), default="uploaded")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_document_jobs_progress"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','canceled')",
            name="ck_document_jobs_status",
        ),
        CheckConstraint(
            "stage IN ('uploaded','parsing','chunking','embedding','indexing','completed','failed')",
            name="ck_document_jobs_stage",
        ),
    )
