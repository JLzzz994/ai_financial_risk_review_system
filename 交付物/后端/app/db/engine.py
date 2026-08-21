"""SQLAlchemy 异步引擎与会话工厂。"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)
"""全局引擎只负责连接池，业务用例通过会话工厂获取独立会话。"""

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """为 FastAPI 依赖或后台任务提供一个独立异步会话。"""
    async with async_session_factory() as session:
        yield session


async def dispose_engine() -> None:
    """应用关闭时释放连接池资源。"""
    await engine.dispose()
