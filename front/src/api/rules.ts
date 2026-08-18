import type { MarketPriceItem, Paginated, RuleItem, SupplierRuleItem } from '@/types/domain'
import { apiFetch } from './client'

export interface RuleQuery {
  page?: number
  page_size?: number
  rule_type?: string
  status?: string
  keyword?: string
}

export function listRules(query: RuleQuery = {}): Promise<Paginated<RuleItem>> {
  return apiFetch<Paginated<RuleItem>>('/rules', { query })
}

export function patchRule(
  ruleId: string,
  payload: Partial<Pick<RuleItem, 'params' | 'status'>>,
): Promise<RuleItem> {
  return apiFetch<RuleItem>(`/rules/${ruleId}`, {
    method: 'PATCH',
    body: payload,
    idempotencyKey: crypto.randomUUID(),
  })
}

export function publishRule(ruleId: string, reason: string): Promise<RuleItem> {
  return apiFetch<RuleItem>(`/rules/${ruleId}/publish`, {
    method: 'POST',
    body: { reason },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function listMarketPrices(keyword?: string): Promise<MarketPriceItem[]> {
  return apiFetch<MarketPriceItem[]>('/market-price-references', { query: { keyword } })
}

export function patchMarketPrice(id: string, referencePrice: string): Promise<MarketPriceItem> {
  return apiFetch<MarketPriceItem>(`/market-price-references/${id}`, {
    method: 'PATCH',
    body: { reference_price: referencePrice },
  })
}

export function listSupplierRules(keyword?: string): Promise<SupplierRuleItem[]> {
  return apiFetch<SupplierRuleItem[]>('/supplier-risk-rules', { query: { keyword } })
}

export function patchSupplierRule(id: string, enabled: boolean, threshold?: string): Promise<SupplierRuleItem> {
  return apiFetch<SupplierRuleItem>(`/supplier-risk-rules/${id}`, {
    method: 'PATCH',
    body: { enabled, threshold },
    idempotencyKey: crypto.randomUUID(),
  })
}

export interface SystemParameter {
  key: string
  value: string
  description: string
  updated_at: string
}

export function listSystemParameters(): Promise<SystemParameter[]> {
  return apiFetch<SystemParameter[]>('/system-parameters')
}

export function patchSystemParameter(key: string, value: string): Promise<SystemParameter> {
  return apiFetch<SystemParameter>(`/system-parameters/${key}`, {
    method: 'PATCH',
    body: { value },
    idempotencyKey: crypto.randomUUID(),
  })
}
