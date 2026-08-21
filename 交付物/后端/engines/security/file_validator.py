"""附件文件名、MIME、大小和文件头校验。"""

from pathlib import Path


class FileValidationError(ValueError):
    """文件不符合附件安全策略。"""


MAX_ATTACHMENT_SIZE = 20 * 1024 * 1024

_MIME_BY_EXTENSION = {
    ".pdf": frozenset({"application/pdf"}),
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".xlsx": frozenset({
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    }),
    ".xls": frozenset({"application/vnd.ms-excel", "application/octet-stream"}),
    ".docx": frozenset({
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    }),
}


def _has_expected_header(extension: str, content: bytes) -> bool:
    """检查常见格式的魔数，避免只依赖客户端提供的扩展名和 MIME。"""
    if extension == ".pdf":
        return content.startswith(b"%PDF-")
    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension in {".xlsx", ".docx"}:
        return content.startswith(b"PK\x03\x04")
    if extension == ".xls":
        return content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    return False


def validate_file(
    file_name: str,
    content: bytes,
    content_type: str,
    *,
    max_size: int = MAX_ATTACHMENT_SIZE,
) -> str:
    """校验附件并返回规范化扩展名。"""
    if not file_name.strip() or "\x00" in file_name:
        raise FileValidationError("附件文件名无效")
    if Path(file_name).name != file_name or ".." in Path(file_name).parts:
        raise FileValidationError("附件文件名不能包含路径")
    extension = Path(file_name).suffix.lower()
    if extension not in _MIME_BY_EXTENSION:
        raise FileValidationError("附件扩展名不在白名单中")
    if not content:
        raise FileValidationError("附件内容不能为空")
    if len(content) > max_size:
        raise FileValidationError(f"单个附件不能超过 {max_size // (1024 * 1024)}MB")
    normalized_mime = content_type.split(";", 1)[0].strip().lower()
    if normalized_mime not in _MIME_BY_EXTENSION[extension]:
        raise FileValidationError("附件 MIME 类型与扩展名不匹配")
    if not _has_expected_header(extension, content):
        raise FileValidationError("附件文件头与声明格式不匹配")
    return extension


__all__ = ["FileValidationError", "MAX_ATTACHMENT_SIZE", "validate_file"]
