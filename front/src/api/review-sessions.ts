import type { ReviewSession, SessionMessage } from '@/types/domain'
import { apiFetch } from './client'

export function createReviewSession(documentId: string): Promise<ReviewSession> {
  return apiFetch<ReviewSession>('/review-sessions', {
    method: 'POST',
    body: { document_id: documentId },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function getReviewSession(sessionId: string): Promise<ReviewSession> {
  return apiFetch<ReviewSession>(`/review-sessions/${sessionId}`)
}

export function listMessages(sessionId: string): Promise<SessionMessage[]> {
  return apiFetch<SessionMessage[]>(`/review-sessions/${sessionId}/messages`)
}

export type SessionIntent =
  | 'identify_document'
  | 'start_analysis'
  | 'query_result'
  | 'explain_finding'
  | 'chitchat'

export function postMessage(
  sessionId: string,
  content: string,
  intent?: SessionIntent,
): Promise<SessionMessage[]> {
  return apiFetch<SessionMessage[]>(`/review-sessions/${sessionId}/messages`, {
    method: 'POST',
    body: { content, intent },
    idempotencyKey: crypto.randomUUID(),
  })
}

export function closeSession(sessionId: string, reason: string): Promise<ReviewSession> {
  return apiFetch<ReviewSession>(`/review-sessions/${sessionId}/close`, {
    method: 'POST',
    body: { reason },
    idempotencyKey: crypto.randomUUID(),
  })
}
