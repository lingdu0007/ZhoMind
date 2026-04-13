from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database is not connected")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database is not connected")
        return self._session_factory

    async def connect(self) -> None:
        if self._engine is not None:
            return

        self._engine = create_async_engine(self.url, future=True, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
        )
        async with self._engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

    async def disconnect(self) -> None:
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session


def create_database(url: str) -> Database:
    return Database(url)
