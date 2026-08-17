import type { AnalysisTask, RiskFinding } from '@/types/domain'
import { API_BASE_URL, MOCK_ENABLED, apiFetch } from './client'

export function createAnalysisTask(documentId: string, idempotencyKey: string): Promise<AnalysisTask> {
  return apiFetch<AnalysisTask>(`/documents/${documentId}/analysis`, {
    method: 'POST',
    body: {},
    idempotencyKey,
  })
}

export function getAnalysisTask(taskId: string): Promise<AnalysisTask> {
  return apiFetch<AnalysisTask>(`/analysis-tasks/${taskId}`)
}

export function retryAnalysisTask(taskId: string): Promise<AnalysisTask> {
  return apiFetch<AnalysisTask>(`/analysis-tasks/${taskId}/retry`, {
    method: 'POST',
    idempotencyKey: crypto.randomUUID(),
  })
}

export function listTaskFindings(taskId: string): Promise<RiskFinding[]> {
  return apiFetch<RiskFinding[]>(`/analysis-tasks/${taskId}/findings`)
}

export function listDocumentFindings(documentId: string): Promise<RiskFinding[]> {
  return apiFetch<RiskFinding[]>(`/documents/${documentId}/risk-findings`)
}

export interface ReviewStatusPayload {
  review_status: 'confirmed' | 'dismissed' | 'pending'
  review_comment: string
}

export function patchFindingReviewStatus(
  findingId: string,
  payload: ReviewStatusPayload,
): Promise<RiskFinding> {
  return apiFetch<RiskFinding>(`/risk-findings/${findingId}/review-status`, {
    method: 'PATCH',
    body: payload,
  })
}

/* ---------------- SSE：任务事件订阅（SPEC 20 §5） ---------------- */

export interface TaskEventFrame {
  type: 'progress' | 'result' | 'error'
  step?: string
  status?: string
  task_id?: string
  data?: Record<string, unknown>
}

export type TaskEventState = 'connecting' | 'open' | 'reconnecting' | 'closed'

export interface TaskEventSubscription {
  close: () => void
}

/**
 * 订阅分析任务事件：progress / result / error。
 * 断线后：通过任务状态接口恢复 + 携带 Last-Event-ID 重新订阅，不重复创建任务。
 * 组件卸载时 close() 只关闭连接，不取消后端任务。
 */
export function subscribeTaskEvents(
  taskId: string,
  onEvent: (frame: TaskEventFrame) => void,
  onStateChange?: (state: TaskEventState) => void,
): TaskEventSubscription {
  if (MOCK_ENABLED) {
    return subscribeMockTaskEvents(taskId, onEvent, onStateChange)
  }

  let lastEventId = ''
  let closed = false
  let source: EventSource | null = null
  let reconcileTimer: number | null = null

  const open = (): void => {
    if (closed) return
    onStateChange?.('connecting')
    const url = lastEventId
      ? `${API_BASE_URL}/analysis-tasks/${taskId}/events?last_event_id=${encodeURIComponent(lastEventId)}`
      : `${API_BASE_URL}/analysis-tasks/${taskId}/events`
    source = new EventSource(url)
    source.onopen = () => onStateChange?.('open')
    source.onmessage = (event: MessageEvent<string>) => {
      if (event.lastEventId) lastEventId = event.lastEventId
      try {
        onEvent(JSON.parse(event.data) as TaskEventFrame)
      } catch {
        // 忽略无法解析的帧
      }
    }
    source.onerror = () => {
      if (closed) return
      onStateChange?.('reconnecting')
      // EventSource 会自动重连；同时用任务状态接口对齐一次事实状态
      if (reconcileTimer === null) {
        reconcileTimer = window.setTimeout(() => {
          reconcileTimer = null
          void getAnalysisTask(taskId)
            .then((task) => {
              onEvent({
                type: task.stage === 'succeeded' ? 'result' : 'progress',
                step: task.stage,
                status: task.stage === 'succeeded' ? 'success' : 'running',
                task_id: task.task_id,
              })
            })
            .catch(() => undefined)
        }, 1500)
      }
    }
  }

  open()

  return {
    close: () => {
      closed = true
      if (reconcileTimer !== null) window.clearTimeout(reconcileTimer)
      source?.close()
      onStateChange?.('closed')
    },
  }
}

function subscribeMockTaskEvents(
  taskId: string,
  onEvent: (frame: TaskEventFrame) => void,
  onStateChange?: (state: TaskEventState) => void,
): TaskEventSubscription {
  let closed = false
  onStateChange?.('open')
  const timer = window.setInterval(() => {
    if (closed) return
    void getAnalysisTask(taskId)
      .then((task) => {
        if (task.stage === 'succeeded') {
          onEvent({ type: 'progress', step: task.stage, status: 'running', task_id: task.task_id })
          onEvent({
            type: 'result',
            task_id: task.task_id,
            data: { document_version_id: task.document_version_id, report_status: 'draft' },
          })
          window.clearInterval(timer)
        } else if (task.stage === 'failed') {
          onEvent({ type: 'error', step: task.stage, task_id: task.task_id })
          window.clearInterval(timer)
        } else {
          onEvent({ type: 'progress', step: task.stage, status: 'running', task_id: task.task_id })
        }
      })
      .catch(() => undefined)
  }, 1200)
  return {
    close: () => {
      closed = true
      window.clearInterval(timer)
      onStateChange?.('closed')
    },
  }
}
