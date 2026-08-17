/**
 * Mock 路由 —— 仅开发模式（VITE_ENABLE_MOCK=true）生效。
 * 按 04-SPEC 接口路径匹配，返回贴合原型的示例数据；
 * 状态机（分析任务、附件解析、审批决定、报告导出）按时间线推进，可真实交互。
 */

import { ApiError } from '@/api/client'
import type {
  AnalysisTask,
  Attachment,
  DocumentDetail,
  SessionMessage,
} from '@/types/domain'
import { mockAuth } from './mock-auth'
import {
  analysisTaskSeed,
  amountComparisonSeed,
  approvalHistorySeed,
  approvalTasksSeed,
  attachmentsSeed,
  auditLogsSeed,
  documentLineItems,
  documentsSeed,
  findingsSeed,
  marketPricesSeed,
  mockUsers,
  reportsSeed,
  rulesSeed,
  sessionMessagesSeed,
  sessionSeed,
  supplierRiskSeed,
  supplierRulesSeed,
  versionsSeed,
  workflowsSeed,
  type MockUser,
} from './fixtures'

/* ---------------- 可变状态 ---------------- */

const state = {
  documents: structuredClone(documentsSeed),
  versions: structuredClone(versionsSeed),
  attachments: structuredClone(attachmentsSeed),
  findings: structuredClone(findingsSeed),
  tasks: new Map<string, { startedAt: number; documentId: string; documentVersionId: string }>(),
  approvalTasks: structuredClone(approvalTasksSeed),
  auditLogs: structuredClone(auditLogsSeed),
  workflows: structuredClone(workflowsSeed),
  rules: structuredClone(rulesSeed),
  session: structuredClone(sessionSeed),
  sessionMessages: structuredClone(sessionMessagesSeed),
  exports: new Map<string, { createdAt: number; documentVersionId: string }>(),
  attachmentUploads: new Map<string, number>(),
  idCounter: 100,
}

function nextId(prefix: string): string {
  state.idCounter += 1
  return `${prefix}-${state.idCounter}`
}

function currentUser(): MockUser {
  const token = mockAuth.token
  const user = mockUsers.find((u) => `mock.${u.user_id}` === token)
  if (!user) throw new ApiError(401, 'unauthorized', '登录已过期，请重新登录')
  return user
}

function findDocument(documentId: string): DocumentDetail {
  const doc = state.documents.find((d) => d.document_id === documentId)
  if (!doc) throw new ApiError(404, 'not_found', '单据不存在或已被删除')
  return doc
}

function appendAudit(action: string, resourceNo: string, result = 'success', detail?: string): void {
  const user = mockUsers.find((u) => `mock.${u.user_id}` === mockAuth.token)
  state.auditLogs.unshift({
    log_id: nextId('al'),
    occurred_at: new Date().toISOString(),
    actor_name: user?.display_name ?? '系统',
    action,
    resource_type: action.split('.')[0],
    resource_no: resourceNo,
    result,
    request_id: `req-${Math.random().toString(16).slice(2, 8)}`,
    detail,
  })
}

/* ---------------- 分析任务时间线 ---------------- */

const STAGE_TIMELINE: Array<{ untilMs: number; stage: AnalysisTask['stage'] }> = [
  { untilMs: 1500, stage: 'queued' },
  { untilMs: 3200, stage: 'querying_document' },
  { untilMs: 5000, stage: 'loading_attachments' },
  { untilMs: 8000, stage: 'parsing_attachments' },
  { untilMs: 11000, stage: 'analyzing' },
]

function stageFor(elapsed: number): string {
  for (const item of STAGE_TIMELINE) {
    if (elapsed < item.untilMs) return item.stage
  }
  return 'succeeded'
}

function buildTask(taskId: string): AnalysisTask {
  const timeline = state.tasks.get(taskId)
  if (!timeline) throw new ApiError(404, 'not_found', '分析任务不存在')
  const elapsed = Date.now() - timeline.startedAt
  const stage = stageFor(elapsed)
  const progress = Math.min(100, Math.round((elapsed / 11000) * 100))
  return {
    task_id: taskId,
    document_id: timeline.documentId,
    document_version_id: timeline.documentVersionId,
    stage,
    progress: stage === 'succeeded' ? 100 : progress,
    retry_count: 0,
    manual_takeover: false,
    started_at: new Date(timeline.startedAt).toISOString(),
    finished_at: stage === 'succeeded' ? new Date(timeline.startedAt + 11000).toISOString() : undefined,
  }
}

function startTask(documentId: string, documentVersionId: string): AnalysisTask {
  const taskId = nextId('task')
  state.tasks.set(taskId, { startedAt: Date.now(), documentId, documentVersionId })
  return buildTask(taskId)
}

/* ---------------- 附件解析时间线 ---------------- */

function parseStatusFor(attachmentId: string, uploadedAt: string): string {
  const started = state.attachmentUploads.get(attachmentId) ?? Date.parse(uploadedAt)
  const elapsed = Date.now() - started
  if (elapsed < 1600) return 'pending'
  if (elapsed < 3400) return 'parsing'
  return 'succeeded'
}

function decorateAttachment(att: Attachment): Attachment {
  return { ...att, parse_status: parseStatusFor(att.attachment_id, att.uploaded_at) }
}

/* ---------------- 会话回复 ---------------- */

function assistantReply(content: string, intent?: string): SessionMessage {
  const text =
    intent === 'start_analysis'
      ? '已创建分析任务，正在按顺序执行：读取单据 → 加载附件 → 解析附件 → 规则与风险分析。完成后我会推送结果。'
      : intent === 'query_result'
        ? '当前分析已完成：共 4 条风险（高 1、中 2、低 1），其中 1 条证据不足待人工确认。详情可在风险分析页查看。'
        : intent === 'explain_finding'
          ? `关于「${content.slice(0, 24)}」：该风险由确定性规则命中，置信度与证据已绑定附件页码和原文片段，可在证据抽屉中核对。`
          : '收到。你可以让我“开始风险分析”或“查询分析结果”，也可以让我解释某条风险的依据。'
  return {
    message_id: nextId('m'),
    role: 'assistant',
    content: text,
    intent,
    created_at: new Date().toISOString(),
  }
}

/* ---------------- 路由表 ---------------- */

type Query = Record<string, unknown>
type Body = Record<string, unknown>
type Handler = (match: RegExpMatchArray, body: Body, query: Query) => unknown

const routes: Array<{ method: string; pattern: RegExp; handler: Handler }> = [
  /* ---- 认证 ---- */
  {
    method: 'POST',
    pattern: /^\/auth\/login$/,
    handler: (_m, body) => {
      const username = String(body.username ?? '')
      const password = String(body.password ?? '')
      const user = mockUsers.find((u) => u.username === username)
      if (!user || user.password !== password) {
        throw new ApiError(401, 'unauthorized', '用户名或密码错误')
      }
      mockAuth.token = `mock.${user.user_id}`
      return { access_token: mockAuth.token, token_type: 'bearer', expires_in: 1800 }
    },
  },
  {
    method: 'GET',
    pattern: /^\/auth\/me$/,
    handler: () => {
      const user = currentUser()
      return {
        user_id: user.user_id,
        username: user.username,
        display_name: user.display_name,
        department: user.department,
        roles: user.roles,
        org_scope: user.org_scope,
      }
    },
  },
  {
    method: 'POST',
    pattern: /^\/auth\/logout$/,
    handler: () => {
      mockAuth.token = ''
      return undefined
    },
  },

  /* ---- 单据 ---- */
  {
    method: 'GET',
    pattern: /^\/documents$/,
    handler: (_m, _b, query) => {
      const user = currentUser()
      let items = [...state.documents]
      if (user.roles.includes('applicant') && !user.roles.some((r) => r === 'finance' || r === 'approver')) {
        items = items.filter((d) => d.applicant_id === user.user_id)
      }
      if (user.roles.length === 1 && user.roles[0] === 'admin') {
        items = []
      }
      const status = String(query.document_status ?? '')
      if (status) items = items.filter((d) => d.document_status === status)
      const keyword = String(query.keyword ?? '').trim()
      if (keyword) {
        items = items.filter(
          (d) => d.document_no.includes(keyword) || d.expense_category.includes(keyword),
        )
      }
      items.sort((a, b) => b.created_at.localeCompare(a.created_at))
      return paginate(items, query)
    },
  },
  {
    method: 'POST',
    pattern: /^\/documents$/,
    handler: (_m, body) => {
      currentUser()
      const now = new Date().toISOString()
      const doc: DocumentDetail = {
        document_id: nextId('d'),
        document_no: `报销单-${now.slice(0, 10).replace(/-/g, '')}`,
        document_type: 'expense_reimbursement',
        expense_category: String(body.expense_category ?? '市场推广费'),
        applicant_id: 'u-applicant',
        applicant_name: '李申请',
        applicant_department: String(body.applicant_department ?? '市场部'),
        budget_department: body.budget_department ? String(body.budget_department) : undefined,
        total_amount: String(body.total_amount ?? '0.00'),
        currency: 'CNY',
        document_status: 'draft',
        current_version: 0,
        apply_date: String(body.apply_date ?? now.slice(0, 10)),
        payee_name: body.payee_name ? String(body.payee_name) : undefined,
        payee_account: body.payee_account ? String(body.payee_account) : undefined,
        payee_bank: body.payee_bank ? String(body.payee_bank) : undefined,
        reason_text: String(body.reason_text ?? ''),
        line_items: [],
        created_at: now,
        updated_at: now,
      }
      state.documents.unshift(doc)
      appendAudit('document.create', doc.document_no)
      return doc
    },
  },
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const doc = findDocument(m[1]!)
      return { ...doc, line_items: documentLineItems[doc.document_id] ?? doc.line_items ?? [] }
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/documents\/([^/]+)$/,
    handler: (m, body) => {
      currentUser()
      const doc = findDocument(m[1]!)
      if (doc.document_status !== 'draft' && doc.document_status !== 'returned') {
        throw new ApiError(409, 'version_conflict', '单据当前状态不可编辑，请刷新后查看')
      }
      for (const key of [
        'expense_category',
        'applicant_department',
        'budget_department',
        'apply_date',
        'total_amount',
        'payee_name',
        'payee_account',
        'payee_bank',
        'reason_text',
      ] as const) {
        if (body[key] !== undefined) (doc as unknown as Record<string, unknown>)[key] = body[key]
      }
      doc.updated_at = new Date().toISOString()
      appendAudit('document.update', doc.document_no)
      return { ...doc, line_items: documentLineItems[doc.document_id] ?? [] }
    },
  },
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/copy$/,
    handler: (m) => {
      currentUser()
      const source = findDocument(m[1]!)
      const now = new Date().toISOString()
      const copy: DocumentDetail = {
        ...structuredClone(source),
        document_id: nextId('d'),
        document_no: `报销单-${now.slice(0, 10).replace(/-/g, '')}`,
        document_status: 'draft',
        current_version: 0,
        line_items: [],
        created_at: now,
        updated_at: now,
      }
      state.documents.unshift(copy)
      appendAudit('document.copy', `${source.document_no} → ${copy.document_no}`)
      return copy
    },
  },
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/submit$/,
    handler: (m) => {
      currentUser()
      const doc = findDocument(m[1]!)
      if (doc.document_status !== 'draft' && doc.document_status !== 'returned') {
        throw new ApiError(409, 'version_conflict', '只有草稿或退回状态的单据可以提交')
      }
      const versionNo = doc.current_version + 1
      const versionId = nextId('dv')
      state.versions.unshift({
        document_version_id: versionId,
        version_no: versionNo,
        created_by: doc.applicant_name,
        created_at: new Date().toISOString(),
        trigger: versionNo === 1 ? 'submit' : 'resubmit',
        change_summary: versionNo === 1 ? '首次提交' : '退回后重新提交',
        finding_count: 0,
        overall_risk_level: undefined,
      })
      doc.current_version = versionNo
      doc.document_status = 'pending_review'
      doc.updated_at = new Date().toISOString()
      const task = startTask(doc.document_id, versionId)
      doc.analysis_task_id = task.task_id
      appendAudit('document.submit', `${doc.document_no} v${versionNo}`)
      return {
        document_id: doc.document_id,
        document_version_id: versionId,
        analysis_task_id: task.task_id,
        status: doc.document_status,
      }
    },
  },
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/withdraw$/,
    handler: (m) => {
      const user = currentUser()
      const doc = findDocument(m[1]!)
      if (doc.applicant_id !== user.user_id) throw new ApiError(403, 'forbidden', '只能操作本人单据')
      if (!['pending_review', 'reviewing'].includes(doc.document_status)) {
        throw new ApiError(409, 'version_conflict', '当前状态不可撤回')
      }
      doc.document_status = 'withdrawn'
      doc.updated_at = new Date().toISOString()
      appendAudit('document.withdraw', doc.document_no)
      return undefined
    },
  },
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/void$/,
    handler: (m) => {
      const user = currentUser()
      const doc = findDocument(m[1]!)
      if (doc.applicant_id !== user.user_id) throw new ApiError(403, 'forbidden', '只能操作本人单据')
      if (['approved', 'voided'].includes(doc.document_status)) {
        throw new ApiError(409, 'version_conflict', '当前状态不可作废')
      }
      doc.document_status = 'voided'
      doc.updated_at = new Date().toISOString()
      appendAudit('document.void', doc.document_no)
      return undefined
    },
  },
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)\/versions$/,
    handler: (m) => {
      currentUser()
      const doc = findDocument(m[1]!)
      const own = state.versions.filter((v) =>
        v.document_version_id.includes(doc.document_id.replace('d-', '')) ||
        (doc.document_id === 'd-20260815' && v.document_version_id.includes('20260815')),
      )
      return own.length > 0 ? own : state.versions
    },
  },
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)\/approval-history$/,
    handler: (m) => {
      currentUser()
      findDocument(m[1]!)
      return approvalHistorySeed[m[1]!] ?? []
    },
  },

  /* ---- 明细 ---- */
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/line-items$/,
    handler: (m, body) => {
      currentUser()
      const doc = findDocument(m[1]!)
      const items = (documentLineItems[doc.document_id] ??= [])
      const item = {
        item_id: nextId('li'),
        expense_item: String(body.expense_item ?? ''),
        expense_date: String(body.expense_date ?? ''),
        amount: String(body.amount ?? '0.00'),
        currency: 'CNY',
        invoice_no: body.invoice_no ? String(body.invoice_no) : undefined,
        remark: body.remark ? String(body.remark) : undefined,
      }
      items.push(item)
      return item
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/documents\/([^/]+)\/line-items\/([^/]+)$/,
    handler: (m, body) => {
      currentUser()
      const items = documentLineItems[m[1]!] ?? []
      const item = items.find((i) => i.item_id === m[2])
      if (!item) throw new ApiError(404, 'not_found', '明细不存在')
      Object.assign(item, body)
      return item
    },
  },
  {
    method: 'DELETE',
    pattern: /^\/documents\/([^/]+)\/line-items\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const items = documentLineItems[m[1]!] ?? []
      const index = items.findIndex((i) => i.item_id === m[2])
      if (index >= 0) items.splice(index, 1)
      return undefined
    },
  },

  /* ---- 附件 ---- */
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)\/attachments$/,
    handler: (m) => {
      currentUser()
      findDocument(m[1]!)
      return state.attachments.map(decorateAttachment)
    },
  },
  {
    method: 'DELETE',
    pattern: /^\/attachments\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const index = state.attachments.findIndex((a) => a.attachment_id === m[1])
      if (index < 0) throw new ApiError(404, 'not_found', '附件不存在')
      const [removed] = state.attachments.splice(index, 1)
      appendAudit('attachment.delete', removed!.file_name)
      return undefined
    },
  },
  {
    method: 'GET',
    pattern: /^\/attachments\/([^/]+)\/parse-status$/,
    handler: (m) => {
      currentUser()
      const att = state.attachments.find((a) => a.attachment_id === m[1])
      if (!att) throw new ApiError(404, 'not_found', '附件不存在')
      return decorateAttachment(att)
    },
  },
  {
    method: 'POST',
    pattern: /^\/attachments\/([^/]+)\/parse$/,
    handler: (m) => {
      currentUser()
      const att = state.attachments.find((a) => a.attachment_id === m[1])
      if (!att) throw new ApiError(404, 'not_found', '附件不存在')
      state.attachmentUploads.set(att.attachment_id, Date.now())
      return decorateAttachment(att)
    },
  },

  /* ---- 分析任务与风险 ---- */
  {
    method: 'POST',
    pattern: /^\/documents\/([^/]+)\/analysis$/,
    handler: (m) => {
      currentUser()
      const doc = findDocument(m[1]!)
      const versionId = state.versions[0]?.document_version_id ?? `dv-${doc.document_id}-v${doc.current_version}`
      const task = startTask(doc.document_id, versionId)
      appendAudit('analysis_task.create', task.task_id)
      return task
    },
  },
  {
    method: 'GET',
    pattern: /^\/analysis-tasks\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      if (m[1] === analysisTaskSeed.task_id) return analysisTaskSeed
      return buildTask(m[1]!)
    },
  },
  {
    method: 'POST',
    pattern: /^\/analysis-tasks\/([^/]+)\/retry$/,
    handler: (m) => {
      currentUser()
      const existing = state.tasks.get(m[1]!)
      if (!existing) throw new ApiError(404, 'not_found', '分析任务不存在')
      existing.startedAt = Date.now()
      appendAudit('analysis_task.retry', m[1]!)
      return buildTask(m[1]!)
    },
  },
  {
    method: 'GET',
    pattern: /^\/(analysis-tasks|documents)\/([^/]+)(\/risk-findings|\/findings)$/,
    handler: (_m) => {
      currentUser()
      return state.findings
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/risk-findings\/([^/]+)\/review-status$/,
    handler: (m, body) => {
      const user = currentUser()
      const finding = state.findings.find((f) => f.finding_id === m[1])
      if (!finding) throw new ApiError(404, 'not_found', '风险项不存在')
      finding.review_status = String(body.review_status ?? 'pending')
      finding.reviewed_by = user.display_name
      finding.reviewed_at = new Date().toISOString()
      finding.review_comment = String(body.review_comment ?? '')
      appendAudit('risk_finding.review', finding.finding_id, 'success', `${finding.review_status}：${finding.review_comment}`)
      return finding
    },
  },

  /* ---- 金额核对 / 供应商 ---- */
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)\/amount-comparison$/,
    handler: (m) => {
      currentUser()
      findDocument(m[1]!)
      return amountComparisonSeed
    },
  },
  {
    method: 'GET',
    pattern: /^\/(supplier-risks|suppliers)\/([^/]+)(\/risks)?$/,
    handler: () => {
      currentUser()
      return supplierRiskSeed
    },
  },

  /* ---- 审批 ---- */
  {
    method: 'GET',
    pattern: /^\/approval-tasks$/,
    handler: (_m, _b, query) => {
      const user = currentUser()
      let items = state.approvalTasks.filter((t) => t.assignee_id === user.user_id)
      if (user.roles.includes('finance') && !user.roles.includes('approver')) {
        items = state.approvalTasks.filter((t) => t.node_name.includes('财务'))
      }
      const status = String(query.task_status ?? '')
      if (status) items = items.filter((t) => t.task_status === status)
      const keyword = String(query.keyword ?? '').trim()
      if (keyword) items = items.filter((t) => t.document_no.includes(keyword))
      return paginate(items, query)
    },
  },
  {
    method: 'GET',
    pattern: /^\/approval-tasks\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const task = state.approvalTasks.find((t) => t.task_id === m[1])
      if (!task) throw new ApiError(404, 'not_found', '审批任务不存在')
      return task
    },
  },
  {
    method: 'POST',
    pattern: /^\/approval-tasks\/([^/]+)\/decision$/,
    handler: (m, body) => {
      const user = currentUser()
      const task = state.approvalTasks.find((t) => t.task_id === m[1])
      if (!task) throw new ApiError(404, 'not_found', '审批任务不存在')
      if (task.assignee_id !== user.user_id) {
        throw new ApiError(403, 'forbidden', '该任务未分配给当前用户')
      }
      if (task.task_status !== 'pending') {
        throw new ApiError(409, 'version_conflict', '任务已被处理，请刷新查看最新状态')
      }
      const decision = String(body.decision ?? '')
      const comment = String(body.review_comment ?? '')
      if (!['approve', 'return', 'reject'].includes(decision)) {
        throw new ApiError(422, 'validation_error', '决定必须为 approve / return / reject')
      }
      if (!comment.trim()) {
        throw new ApiError(422, 'validation_error', '审批意见不能为空')
      }
      task.task_status = decision === 'approve' ? 'approved' : decision === 'return' ? 'returned' : 'rejected'
      task.decision = decision
      task.review_comment = comment
      task.processed_at = new Date().toISOString()
      const doc = state.documents.find((d) => d.document_id === task.document_id)
      if (doc) {
        doc.document_status =
          decision === 'approve' ? 'approved' : decision === 'return' ? 'returned' : 'rejected'
        doc.updated_at = new Date().toISOString()
      }
      appendAudit('approval_task.decision', `${task.document_no} / ${task.node_name}`, 'success', `decision=${decision}`)
      return task
    },
  },

  /* ---- 审核会话 ---- */
  {
    method: 'GET',
    pattern: /^\/review-sessions\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      if (m[1] !== state.session.session_id) throw new ApiError(404, 'not_found', '会话不存在')
      return state.session
    },
  },
  {
    method: 'GET',
    pattern: /^\/review-sessions\/([^/]+)\/messages$/,
    handler: () => {
      currentUser()
      return state.sessionMessages
    },
  },
  {
    method: 'POST',
    pattern: /^\/review-sessions\/([^/]+)\/messages$/,
    handler: (_m, body) => {
      currentUser()
      const content = String(body.content ?? '')
      const intent = body.intent ? String(body.intent) : undefined
      state.sessionMessages.push({
        message_id: nextId('m'),
        role: 'user',
        content,
        intent,
        created_at: new Date().toISOString(),
      })
      const reply = assistantReply(content, intent)
      state.sessionMessages.push(reply)
      if (intent === 'start_analysis' && !state.tasks.has('task-live-session')) {
        state.tasks.set('task-live-session', {
          startedAt: Date.now(),
          documentId: state.session.document_id,
          documentVersionId: state.session.document_id.includes('20260815')
            ? 'dv-20260815-v2'
            : 'dv-20260815-v2',
        })
        state.session.analysis_task_id = 'task-live-session'
      }
      return [...state.sessionMessages]
    },
  },
  {
    method: 'POST',
    pattern: /^\/review-sessions\/([^/]+)\/close$/,
    handler: (m) => {
      currentUser()
      if (m[1] !== state.session.session_id) throw new ApiError(404, 'not_found', '会话不存在')
      state.session.session_status = 'closed'
      appendAudit('review_session.close', state.session.session_id)
      return state.session
    },
  },

  /* ---- 报告 ---- */
  {
    method: 'GET',
    pattern: /^\/review-reports\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const report = reportsSeed.find((r) => r.document_version_id === m[1])
      if (!report) throw new ApiError(404, 'not_found', '报告尚未生成')
      return report
    },
  },
  {
    method: 'GET',
    pattern: /^\/documents\/([^/]+)\/review-reports$/,
    handler: (m) => {
      currentUser()
      const doc = findDocument(m[1]!)
      if (doc.document_id === 'd-20260815') {
        return reportsSeed.map((r) => ({
          document_version_id: r.document_version_id,
          version_no: r.version_no,
          report_status: r.report_status,
          overall_risk_level: r.overall_risk_level,
          generated_at: r.generated_at,
        }))
      }
      return []
    },
  },
  {
    method: 'POST',
    pattern: /^\/review-reports\/([^/]+)\/export$/,
    handler: (m) => {
      currentUser()
      const exportTaskId = nextId('exp')
      state.exports.set(exportTaskId, { createdAt: Date.now(), documentVersionId: m[1]! })
      appendAudit('review_report.export', m[1]!)
      return { export_task_id: exportTaskId, status: 'running' }
    },
  },
  {
    method: 'GET',
    pattern: /^\/review-reports\/exports\/([^/]+)$/,
    handler: (m) => {
      currentUser()
      const exp = state.exports.get(m[1]!)
      if (!exp) throw new ApiError(404, 'not_found', '导出任务不存在')
      return {
        export_task_id: m[1],
        status: Date.now() - exp.createdAt > 1500 ? 'succeeded' : 'running',
        file_name: `审核报告_${exp.documentVersionId}.pdf`,
      }
    },
  },

  /* ---- 规则 / 参数 ---- */
  {
    method: 'GET',
    pattern: /^\/rules$/,
    handler: (_m, _b, query) => {
      currentUser()
      let items = [...state.rules]
      const keyword = String(query.keyword ?? '').trim()
      if (keyword) {
        items = items.filter((r) => r.rule_name.includes(keyword) || r.rule_code.includes(keyword))
      }
      const ruleType = String(query.rule_type ?? '')
      if (ruleType) items = items.filter((r) => r.rule_type === ruleType)
      return paginate(items, query)
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/rules\/([^/]+)$/,
    handler: (m, body) => {
      currentUser()
      const rule = state.rules.find((r) => r.rule_id === m[1])
      if (!rule) throw new ApiError(404, 'not_found', '规则不存在')
      if (body.params) rule.params = body.params as Record<string, string>
      if (body.status) rule.status = String(body.status)
      rule.updated_at = new Date().toISOString()
      appendAudit('rule.update', rule.rule_code)
      return rule
    },
  },
  {
    method: 'POST',
    pattern: /^\/rules\/([^/]+)\/publish$/,
    handler: (m) => {
      currentUser()
      const rule = state.rules.find((r) => r.rule_id === m[1])
      if (!rule) throw new ApiError(404, 'not_found', '规则不存在')
      rule.status = 'published'
      const minor = Number(rule.rule_version.replace('v', '')) + 0.1
      rule.rule_version = `v${minor.toFixed(1)}`
      rule.updated_at = new Date().toISOString()
      appendAudit('rule.publish', rule.rule_code)
      return rule
    },
  },
  {
    method: 'GET',
    pattern: /^\/market-price-references$/,
    handler: () => {
      currentUser()
      return marketPricesSeed
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/market-price-references\/([^/]+)$/,
    handler: (m, body) => {
      currentUser()
      const item = marketPricesSeed.find((i) => i.id === m[1])
      if (!item) throw new ApiError(404, 'not_found', '市场价条目不存在')
      item.reference_price = String(body.reference_price ?? item.reference_price)
      appendAudit('market_price.update', item.item_name)
      return item
    },
  },
  {
    method: 'GET',
    pattern: /^\/supplier-risk-rules$/,
    handler: () => {
      currentUser()
      return supplierRulesSeed
    },
  },
  {
    method: 'GET',
    pattern: /^\/system-parameters$/,
    handler: () => {
      currentUser()
      return [
        { key: 'analysis.retry_max', value: '3', description: '分析任务自动重试上限，超过后转人工接管', updated_at: '2026-07-20T10:00:00+08:00' },
        { key: 'analysis.retry_backoff_seconds', value: '30', description: '重试指数退避基数（秒）', updated_at: '2026-07-20T10:00:00+08:00' },
        { key: 'ocr.timeout_seconds', value: '120', description: 'OCR 适配器超时', updated_at: '2026-06-30T09:00:00+08:00' },
        { key: 'llm.timeout_seconds', value: '60', description: 'LLM 适配器超时', updated_at: '2026-06-30T09:00:00+08:00' },
        { key: 'export.max_rows', value: '10000', description: '审计/报告导出最大行数', updated_at: '2026-05-11T11:20:00+08:00' },
      ]
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/supplier-risk-rules\/([^/]+)$/,
    handler: (m, body) => {
      currentUser()
      const item = supplierRulesSeed.find((i) => i.id === m[1])
      if (!item) throw new ApiError(404, 'not_found', '供应商规则不存在')
      if (body.enabled !== undefined) item.enabled = Boolean(body.enabled)
      if (body.threshold) item.threshold = String(body.threshold)
      appendAudit('supplier_rule.update', `${item.supplier_name}/${item.rule_name}`)
      return item
    },
  },

  /* ---- 流程配置 ---- */
  {
    method: 'GET',
    pattern: /^\/approval-workflows$/,
    handler: () => {
      currentUser()
      return state.workflows
    },
  },
  {
    method: 'PATCH',
    pattern: /^\/approval-workflows\/([^/]+)$/,
    handler: (m, body) => {
      const user = currentUser()
      if (!user.roles.includes('admin')) throw new ApiError(403, 'forbidden', '仅管理员可维护流程配置')
      const wf = state.workflows.find((w) => w.workflow_id === m[1])
      if (!wf) throw new ApiError(404, 'not_found', '流程模板不存在')
      if (wf.status === 'published' && body.status !== 'disabled') {
        throw new ApiError(409, 'version_conflict', '已发布模板不可直接修改，请新建草稿版本')
      }
      if (body.status) wf.status = String(body.status)
      if (Array.isArray(body.nodes)) {
        wf.nodes = body.nodes as typeof wf.nodes
      }
      if (body.match_condition) wf.match_condition = String(body.match_condition)
      wf.updated_at = new Date().toISOString()
      appendAudit('approval_workflow.update', `${wf.name} v${wf.version}`)
      return wf
    },
  },
  {
    method: 'POST',
    pattern: /^\/approval-workflows\/([^/]+)\/publish$/,
    handler: (m) => {
      const user = currentUser()
      if (!user.roles.includes('admin')) throw new ApiError(403, 'forbidden', '仅管理员可发布流程')
      const wf = state.workflows.find((w) => w.workflow_id === m[1])
      if (!wf) throw new ApiError(404, 'not_found', '流程模板不存在')
      wf.status = 'published'
      wf.published_at = new Date().toISOString()
      appendAudit('approval_workflow.publish', `${wf.name} v${wf.version}`)
      return wf
    },
  },

  /* ---- 审计 ---- */
  {
    method: 'GET',
    pattern: /^\/audit-logs$/,
    handler: (_m, _b, query) => {
      const user = currentUser()
      if (!user.roles.includes('admin')) throw new ApiError(403, 'forbidden', '仅授权管理员可查看审计日志')
      let items = [...state.auditLogs]
      const action = String(query.action ?? '')
      if (action) items = items.filter((l) => l.action.includes(action))
      const actor = String(query.actor ?? '')
      if (actor) items = items.filter((l) => l.actor_name.includes(actor))
      const requestId = String(query.request_id ?? '')
      if (requestId) items = items.filter((l) => l.request_id.includes(requestId))
      return paginate(items, query)
    },
  },
]

function paginate<T>(items: T[], query: Query): { items: T[]; total: number; page: number; page_size: number } {
  const page = Number(query.page ?? 1) || 1
  const pageSize = Number(query.page_size ?? 50) || 50
  const start = (page - 1) * pageSize
  return { items: items.slice(start, start + pageSize), total: items.length, page, page_size: pageSize }
}

/* ---------------- 入口 ---------------- */

export interface MockResult<T> {
  handled: boolean
  data?: T
}

async function delay(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 220 + Math.random() * 260))
}

export async function mockRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  query?: object,
): Promise<MockResult<T>> {
  const cleanPath = path.split('?')[0] ?? path
  for (const route of routes) {
    if (route.method !== method) continue
    const match = cleanPath.match(route.pattern)
    if (!match) continue
    await delay()
    const data = route.handler(match, (body ?? {}) as Body, (query ?? {}) as Query) as T
    return { handled: true, data }
  }
  return { handled: false }
}

export async function mockUpload<T>(
  path: string,
  file: File,
  _extra?: Record<string, string>,
): Promise<MockResult<T>> {
  const match = path.match(/^\/documents\/([^/]+)\/attachments$/)
  if (!match) return { handled: false }
  await delay()
  currentUser()
  findDocument(match[1]!)
  const attachmentId = nextId('att')
  state.attachmentUploads.set(attachmentId, Date.now())
  const att: Attachment = {
    attachment_id: attachmentId,
    file_name: file.name,
    file_size: file.size,
    mime_type: file.type || 'application/octet-stream',
    storage_status: 'stored',
    parse_status: 'pending',
    required_kind: undefined,
    uploaded_by: mockUsers.find((u) => `mock.${u.user_id}` === mockAuth.token)?.display_name ?? '—',
    uploaded_at: new Date().toISOString(),
  }
  state.attachments.push(att)
  appendAudit('attachment.upload', att.file_name)
  return { handled: true, data: att as T }
}
