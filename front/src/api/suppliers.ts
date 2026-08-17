import type { AmountComparison, SupplierRisk } from '@/types/domain'
import { apiFetch } from './client'

export function getAmountComparison(documentId: string): Promise<AmountComparison> {
  return apiFetch<AmountComparison>(`/documents/${documentId}/amount-comparison`)
}

export function getSupplierRisk(supplierId: string): Promise<SupplierRisk> {
  return apiFetch<SupplierRisk>(`/supplier-risks/${supplierId}`)
}

export function getSupplierRiskByCode(supplierCode: string): Promise<SupplierRisk> {
  return apiFetch<SupplierRisk>(`/suppliers/${supplierCode}/risks`)
}
