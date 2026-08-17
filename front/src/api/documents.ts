import type {
  DocumentDetail,
  DocumentSummary,
  DocumentVersionInfo,
  LineItem,
  Paginated,
} from '@/types/domain'
import { apiFetch } from './client'

export interface DocumentListQuery {
  page?: number
  page_size?: number
  document_type?: string
  document_status?: string
  keyword?: string
  date_from?: string
  date_to?: string
}

export function listDocuments(query: DocumentListQuery = {}): Promise<Paginated<DocumentSummary>> {
  return apiFetch<Paginated<DocumentSummary>>('/documents', { query })
}

export function getDocument(documentId: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/documents/${documentId}`)
}

export interface DocumentPayload {
  document_type: string
  expense_category?: string
  applicant_department?: string
  budget_department?: string
  apply_date?: string
  total_amount?: string
  currency?: string
  payee_name?: string
  payee_account?: string
  payee_bank?: string
  reason_text?: string
  expected_updated_at?: string
}

export function createDocument(payload: DocumentPayload, idempotencyKey: string): Promise<DocumentSummary> {
  return apiFetch<DocumentSummary>('/documents', {
    method: 'POST',
    body: payload,
    idempotencyKey,
  })
}

export function updateDocument(
  documentId: string,
  payload: DocumentPayload,
  idempotencyKey: string,
): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/documents/${documentId}`, {
    method: 'PATCH',
    body: payload,
    idempotencyKey,
  })
}

export function copyDocument(documentId: string): Promise<DocumentSummary> {
  return apiFetch<DocumentSummary>(`/documents/${documentId}/copy`, { method: 'POST' })
}

export interface SubmissionResult {
  document_id: string
  document_version_id: string
  analysis_task_id: string
  status: string
}

export function submitDocument(
  documentId: string,
  reason: string,
  idempotencyKey: string,
): Promise<SubmissionResult> {
  return apiFetch<SubmissionResult>(`/documents/${documentId}/submit`, {
    method: 'POST',
    body: { reason },
    idempotencyKey,
  })
}

export function withdrawDocument(documentId: string, reason: string): Promise<void> {
  return apiFetch<void>(`/documents/${documentId}/withdraw`, {
    method: 'POST',
    body: { reason },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function voidDocument(documentId: string, reason: string): Promise<void> {
  return apiFetch<void>(`/documents/${documentId}/void`, {
    method: 'POST',
    body: { reason },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function listVersions(documentId: string): Promise<DocumentVersionInfo[]> {
  return apiFetch<DocumentVersionInfo[]>(`/documents/${documentId}/versions`)
}

export function getLineItems(documentId: string): Promise<LineItem[]> {
  return apiFetch<LineItem[]>(`/documents/${documentId}/line-items`)
}

export function createLineItem(documentId: string, item: Omit<LineItem, 'item_id'>): Promise<LineItem> {
  return apiFetch<LineItem>(`/documents/${documentId}/line-items`, { method: 'POST', body: item })
}

export function updateLineItem(documentId: string, itemId: string, item: Partial<LineItem>): Promise<LineItem> {
  return apiFetch<LineItem>(`/documents/${documentId}/line-items/${itemId}`, {
    method: 'PATCH',
    body: item,
  })
}

export function deleteLineItem(documentId: string, itemId: string): Promise<void> {
  return apiFetch<void>(`/documents/${documentId}/line-items/${itemId}`, { method: 'DELETE' })
}
