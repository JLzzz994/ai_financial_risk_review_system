"""应用依赖就绪检查。"""

import logging
from asyncio import gather
from typing import Literal

from pydantic import BaseModel
from redis.asyncio import Redis, from_url
from sqlalchemy import text

from app.config import settings
from app.db.engine import engine

logger = logging.getLogger(__name__)


DependencyStatus = Literal["ok", "unavailable"]


class ReadinessDependencies(BaseModel):
    """就绪检查涉及的基础依赖状态。"""

    database: DependencyStatus
    redis: DependencyStatus


class ReadinessResult(BaseModel):
    """应用就绪检查结果。"""

    status: Literal["ready", "not_ready"]
    dependencies: ReadinessDependencies


async def check_database() -> bool:
    """执行一次最小 PostgreSQL 查询，确认连接和事务协议可用。"""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("readiness dependency=database status=unavailable")
        return False


async def check_redis() -> bool:
    """执行 Redis PING，并在检查结束后释放短连接。"""
    client: Redis = from_url(  # type: ignore[no-untyped-call]
        settings.redis_url, socket_connect_timeout=2, socket_timeout=2
    )
    try:
        return bool(await client.ping())
    except Exception:
        logger.exception("readiness dependency=redis status=unavailable")
        return False
    finally:
        await client.aclose()


async def get_readiness() -> ReadinessResult:
    """并行检查 PostgreSQL 和 Redis，避免就绪探针串行阻塞。"""
    database_ok, redis_ok = await gather(check_database(), check_redis())
    dependencies = ReadinessDependencies(
        database="ok" if database_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
    status: Literal["ready", "not_ready"] = (
        "ready" if database_ok and redis_ok else "not_ready"
    )
    return ReadinessResult(status=status, dependencies=dependencies)
