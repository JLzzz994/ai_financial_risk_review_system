"""金额核对、供应商风险和规则中心接口。"""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_session
from app.dependencies.auth import get_current_principal
from app.errors import AppError
from app.repositories.sql_support_repository import SqlSupportRepository
from app.schemas.auth import PermissionCode, Principal
from app.schemas.support import (
    AmountComparisonResponse,
    MarketPricePatch,
    MarketPriceResponse,
    RuleItemResponse,
    RulePage,
    RulePatch,
    RulePublishRequest,
    SupplierRiskResponse,
    SupplierRulePatch,
    SupplierRuleResponse,
    SystemParameterPatch,
    SystemParameterResponse,
)
from app.services.permission_service import authorize

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

_SUPPLIER_RULES = [
    SupplierRuleResponse(
        id="sr-1",
        supplier_code="SUP-01023",
        supplier_name="华扬广告传媒有限公司",
        rule_name="单笔付款上限",
        threshold=Decimal("50000.00"),
        enabled=True,
    ),
    SupplierRuleResponse(
        id="sr-2",
        supplier_code="SUP-01023",
        supplier_name="华扬广告传媒有限公司",
        rule_name="月累计付款上限",
        threshold=Decimal("200000.00"),
        enabled=True,
    ),
]

_SYSTEM_PARAMETERS = {
    "analysis.retry_max": "3",
    "analysis.retry_backoff_seconds": "30",
    "ocr.timeout_seconds": "120",
    "llm.timeout_seconds": "60",
    "export.max_rows": "10000",
    "rag_rule_version": settings.rag_rule_version,
}
_SYSTEM_PARAMETER_DESCRIPTIONS = {
    "analysis.retry_max": "分析任务自动重试上限，超过后转人工接管",
    "analysis.retry_backoff_seconds": "重试指数退避基数（秒）",
    "ocr.timeout_seconds": "OCR 适配器超时",
    "llm.timeout_seconds": "LLM 适配器超时",
    "export.max_rows": "审计/报告导出最大行数",
    "rag_rule_version": "当前风险规则版本",
}
_CONFIG_IDEMPOTENCY: dict[
    tuple[str, str], RuleItemResponse | SupplierRuleResponse | SystemParameterResponse
] = {}
_CONFIG_IDEMPOTENCY_FINGERPRINTS: dict[tuple[str, str], str] = {}


async def _authorize_config(authorization: str | None) -> Principal:
    """认证并校验配置管理权限。"""
    principal = await get_current_principal(authorization)
    authorize(principal, PermissionCode.CONFIG_MANAGE, is_configuration_resource=True)
    return principal


async def _authorize_config_read(authorization: str | None) -> Principal:
    """认证并校验配置读取权限。"""
    principal = await get_current_principal(authorization)
    authorize(principal, PermissionCode.CONFIG_READ, is_configuration_resource=True)
    return principal


def _require_idempotency(key: str | None) -> str:
    """校验配置写操作的幂等键。"""
    if not key or not key.strip():
        raise AppError("missing_idempotency_key", "配置变更必须提供 Idempotency-Key", 400)
    return key.strip()


def _cached_config_response(
    cache_key: tuple[str, str], fingerprint: str
) -> RuleItemResponse | SupplierRuleResponse | SystemParameterResponse | None:
    """返回不可变幂等快照，并拒绝同键不同请求体。"""
    cached = _CONFIG_IDEMPOTENCY.get(cache_key)
    if cached is None:
        return None
    if _CONFIG_IDEMPOTENCY_FINGERPRINTS[cache_key] != fingerprint:
        raise AppError("conflict", "Idempotency-Key 已用于其他请求", 409)
    return deepcopy(cached)


def _store_config_response(
    cache_key: tuple[str, str], fingerprint: str,
    response: RuleItemResponse | SupplierRuleResponse | SystemParameterResponse,
) -> None:
    """保存配置写结果的深拷贝快照。"""
    _CONFIG_IDEMPOTENCY_FINGERPRINTS[cache_key] = fingerprint
    _CONFIG_IDEMPOTENCY[cache_key] = deepcopy(response)


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
    await _authorize_config_read(authorization)
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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RuleItemResponse:
    """更新内置规则的启用状态或参数。"""
    await _authorize_config(authorization)
    key = _require_idempotency(idempotency_key)
    cache_key = (f"rule.patch:{rule_id}", key)
    fingerprint = payload.model_dump_json()
    cached = _cached_config_response(cache_key, fingerprint)
    if isinstance(cached, RuleItemResponse):
        return cached
    rule = next((item for item in _RULES if item.rule_id == rule_id), None)
    if rule is None:
        raise AppError("not_found", "规则不存在", 404)
    if payload.status is None and payload.params is None:
        raise AppError("conflict", "没有需要更新的字段", 409)
    if payload.status is not None:
        rule.status = payload.status
    if payload.params is not None:
        rule.params = payload.params
    rule.updated_at = datetime.now(UTC)
    _store_config_response(cache_key, fingerprint, rule)
    return deepcopy(rule)


@router.post("/rules/{rule_id}/publish", response_model=RuleItemResponse)
async def publish_rule(
    rule_id: str,
    payload: RulePublishRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RuleItemResponse:
    """由人工配置接口发布规则，审批和 Agent 不得调用该状态变更。"""
    await _authorize_config(authorization)
    key = _require_idempotency(idempotency_key)
    cache_key = (f"rule.publish:{rule_id}", key)
    fingerprint = payload.model_dump_json()
    cached = _cached_config_response(cache_key, fingerprint)
    if isinstance(cached, RuleItemResponse):
        return cached
    rule = next((item for item in _RULES if item.rule_id == rule_id), None)
    if rule is None:
        raise AppError("not_found", "规则不存在", 404)
    rule.status = "published"
    try:
        version = float(rule.rule_version.removeprefix("v")) + 0.1
        rule.rule_version = f"v{version:.1f}"
    except ValueError as exc:
        raise AppError("conflict", "规则版本格式不正确", 409) from exc
    rule.updated_at = datetime.now(UTC)
    _store_config_response(cache_key, fingerprint, rule)
    return deepcopy(rule)


@router.get("/supplier-risk-rules", response_model=list[SupplierRuleResponse])
async def list_supplier_rules(
    keyword: str | None = None,
    authorization: str | None = Header(default=None),
) -> list[SupplierRuleResponse]:
    """查询供应商规则目录。"""
    await _authorize_config_read(authorization)
    if not keyword:
        return _SUPPLIER_RULES
    normalized = keyword.strip().lower()
    return [
        item
        for item in _SUPPLIER_RULES
        if normalized in item.supplier_code.lower()
        or normalized in item.supplier_name.lower()
        or normalized in item.rule_name.lower()
    ]


@router.patch("/supplier-risk-rules/{rule_id}", response_model=SupplierRuleResponse)
async def update_supplier_rule(
    rule_id: str,
    payload: SupplierRulePatch,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SupplierRuleResponse:
    """更新供应商规则启用状态和阈值。"""
    await _authorize_config(authorization)
    key = _require_idempotency(idempotency_key)
    cache_key = (f"supplier-rule.patch:{rule_id}", key)
    fingerprint = payload.model_dump_json()
    cached = _cached_config_response(cache_key, fingerprint)
    if isinstance(cached, SupplierRuleResponse):
        return cached
    item = next((rule for rule in _SUPPLIER_RULES if rule.id == rule_id), None)
    if item is None:
        raise AppError("not_found", "供应商规则不存在", 404)
    if payload.enabled is None and payload.threshold is None:
        raise AppError("conflict", "没有需要更新的字段", 409)
    if payload.enabled is not None:
        item.enabled = payload.enabled
    if payload.threshold is not None:
        item.threshold = payload.threshold
    _store_config_response(cache_key, fingerprint, item)
    return deepcopy(item)


@router.get("/system-parameters", response_model=list[SystemParameterResponse])
async def list_system_parameters(
    authorization: str | None = Header(default=None),
) -> list[SystemParameterResponse]:
    """查询系统参数目录。"""
    await _authorize_config_read(authorization)
    now = datetime.now(UTC)
    return [
        SystemParameterResponse(
            key=key,
            value=value,
            description=_SYSTEM_PARAMETER_DESCRIPTIONS[key],
            updated_at=now,
        )
        for key, value in _SYSTEM_PARAMETERS.items()
    ]


@router.patch("/system-parameters/{key}", response_model=SystemParameterResponse)
async def update_system_parameter(
    key: str,
    payload: SystemParameterPatch,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> SystemParameterResponse:
    """更新已登记的系统参数；未知参数明确返回 404。"""
    await _authorize_config(authorization)
    key_value = _require_idempotency(idempotency_key)
    cache_key = (f"system-parameter.patch:{key}", key_value)
    fingerprint = payload.model_dump_json()
    cached = _cached_config_response(cache_key, fingerprint)
    if isinstance(cached, SystemParameterResponse):
        return cached
    if key not in _SYSTEM_PARAMETERS:
        raise AppError("not_found", "系统参数不存在", 404)
    _SYSTEM_PARAMETERS[key] = payload.value
    if key == "rag_rule_version":
        settings.rag_rule_version = payload.value
    response = SystemParameterResponse(
        key=key,
        value=payload.value,
        description=_SYSTEM_PARAMETER_DESCRIPTIONS[key],
        updated_at=datetime.now(UTC),
    )
    _store_config_response(cache_key, fingerprint, response)
    return deepcopy(response)
