import type { ReviewReport } from '@/types/domain'
import { apiDownload, apiFetch } from './client'

/** 权威报告接口：按 document_version_id 读取（SPEC 15） */
export function getReviewReport(documentVersionId: string): Promise<ReviewReport> {
  return apiFetch<ReviewReport>(`/review-reports/${documentVersionId}`)
}

export interface ReportVersionRow {
  document_version_id: string
  version_no: number
  report_status: string
  overall_risk_level?: string
  generated_at?: string
}

export function listReportVersions(documentId: string): Promise<ReportVersionRow[]> {
  return apiFetch<ReportVersionRow[]>(`/documents/${documentId}/review-reports`)
}

export interface ExportTask {
  export_task_id: string
  status: 'pending' | 'running' | 'succeeded' | 'failed'
  file_name?: string
  error_message?: string
}

export function exportReviewReport(
  documentVersionId: string,
  format: 'pdf' | 'xlsx',
): Promise<ExportTask> {
  return apiFetch<ExportTask>(`/review-reports/${documentVersionId}/export`, {
    method: 'POST',
    body: { format },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function getExportTask(exportTaskId: string): Promise<ExportTask> {
  return apiFetch<ExportTask>(`/review-reports/exports/${exportTaskId}`)
}

export function downloadExport(exportTaskId: string, fileName: string): Promise<void> {
  return apiDownload(`/review-reports/exports/${exportTaskId}/download`, fileName)
}
