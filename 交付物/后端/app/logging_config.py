"""安全的应用日志配置。"""

import logging
from pathlib import Path
from typing import Literal

from app.config import settings

_SENSITIVE_WORDS = (
    "password",
    "token",
    "secret",
    "authorization",
    "身份证",
    "银行卡",
    "附件",
    "原文",
)


def configure_logging() -> None:
    """配置控制台和 var/logs/app.log 文件日志，并确保目录存在。"""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    if not root.handlers:
        stream = logging.StreamHandler()
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        stream.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        root.addHandler(stream)
        root.addHandler(file_handler)


def get_logger(module: str) -> logging.Logger:
    """按模块名称获取日志记录器。"""
    return logging.getLogger(module)


def log_boundary(
    logger: logging.Logger,
    function: str,
    phase: Literal["enter", "exit"],
    **context: str,
) -> None:
    """记录函数边界和脱敏上下文，过滤可能包含敏感数据的键和值。"""
    safe_context = {
        key: value
        for key, value in context.items()
        if not any(word in key.lower() for word in _SENSITIVE_WORDS)
        and not any(word in value.lower() for word in _SENSITIVE_WORDS)
    }
    logger.info("boundary phase=%s function=%s context=%s", phase, function, safe_context)
