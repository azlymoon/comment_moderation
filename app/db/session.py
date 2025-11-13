from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


class DB:
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    current_database_url: str = settings.database_url


def init_engine(database_url: str | None = None) -> AsyncEngine:
    target_url = database_url or DB.current_database_url
    if DB.engine is None or target_url != DB.current_database_url:
        DB.current_database_url = target_url
        DB.engine = create_async_engine(DB.current_database_url, echo=False, future=True)
        DB.session_factory = async_sessionmaker(
            bind=DB.engine,
            expire_on_commit=False,
            class_=AsyncSession,
            autoflush=False,
        )
    assert DB.engine is not None
    return DB.engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if DB.session_factory is None:
        init_engine()
    assert DB.session_factory is not None
    async with DB.session_factory() as session:
        yield session


async def run_migrations() -> None:
    database_engine = init_engine()
    try:
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except OperationalError as exc:
        if not settings.allow_sqlite_fallback:
            logger.error(
                "Не удалось подключиться к базе данных %s: %s",
                current_database_url,
                exc,
            )
            raise
        logger.warning(
            "Основная БД недоступна (%s). Переключаемся на SQLite: %s",
            exc,
            settings.sqlite_fallback_url,
        )
        fallback_engine = init_engine(settings.sqlite_fallback_url)
        async with fallback_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
