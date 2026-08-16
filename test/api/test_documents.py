"""费用报销服务契约测试。"""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.schemas.documents import CreateDocumentCommand
from app.services.document_service import DocumentService


def test_only_cny_is_supported() -> None:
    """MVP 禁止隐式汇率换算。"""
    command = CreateDocumentCommand(applicant_id=uuid4(), applicant_department="财务", total_amount=Decimal("1.00"), currency="USD", apply_date="2026-08-17", reason_text="差旅")
    with pytest.raises(ValueError):
        DocumentService().create_draft(command)
