from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    deleting = "deleting"


class ChunkStrategy(str, Enum):
    padding = "padding"
    general = "general"
    book = "book"
    paper = "paper"
    resume = "resume"
    table = "table"
    qa = "qa"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class JobStage(str, Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    chunking = "chunking"
    embedding = "embedding"
    indexing = "indexing"
    completed = "completed"
    failed = "failed"
