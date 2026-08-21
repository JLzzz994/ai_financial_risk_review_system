import type { Attachment } from '@/types/domain'
import { apiDownload, apiFetch, apiUpload } from './client'

export function listAttachments(documentId: string): Promise<Attachment[]> {
  return apiFetch<Attachment[]>(`/documents/${documentId}/attachments`)
}

export function uploadAttachment(
  documentId: string,
  file: File,
  requiredKind?: string,
): Promise<Attachment> {
  return apiUpload<Attachment>(`/documents/${documentId}/attachments`, file, requiredKind ? { required_kind: requiredKind } : undefined)
}

export function deleteAttachment(attachmentId: string): Promise<void> {
  return apiFetch<void>(`/attachments/${attachmentId}`, { method: 'DELETE' })
}

export function parseAttachment(attachmentId: string): Promise<Attachment> {
  return apiFetch<Attachment>(`/attachments/${attachmentId}/parse`, {
    method: 'POST',
    idempotencyKey: crypto.randomUUID(),
  })
}

export function getParseStatus(attachmentId: string): Promise<Attachment> {
  return apiFetch<Attachment>(`/attachments/${attachmentId}/parse-status`)
}

export function downloadAttachment(attachmentId: string, fileName: string): Promise<void> {
  return apiDownload(`/attachments/${attachmentId}/download`, fileName)
}

export function getAttachmentPreviewUrl(attachmentId: string): string {
  return `/api/v1/attachments/${attachmentId}/preview`
}
