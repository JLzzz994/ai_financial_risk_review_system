"""业务用例使用的异步 Unit of Work。"""

from types import TracebackType
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory


class SessionFactory(Protocol):
    """创建独立异步会话的最小契约，便于单元测试替换。"""

    def __call__(self) -> AsyncSession:
        """创建一个尚未提交的会话。"""


class UnitOfWork:
    """协调一个业务用例中的会话、提交、回滚和关闭。"""

    def __init__(self, session_factory: SessionFactory = async_session_factory) -> None:
        """注入会话工厂；默认使用应用级异步会话工厂。"""
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        """进入事务边界并创建本次用例专属会话。"""
        self.session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """异常退出时回滚，任何退出路径都关闭会话。"""
        del exc_value, traceback
        if exc_type is not None:
            await self.rollback()
        await self.close()

    async def commit(self) -> None:
        """提交当前事务；未进入上下文时明确报错。"""
        await self._require_session().commit()

    async def rollback(self) -> None:
        """回滚当前事务；未进入上下文时明确报错。"""
        await self._require_session().rollback()

    async def close(self) -> None:
        """释放当前会话，避免跨请求复用数据库连接。"""
        if self.session is not None:
            await self.session.close()
            self.session = None

    def _require_session(self) -> AsyncSession:
        """返回当前会话或抛出事务边界错误。"""
        if self.session is None:
            raise RuntimeError("UnitOfWork 必须在异步上下文中使用")
        return self.session
