import asyncio

from fastapi.testclient import TestClient

from src.application.document_service import DocumentService, DocumentTaskExecutor
from src.main import app
from src.infrastructure.logging.observability import bind_context
from src.shared.request_context import request_id_ctx


class _QueueStub:
    def __init__(self) -> None:
        self.items: list[tuple[str, dict]] = []

    async def enqueue(self, task_name: str, payload: dict) -> None:
        self.items.append((task_name, payload))


client = TestClient(app)


def test_chat_stream_meta_uses_header_request_id() -> None:
    request_id = "req_obs_chat_stream_001"
    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        headers={"x-request-id": request_id},
        json={"message": "hello"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["x-request-id"] == request_id
        body = "".join(response.iter_text())
        assert f'"request_id": "{request_id}"' in body


def test_document_upload_enqueues_request_id() -> None:
    async def _run() -> None:
        queue = _QueueStub()
        service = DocumentService(queue_runner=queue)
        with bind_context(request_id="req_obs_upload_001"):
            await service.create_upload_job(
                filename="demo.txt",
                file_type="text/plain",
                content=b"hello",
            )
        assert queue.items
        _, payload = queue.items[0]
        assert payload["request_id"] == "req_obs_upload_001"

    asyncio.run(_run())


def test_worker_restores_request_id_from_payload(monkeypatch) -> None:
    async def _run() -> None:
        queue = _QueueStub()
        service = DocumentService(queue_runner=queue)
        accepted = await service.create_upload_job(
            filename="demo.txt",
            file_type="text/plain",
            content=b"hello",
        )

        executor = DocumentTaskExecutor(service=service)
        observed: dict[str, str] = {}

        async def _fake_process(job_id: str) -> None:
            _ = job_id
            observed["request_id"] = request_id_ctx.get()

        monkeypatch.setattr(service, "process_build_job", _fake_process)
        await executor.execute(
            "document.build",
            {"job_id": accepted["job_id"], "request_id": "req_obs_worker_001"},
        )
        assert observed["request_id"] == "req_obs_worker_001"

    asyncio.run(_run())
