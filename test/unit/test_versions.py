"""单据版本规则测试。"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.repositories.document_repository import InMemoryDocumentRepository
from app.schemas.documents import CreateDocumentCommand
from app.services.document_service import DocumentService


def test_submit_creates_immutable_incremented_version() -> None:
    """提交生成版本 1，并提升乐观锁版本。"""
    repo = InMemoryDocumentRepository()
    service = DocumentService(repo)
    actor = uuid4()
    document = service.create_draft(CreateDocumentCommand(applicant_id=actor, applicant_department="财务", total_amount=Decimal("10.00"), apply_date=date.today(), reason_text="差旅"))
    version = service.submit(document.document_id, actor, expected_state_version=1)
    assert version.version_no == 1
    assert repo.documents[document.document_id].status == "pending_review"


def test_submit_rejects_stale_state_version() -> None:
    """过期 state_version 必须拒绝提交。"""
    service = DocumentService()
    actor = uuid4()
    document = service.create_draft(CreateDocumentCommand(applicant_id=actor, applicant_department="财务", total_amount=Decimal("10.00"), apply_date=date.today(), reason_text="差旅"))
    with pytest.raises(ValueError, match="修改"):
        service.submit(document.document_id, actor, expected_state_version=0)
