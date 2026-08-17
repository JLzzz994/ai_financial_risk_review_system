import type { ApprovalHistoryNode, ApprovalTask, Paginated } from '@/types/domain'
import { apiFetch } from './client'

export interface ApprovalTaskQuery {
  page?: number
  page_size?: number
  task_status?: string
  keyword?: string
}

export function listApprovalTasks(query: ApprovalTaskQuery = {}): Promise<Paginated<ApprovalTask>> {
  return apiFetch<Paginated<ApprovalTask>>('/approval-tasks', { query })
}

export function getApprovalTask(taskId: string): Promise<ApprovalTask> {
  return apiFetch<ApprovalTask>(`/approval-tasks/${taskId}`)
}

export type DecisionValue = 'approve' | 'return' | 'reject'

export interface DecisionPayload {
  decision: DecisionValue
  review_comment: string
}

/**
 * 唯一审批决定接口（SPEC 13）。
 * 幂等键由调用方生成并在重试时复用。
 */
export function submitDecision(
  taskId: string,
  payload: DecisionPayload,
  idempotencyKey: string,
): Promise<ApprovalTask> {
  return apiFetch<ApprovalTask>(`/approval-tasks/${taskId}/decision`, {
    method: 'POST',
    body: payload,
    idempotencyKey,
  })
}

export function getApprovalHistory(documentId: string): Promise<ApprovalHistoryNode[]> {
  return apiFetch<ApprovalHistoryNode[]>(`/documents/${documentId}/approval-history`)
}
