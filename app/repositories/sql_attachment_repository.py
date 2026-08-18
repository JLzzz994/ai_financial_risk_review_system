"""PostgreSQL 附件元数据与解析结果仓储。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import DocumentVersion, FinancialDocument
from app.models.extended import attachment_parse_results, document_attachments
from app.services.attachment_service import AttachmentRecord


@dataclass(frozen=True, slots=True)
class ParseResultRecord:
    """不可变解析结果，历史结果不做覆盖更新。"""

    result_id: UUID
    attachment_id: UUID
    document_version_id: UUID
    document_category: str
    full_text: str
    fields: dict[str, Any]
    evidence_positions: dict[str, Any]
    confidence: float | None
    provider_name: str
    provider_version: str
    created_at: datetime
    idempotency_key: str | None = None


class SqlAttachmentRepository:
    """将附件元数据和解析结果映射到数据对象文档规定的表。"""

    async def find_by_hash(
        self, session: AsyncSession, document_version_id: UUID, file_hash: str
    ) -> AttachmentRecord | None:
        """按版本和 SHA-256 查询未删除附件。"""
        result = await session.execute(
            select(document_attachments).where(
                document_attachments.c.document_version_id == document_version_id,
                document_attachments.c.file_hash == file_hash,
                document_attachments.c.storage_status != "deleted",
            )
        )
        row = result.mappings().first()
        return self._to_record(row) if row is not None else None

    async def get(self, session: AsyncSession, attachment_id: UUID) -> AttachmentRecord | None:
        """按附件 ID 查询未删除或历史状态记录。"""
        result = await session.execute(
            select(document_attachments).where(document_attachments.c.id == attachment_id)
        )
        row = result.mappings().first()
        return self._to_record(row) if row is not None else None

    async def list_by_document(
        self, session: AsyncSession, document_id: UUID
    ) -> list[AttachmentRecord]:
        """按单据查询未删除附件。"""
        result = await session.execute(
            select(document_attachments)
            .where(
                document_attachments.c.document_id == document_id,
                document_attachments.c.storage_status != "deleted",
            )
            .order_by(document_attachments.c.created_at)
        )
        return [self._to_record(row) for row in result.mappings().all()]

    async def list_by_version(
        self, session: AsyncSession, document_version_id: UUID
    ) -> list[AttachmentRecord]:
        """按不可变版本查询未删除附件。"""
        result = await session.execute(
            select(document_attachments)
            .where(
                document_attachments.c.document_version_id == document_version_id,
                document_attachments.c.storage_status != "deleted",
            )
            .order_by(document_attachments.c.created_at)
        )
        return [self._to_record(row) for row in result.mappings().all()]

    async def save(self, session: AsyncSession, record: AttachmentRecord) -> AttachmentRecord:
        """新增或更新附件状态；对象键只保存为内部 metadata。"""
        values = {
            "document_id": record.document_id,
            "document_version_id": record.document_version_id,
            "file_name": record.file_name,
            "file_type": record.file_name.rsplit(".", 1)[-1].lower()
            if "." in record.file_name
            else "other",
            "file_size": record.file_size,
            "file_path": record.object_key,
            "object_key": record.object_key,
            "file_hash": record.file_hash,
            "storage_status": record.storage_status,
            "parse_status": record.parse_status,
            "parse_retry_count": record.retry_count,
            "parse_error": record.parse_error,
            "parse_idempotency_key": record.parse_idempotency_key,
            "virus_scan_status": "clean",
            "virus_scan_version": "clean-scanner-v1",
            "virus_scanned_at": record.uploaded_at,
        }
        exists = await session.execute(
            select(document_attachments.c.id).where(
                document_attachments.c.id == record.attachment_id
            )
        )
        if exists.scalar_one_or_none() is None:
            values["id"] = record.attachment_id
            await session.execute(insert(document_attachments).values(**values))
        else:
            await session.execute(
                update(document_attachments)
                .where(document_attachments.c.id == record.attachment_id)
                .values(
                    storage_status=record.storage_status,
                    parse_status=record.parse_status,
                    parse_retry_count=record.retry_count,
                    parse_error=record.parse_error,
                    parse_idempotency_key=record.parse_idempotency_key,
                    file_path=record.object_key,
                    object_key=record.object_key,
                )
            )
        return record

    async def get_document_applicant(
        self, session: AsyncSession, document_id: UUID
    ) -> UUID | None:
        """读取单据申请人，用于附件数据范围检查。"""
        result = await session.execute(
            select(FinancialDocument.applicant_id).where(FinancialDocument.id == document_id)
        )
        value = result.scalar_one_or_none()
        return UUID(str(value)) if value is not None else None

    async def get_version_context(
        self, session: AsyncSession, document_id: UUID, document_version_id: UUID
    ) -> tuple[str, UUID] | None:
        """读取版本所属单据状态和申请人，避免路由自行拼接 SQL。"""
        result = await session.execute(
            select(FinancialDocument.document_status, FinancialDocument.applicant_id)
            .join(DocumentVersion, DocumentVersion.document_id == FinancialDocument.id)
            .where(
                FinancialDocument.id == document_id,
                DocumentVersion.id == document_version_id,
            )
        )
        row = result.first()
        if row is None:
            return None
        return str(row[0]), UUID(str(row[1]))

    async def append_parse_result(
        self, session: AsyncSession, result: ParseResultRecord
    ) -> ParseResultRecord:
        """追加一条解析结果，禁止覆盖历史结果。"""
        if result.idempotency_key:
            # 同一附件行加锁，避免 select 后 insert 的并发竞态。
            await session.execute(
                select(document_attachments.c.id)
                .where(document_attachments.c.id == result.attachment_id)
                .with_for_update()
            )
            existing = await session.execute(
                select(attachment_parse_results.c.id).where(
                    attachment_parse_results.c.attachment_id == result.attachment_id,
                    attachment_parse_results.c.document_version_id == result.document_version_id,
                    attachment_parse_results.c.parse_idempotency_key == result.idempotency_key,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return result
        await session.execute(
            insert(attachment_parse_results).values(
                id=result.result_id,
                attachment_id=result.attachment_id,
                document_version_id=result.document_version_id,
                document_category=result.document_category,
                full_text=result.full_text,
                fields_json=result.fields,
                evidence_positions_json=result.evidence_positions,
                confidence=result.confidence,
                provider_name=result.provider_name,
                provider_version=result.provider_version,
                parse_idempotency_key=result.idempotency_key,
            )
        )
        return result

    @staticmethod
    def _to_record(row: Any) -> AttachmentRecord:
        """将数据库行转换为不含物理路径的附件领域对象。"""
        object_key = str(row.get("object_key") or row["file_path"])
        created_at = row.get("created_at") or datetime.now(UTC)
        return AttachmentRecord(
            attachment_id=UUID(str(row["id"])),
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            file_name=str(row["file_name"]),
            file_size=int(row["file_size"]),
            mime_type=str(row["file_type"]),
            object_key=object_key,
            file_hash=str(row["file_hash"]),
            uploaded_by=UUID(int=0),
            uploaded_at=created_at,
            storage_status=str(row["storage_status"]),
            parse_status=str(row["parse_status"]),
            retry_count=int(row.get("parse_retry_count") or 0),
            parse_error=row.get("parse_error"),
            parse_idempotency_key=row.get("parse_idempotency_key"),
        )


__all__ = ["ParseResultRecord", "SqlAttachmentRepository"]
