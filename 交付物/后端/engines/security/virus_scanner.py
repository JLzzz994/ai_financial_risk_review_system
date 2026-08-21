"""病毒扫描适配器契约。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class VirusScanStatus(StrEnum):
    """病毒扫描结果状态。"""

    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VirusScanResult:
    """扫描器返回的脱敏结果。"""

    status: VirusScanStatus
    message: str | None = None


class VirusScanner(Protocol):
    """病毒扫描器窄接口。"""

    def scan(self, content: bytes) -> VirusScanResult:
        """扫描内容，不返回附件原文。"""


class CleanVirusScanner:
    """开发/测试默认扫描器；生产环境替换为企业病毒扫描适配器。"""

    def scan(self, content: bytes) -> VirusScanResult:
        """执行最小 EICAR 签名检查，避免静默接受明显测试样本。"""
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
            return VirusScanResult(VirusScanStatus.INFECTED, "命中病毒测试签名")
        return VirusScanResult(VirusScanStatus.CLEAN)


__all__ = ["CleanVirusScanner", "VirusScanResult", "VirusScanStatus", "VirusScanner"]
