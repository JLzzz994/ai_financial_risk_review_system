import type { WorkflowTemplate } from '@/types/domain'
import { apiFetch } from './client'

export function listWorkflows(): Promise<WorkflowTemplate[]> {
  return apiFetch<WorkflowTemplate[]>('/approval-workflows')
}

export interface WorkflowPayload {
  name: string
  match_condition: string
  nodes: Array<{
    order: number
    name: string
    approver_role: string
    approver_names: string
  }>
}

export function createWorkflowDraft(payload: WorkflowPayload): Promise<WorkflowTemplate> {
  return apiFetch<WorkflowTemplate>('/approval-workflows', {
    method: 'POST',
    body: payload,
    idempotencyKey: crypto.randomUUID(),
  })
}

export function patchWorkflow(
  workflowId: string,
  payload: Partial<WorkflowPayload> & { status?: string },
): Promise<WorkflowTemplate> {
  return apiFetch<WorkflowTemplate>(`/approval-workflows/${workflowId}`, {
    method: 'PATCH',
    body: payload,
  })
}

/** 发布必须二次确认并填写原因（SPEC 19 §2） */
export function publishWorkflow(workflowId: string, reason: string): Promise<WorkflowTemplate> {
  return apiFetch<WorkflowTemplate>(`/approval-workflows/${workflowId}/publish`, {
    method: 'POST',
    body: { reason },
    idempotencyKey: crypto.randomUUID(),
  })
}
