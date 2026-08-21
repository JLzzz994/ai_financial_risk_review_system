"""费用报销版本化附件持久化服务。"""

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AuthorizationError
from app.repositories.sql_attachment_repository import ParseResultRecord, SqlAttachmentRepository
from app.schemas.auth import Principal, RoleCode
from app.services.attachment_service import (
    AttachmentPermissionError,
    AttachmentRecord,
    AttachmentService,
    AttachmentStateError,
)
from engines.common.storage import FileStorage, StoredObject, build_object_key
from engines.security.file_validator import FileValidationError, validate_file
from engines.security.virus_scanner import CleanVirusScanner, VirusScanner, VirusScanStatus


class PersistentAttachmentService:
    """异步编排 FileStorage、病毒扫描和 PostgreSQL 附件元数据。"""

    max_file_size = AttachmentService.max_file_size
    max_version_size = AttachmentService.max_version_size
    editable_document_statuses = AttachmentService.editable_document_statuses

    def __init__(
        self,
        storage: FileStorage,
        repository: SqlAttachmentRepository | Any | None = None,
        scanner: VirusScanner | None = None,
    ) -> None:
        """注入对象存储、SQL 仓储和病毒扫描适配器。"""
        self.storage = storage
        self.repository = repository or SqlAttachmentRepository()
        self.scanner = scanner or CleanVirusScanner()

    async def upload_attachment(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        document_version_id: UUID,
        file_name: str,
        content: bytes,
        content_type: str,
        actor_id: UUID,
        document_status: str,
        required_kind: str | None = None,
    ) -> AttachmentRecord:
        """校验并保存绑定不可变版本的附件，重复哈希直接返回已有记录。"""
        if document_status not in self.editable_document_statuses:
            raise AttachmentStateError("当前单据版本不允许新增附件")
        validate_file(file_name, content, content_type, max_size=self.max_file_size)
        file_hash = sha256(content).hexdigest()
        duplicate = await self.repository.find_by_hash(session, document_version_id, file_hash)
        if duplicate is not None:
            return duplicate
        current = await self.repository.list_by_version(session, document_version_id)
        if sum(item.file_size for item in current) + len(content) > self.max_version_size:
            raise FileValidationError("单据版本附件总量不能超过 200MB")
        scan_result = await asyncio.to_thread(self.scanner.scan, content)
        if scan_result.status is not VirusScanStatus.CLEAN:
            raise FileValidationError(scan_result.message or "病毒扫描未通过")

        attachment_id = uuid4()
        object_key = build_object_key(document_id, document_version_id, attachment_id, file_name)
        try:
            stored: StoredObject = await asyncio.to_thread(
                self.storage.put, object_key, content, content_type
            )
        except Exception as exc:
            raise FileValidationError("附件对象保存失败") from exc
        record = AttachmentRecord(
            attachment_id=attachment_id,
            document_id=document_id,
            document_version_id=document_version_id,
            file_name=Path(file_name).name,
            file_size=stored.size,
            mime_type=stored.content_type,
            object_key=stored.object_key,
            file_hash=file_hash,
            uploaded_by=actor_id,
            required_kind=required_kind,
        )
        try:
            async with session.begin():
                await self.repository.save(session, record)
        except Exception:
            await asyncio.to_thread(self.storage.delete, object_key)
            raise
        return record

    async def list_attachments(
        self, session: AsyncSession, document_id: UUID
    ) -> list[AttachmentRecord]:
        """查询单据下的未删除附件。"""
        return await self.repository.list_by_document(session, document_id)

    async def get_attachment(
        self, session: AsyncSession, attachment_id: UUID, actor: Principal | None = None
    ) -> AttachmentRecord:
        """查询附件并执行申请人、审批人和财务角色的基础数据范围检查。"""
        record = await self.repository.get(session, attachment_id)
        if record is None or record.storage_status == "deleted":
            raise KeyError("附件不存在")
        if actor is not None:
            owner_id = await self.repository.get_document_applicant(session, record.document_id)
            if owner_id != actor.user_id and not actor.roles.intersection(
                {RoleCode.APPROVER, RoleCode.FINANCE}
            ):
                raise AttachmentPermissionError("无权访问该附件")
        return record

    async def create_download_url(
        self,
        session: AsyncSession,
        attachment_id: UUID,
        actor: Principal,
        expires_seconds: int = 300,
    ) -> str:
        """权限校验后生成最长五分钟的短期下载地址。"""
        record = await self.get_attachment(session, attachment_id, actor)
        return await asyncio.to_thread(
            self.storage.create_presigned_url, record.object_key, expires_seconds
        )

    async def delete_attachment(
        self,
        session: AsyncSession,
        attachment_id: UUID,
        actor: Principal,
        document_status: str,
    ) -> AttachmentRecord:
        """软删除附件元数据后删除对象；已提交版本禁止删除。"""
        record = await self.get_attachment(session, attachment_id, actor)
        if document_status not in self.editable_document_statuses:
            raise AttachmentStateError("已提交版本附件不可删除")
        owner_id = await self.repository.get_document_applicant(session, record.document_id)
        if owner_id != actor.user_id:
            raise AuthorizationError("只有申请人可以删除附件")
        record.storage_status = "deleted"
        async with session.begin():
            await self.repository.save(session, record)
        try:
            await asyncio.to_thread(self.storage.delete, record.object_key)
        except Exception as exc:
            record.storage_status = "failed"
            async with session.begin():
                await self.repository.save(session, record)
            raise FileValidationError("对象删除失败，可稍后重试") from exc
        return record

    async def mark_parse_running(
        self, session: AsyncSession, attachment_id: UUID
    ) -> AttachmentRecord:
        """将解析状态推进到 parsing。"""
        record = await self.get_attachment(session, attachment_id)
        if record.storage_status != "stored":
            raise AttachmentStateError("对象未处于 stored 状态，不能解析")
        record.parse_status = "parsing"
        async with session.begin():
            return await self.repository.save(session, record)

    async def mark_parse_failed(
        self, session: AsyncSession, attachment_id: UUID, error_message: str
    ) -> AttachmentRecord:
        """保存脱敏解析失败状态，供重试和人工接管使用。"""
        record = await self.get_attachment(session, attachment_id)
        record.parse_status = "failed"
        record.parse_error = error_message[:500]
        async with session.begin():
            return await self.repository.save(session, record)

    async def mark_parse_succeeded(
        self, session: AsyncSession, attachment_id: UUID
    ) -> AttachmentRecord:
        """保存解析成功状态，结果实体另行追加。"""
        record = await self.get_attachment(session, attachment_id)
        record.parse_status = "succeeded"
        record.parse_error = None
        async with session.begin():
            return await self.repository.save(session, record)

    async def append_parse_result(
        self,
        session: AsyncSession,
        *,
        attachment_id: UUID,
        document_version_id: UUID,
        document_category: str,
        full_text: str,
        fields: dict[str, Any],
        evidence_positions: dict[str, Any],
        confidence: float | None,
        provider_name: str,
        provider_version: str,
    ) -> ParseResultRecord:
        """追加不可变解析结果，证据结构保留页码/坐标/片段/置信度。"""
        result = ParseResultRecord(
            result_id=uuid4(),
            attachment_id=attachment_id,
            document_version_id=document_version_id,
            document_category=document_category,
            full_text=full_text,
            fields=fields,
            evidence_positions=evidence_positions,
            confidence=confidence,
            provider_name=provider_name,
            provider_version=provider_version,
            created_at=datetime.now(UTC),
        )
        async with session.begin():
            await self.repository.append_parse_result(session, result)
        return result


__all__ = ["PersistentAttachmentService"]
