import asyncio
import logging
from dataclasses import dataclass

from src.infrastructure.logging.observability import log_event

logger = logging.getLogger(__name__)


class TaskExecutor:
    async def execute(self, task_name: str, payload: dict) -> None:
        raise NotImplementedError("Task executor is not implemented")


@dataclass
class QueueTask:
    task_name: str
    payload: dict


class QueueRunner:
    def __init__(self, backend: str, executor: TaskExecutor) -> None:
        self.backend = backend
        self.executor = executor
        self._queue: asyncio.Queue[QueueTask] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._stopping = False
        self._worker_task = asyncio.create_task(self._run(), name="document-worker")

    async def stop(self) -> None:
        self._stopping = True
        if self._worker_task and not self._worker_task.done():
            await self._queue.put(QueueTask(task_name="__stop__", payload={}))
            await self._worker_task

    async def enqueue(self, task_name: str, payload: dict) -> None:
        await self._queue.put(QueueTask(task_name=task_name, payload=payload))
        log_event(
            logger,
            "INFO",
            "queue.task.enqueued",
            task_name=task_name,
            job_id=payload.get("job_id"),
            document_id=payload.get("document_id"),
            request_id=payload.get("request_id"),
        )

    async def _run(self) -> None:
        while not self._stopping:
            task = await self._queue.get()
            try:
                if task.task_name == "__stop__":
                    return
                log_event(
                    logger,
                    "INFO",
                    "queue.task.started",
                    task_name=task.task_name,
                    job_id=task.payload.get("job_id"),
                    request_id=task.payload.get("request_id"),
                )
                await self.executor.execute(task.task_name, task.payload)
                log_event(
                    logger,
                    "INFO",
                    "queue.task.completed",
                    task_name=task.task_name,
                    job_id=task.payload.get("job_id"),
                    request_id=task.payload.get("request_id"),
                )
            except Exception:
                logger.exception(
                    "queue.task.failed",
                    extra={
                        "task_name": task.task_name,
                        "job_id": task.payload.get("job_id"),
                        "request_id": task.payload.get("request_id"),
                        "error_code": "INTERNAL_ERROR",
                    },
                )
            finally:
                self._queue.task_done()
