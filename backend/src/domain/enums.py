from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"

    def can_transition_to(self, next_status: "DocumentStatus") -> bool:
        allowed_transitions = {
            DocumentStatus.UPLOADED: {DocumentStatus.QUEUED, DocumentStatus.DELETING, DocumentStatus.DELETED},
            DocumentStatus.QUEUED: {DocumentStatus.BUILDING, DocumentStatus.FAILED, DocumentStatus.DELETING},
            DocumentStatus.BUILDING: {DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.DELETING},
            DocumentStatus.READY: {DocumentStatus.QUEUED, DocumentStatus.DELETING, DocumentStatus.DELETED},
            DocumentStatus.FAILED: {DocumentStatus.QUEUED, DocumentStatus.DELETING, DocumentStatus.DELETED},
            DocumentStatus.DELETING: {DocumentStatus.DELETED, DocumentStatus.FAILED},
            DocumentStatus.DELETED: set(),
        }
        return next_status in allowed_transitions[self]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    def is_terminal(self) -> bool:
        return self in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
