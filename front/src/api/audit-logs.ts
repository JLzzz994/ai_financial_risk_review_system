import type { AuditLog, Paginated } from '@/types/domain'
import { apiDownload, apiFetch } from './client'

export interface AuditLogQuery {
  page?: number
  page_size?: number
  action?: string
  actor?: string
  request_id?: string
  date_from?: string
  date_to?: string
}

export function listAuditLogs(query: AuditLogQuery = {}): Promise<Paginated<AuditLog>> {
  return apiFetch<Paginated<AuditLog>>('/audit-logs', { query })
}

export function exportAuditLogs(query: AuditLogQuery = {}): Promise<void> {
  return apiDownload(
    `/audit-logs${queryToString(query)}`,
    `审计日志导出_${new Date().toISOString().slice(0, 10)}`,
  )
}

function queryToString(query: AuditLogQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value) params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}
