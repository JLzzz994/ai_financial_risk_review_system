"""Celery 配置静态约束测试。"""

from pathlib import Path


def test_compose_defines_worker_and_minio() -> None:
    """Compose 必须包含异步 worker 和生产对象存储。"""
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "worker:" in compose
    assert "minio:" in compose
    assert "financial_review" in compose
