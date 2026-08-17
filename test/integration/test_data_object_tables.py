"""数据对象表清单契约测试。"""

from app.models import Base, EXTENDED_TABLE_NAMES


def test_extended_table_names_match_document_inventory() -> None:
    """扩展表至少覆盖数据对象文档中的 18 张非核心表。"""
    assert len(EXTENDED_TABLE_NAMES) == 21
    assert set(EXTENDED_TABLE_NAMES).issubset(Base.metadata.tables)
