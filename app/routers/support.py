"""金额核对、供应商风险和规则中心接口。"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.repositories.sql_support_repository import SqlSupportRepository
from app.schemas.support import (
    AmountComparisonResponse,
    MarketPricePatch,
    MarketPriceResponse,
    RuleItemResponse,
    RulePage,
    RulePatch,
    SupplierRiskResponse,
    SupplierRuleResponse,
    SystemParameterResponse,
)

router = APIRouter(prefix="/api/v1", tags=["support"])
repository = SqlSupportRepository()

_RULES = [
    RuleItemResponse(
        rule_id=code,
        rule_code=code,
        rule_name=name,
        rule_type=rule_type,
        rule_version="v1.0",
        updated_at=datetime.now(UTC),
    )
    for code, name, rule_type in [
        ("amount.threshold", "金额阈值", "amount"),
        ("invoice.duplicate", "发票重复", "duplicate"),
        ("invoice.amount_mismatch", "发票金额不一致", "amount"),
        ("contract.amount_mismatch", "合同金额不一致", "amount"),
        ("payment.batch_anomaly", "批量付款异常", "behavior"),
        ("supplier.screening", "供应商筛查", "supplier"),
        ("supplier.blacklist", "供应商黑名单", "supplier"),
        ("expense.completeness", "附件完整性", "completeness"),
        ("expense.behavior", "报销行为异常", "behavior"),
        ("market.price_outlier", "市场价偏离", "amount"),
    ]
]


@router.get("/documents/{document_id}/amount-comparison", response_model=AmountComparisonResponse)
async def amount_comparison(
    document_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AmountComparisonResponse:
    """查询单据、明细和外部金额的核对结果。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="金额核对数据不存在")
    await get_current_principal(authorization, session)
    try:
        return await repository.amount_comparison(session, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/suppliers/{supplier_code}/risks", response_model=SupplierRiskResponse)
async def supplier_risk_by_code(
    supplier_code: str,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> SupplierRiskResponse:
    """按供应商编码查询风险摘要。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="供应商不存在")
    await get_current_principal(authorization, session)
    try:
        return await repository.supplier_by_code(session, supplier_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/supplier-risks/{supplier_id}", response_model=SupplierRiskResponse)
async def supplier_risk_by_id(
    supplier_id: UUID,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> SupplierRiskResponse:
    """按供应商 ID 查询风险摘要。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=404, detail="供应商不存在")
    await get_current_principal(authorization, session)
    try:
        return await repository.supplier_by_id(session, supplier_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/market-price-references", response_model=list[MarketPriceResponse])
async def list_market_prices(
    keyword: str | None = None,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[MarketPriceResponse]:
    """查询市场价格参考。"""
    if settings.document_backend != "postgres":
        return []
    await get_current_principal(authorization, session)
    return await repository.list_market_prices(session, keyword)


@router.patch("/market-price-references/{price_id}", response_model=MarketPriceResponse)
async def update_market_price(
    price_id: UUID,
    patch: MarketPricePatch,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> MarketPriceResponse:
    """更新市场价格参考。"""
    if settings.document_backend != "postgres":
        raise HTTPException(status_code=503, detail="市场价持久化未启用")
    await get_current_principal(authorization, session)
    try:
        async with session.begin():
            return await repository.update_market_price(session, price_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/rules", response_model=RulePage)
async def list_rules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    keyword: str | None = None,
    rule_type: str | None = None,
    authorization: str | None = Header(default=None),
) -> RulePage:
    """查询十类确定性风险规则目录。"""
    await get_current_principal(authorization)
    items = [
        rule
        for rule in _RULES
        if (not keyword or keyword in rule.rule_code or keyword in rule.rule_name)
        and (not rule_type or rule.rule_type == rule_type)
    ]
    start = (page - 1) * page_size
    return RulePage(
        items=items[start : start + page_size],
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.patch("/rules/{rule_id}", response_model=RuleItemResponse)
async def update_rule(
    rule_id: str,
    payload: RulePatch,
    authorization: str | None = Header(default=None),
) -> RuleItemResponse:
    """更新内置规则的启用状态或参数。"""
    await get_current_principal(authorization)
    rule = next((item for item in _RULES if item.rule_id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    if payload.status is not None:
        rule.status = payload.status
    if payload.params is not None:
        rule.params = payload.params
    rule.updated_at = datetime.now(UTC)
    return rule


@router.get("/supplier-risk-rules", response_model=list[SupplierRuleResponse])
async def list_supplier_rules(
    authorization: str | None = Header(default=None),
) -> list[SupplierRuleResponse]:
    """查询供应商规则目录。"""
    await get_current_principal(authorization)
    return []


@router.get("/system-parameters", response_model=list[SystemParameterResponse])
async def list_system_parameters(
    authorization: str | None = Header(default=None),
) -> list[SystemParameterResponse]:
    """查询系统参数目录。"""
    await get_current_principal(authorization)
    return [SystemParameterResponse(key="rag_rule_version", value=settings.rag_rule_version)]
