"""UnitOfWork 事务边界测试。"""

import asyncio

import pytest

from app.db.uow import UnitOfWork


class FakeSession:
    """记录事务调用的最小异步会话替身。"""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self) -> None:
        """记录提交动作。"""
        self.committed = True

    async def rollback(self) -> None:
        """记录回滚动作。"""
        self.rolled_back = True

    async def close(self) -> None:
        """记录关闭动作。"""
        self.closed = True


def test_uow_commits_and_closes_session() -> None:
    """业务用例正常退出时提交并关闭独立会话。"""
    session = FakeSession()

    async def scenario() -> None:
        async with UnitOfWork(lambda: session) as unit_of_work:
            assert unit_of_work.session is session
            await unit_of_work.commit()

    asyncio.run(scenario())
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_uow_rolls_back_on_exception() -> None:
    """业务用例抛出异常时回滚并关闭会话，然后保留原异常。"""
    session = FakeSession()

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="业务失败"):
            async with UnitOfWork(lambda: session):
                raise RuntimeError("业务失败")

    asyncio.run(scenario())
    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True
