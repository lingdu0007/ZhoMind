from src.domain.enums import DocumentStatus, JobStatus
from src.infrastructure.db.models import DocumentModel, IngestionJobModel


def test_document_and_job_statuses_are_separate() -> None:
    assert DocumentStatus.READY.value == "ready"
    assert DocumentStatus.UPLOADED.can_transition_to(DocumentStatus.QUEUED) is True
    assert DocumentStatus.DELETED.can_transition_to(DocumentStatus.READY) is False
    assert JobStatus.SUCCEEDED.value == "succeeded"
    assert JobStatus.SUCCEEDED.is_terminal() is True
    assert DocumentModel.__tablename__ == "documents"
    assert IngestionJobModel.__tablename__ == "ingestion_jobs"
