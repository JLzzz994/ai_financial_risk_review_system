"""后台任务共用安全辅助函数。"""

import re


def sanitize_error(message: str, limit: int = 500) -> str:
    """移除身份证、银行卡和疑似长原文后再截断。"""
    cleaned = re.sub(r"\b\d{15,19}\b", "[敏感数字已脱敏]", message)
    cleaned = re.sub(
        r"(?i)(身份证|银行卡|附件原文|模型输入)\s*[:：]?[^，。;；\n]*",
        r"\1已脱敏",
        cleaned,
    )
    return cleaned[:limit]
