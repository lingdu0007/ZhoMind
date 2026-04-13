class TaskExecutor:
    async def execute(self, task_name: str, payload: dict) -> None:
        raise NotImplementedError("Task executor is not implemented")


class QueueRunner:
    def __init__(self, backend: str, executor: TaskExecutor) -> None:
        self.backend = backend
        self.executor = executor

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None
