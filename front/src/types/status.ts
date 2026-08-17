/**
 * 状态映射 —— 唯一真相源。
 * 前端只保存/传输小写机器值，中文标签仅用于展示（SPEC 20 §3）。
 */

export type StatusTone = 'gray' | 'blue' | 'green' | 'orange' | 'red' | 'purple'

export interface StatusView {
  label: string
  tone: StatusTone
}

/** 单据状态（SPEC 20 §3 statusMap 原文照抄，另含 manual_review） */
export const documentStatusMap = {
  draft: { label: '草稿', tone: 'gray' },
  pending_review: { label: '待审核', tone: 'blue' },
  reviewing: { label: '复核中', tone: 'orange' },
  pending_approval: { label: '待审批', tone: 'purple' },
  approved: { label: '已通过', tone: 'green' },
  returned: { label: '已退回', tone: 'orange' },
  rejected: { label: '已驳回', tone: 'red' },
  withdrawn: { label: '已撤回', tone: 'gray' },
  voided: { label: '已作废', tone: 'gray' },
  manual_review: { label: '待人工确认', tone: 'orange' },
} as const satisfies Record<string, StatusView>

export type DocumentStatus = keyof typeof documentStatusMap

/** 审批任务状态（ApprovalTaskStatus） */
export const approvalTaskStatusMap = {
  pending: { label: '待处理', tone: 'blue' },
  approved: { label: '已通过', tone: 'green' },
  returned: { label: '已退回', tone: 'orange' },
  rejected: { label: '已驳回', tone: 'red' },
  cancelled: { label: '已取消', tone: 'gray' },
} as const satisfies Record<string, StatusView>

export type ApprovalTaskStatus = keyof typeof approvalTaskStatusMap

/** 审批决定（ApprovalDecision） */
export const approvalDecisionMap = {
  approve: { label: '审批通过', tone: 'green' },
  return: { label: '退回修改', tone: 'orange' },
  reject: { label: '驳回', tone: 'red' },
} as const satisfies Record<string, StatusView>

export type ApprovalDecisionValue = keyof typeof approvalDecisionMap

/** 附件存储状态 */
export const attachmentStorageMap = {
  uploading: { label: '上传中', tone: 'blue' },
  stored: { label: '已存储', tone: 'green' },
  failed: { label: '上传失败', tone: 'red' },
} as const satisfies Record<string, StatusView>

/** 附件解析状态（含 manual_review） */
export const attachmentParseMap = {
  pending: { label: '待解析', tone: 'gray' },
  parsing: { label: '解析中', tone: 'blue' },
  succeeded: { label: '解析成功', tone: 'green' },
  failed: { label: '解析失败', tone: 'red' },
  manual_review: { label: '待人工确认', tone: 'orange' },
} as const satisfies Record<string, StatusView>

/** 分析任务阶段（AnalysisTaskStatus） */
export const analysisStageMap = {
  queued: { label: '排队中', tone: 'gray' },
  querying_document: { label: '读取单据', tone: 'blue' },
  loading_attachments: { label: '加载附件', tone: 'blue' },
  parsing_attachments: { label: '解析附件', tone: 'blue' },
  analyzing: { label: '规则与风险分析', tone: 'blue' },
  succeeded: { label: '分析完成', tone: 'green' },
  failed: { label: '分析失败', tone: 'red' },
  cancelled: { label: '已取消', tone: 'gray' },
} as const satisfies Record<string, StatusView>

export type AnalysisStage = keyof typeof analysisStageMap

export const ANALYSIS_STAGE_ORDER: AnalysisStage[] = [
  'queued',
  'querying_document',
  'loading_attachments',
  'parsing_attachments',
  'analyzing',
  'succeeded',
]

/** 风险等级 */
export const riskLevelMap = {
  high: { label: '高风险', tone: 'red' },
  medium: { label: '中风险', tone: 'orange' },
  low: { label: '低风险', tone: 'green' },
  none: { label: '无风险', tone: 'gray' },
} as const satisfies Record<string, StatusView>

export type RiskLevel = keyof typeof riskLevelMap

/** 风险项人工复核状态 */
export const reviewStatusMap = {
  pending: { label: '待复核', tone: 'blue' },
  confirmed: { label: '已确认风险', tone: 'red' },
  dismissed: { label: '已排除', tone: 'green' },
  manual_review: { label: '待人工确认', tone: 'orange' },
} as const satisfies Record<string, StatusView>

export type ReviewStatus = keyof typeof reviewStatusMap

/** 报告状态 */
export const reportStatusMap = {
  draft: { label: '草稿', tone: 'gray' },
  generating: { label: '生成中', tone: 'blue' },
  succeeded: { label: '已生成', tone: 'green' },
  final: { label: '正式报告', tone: 'green' },
  failed: { label: '生成失败', tone: 'red' },
} as const satisfies Record<string, StatusView>

/** 审核会话状态 */
export const sessionStatusMap = {
  active: { label: '进行中', tone: 'blue' },
  closed: { label: '已关闭', tone: 'gray' },
} as const satisfies Record<string, StatusView>

/** 流程/规则配置状态 */
export const configStatusMap = {
  draft: { label: '草稿', tone: 'gray' },
  published: { label: '已发布', tone: 'green' },
  disabled: { label: '已停用', tone: 'gray' },
  enabled: { label: '已启用', tone: 'green' },
} as const satisfies Record<string, StatusView>

/** 审计结果 */
export const auditResultMap = {
  success: { label: '成功', tone: 'green' },
  failed: { label: '失败', tone: 'red' },
} as const satisfies Record<string, StatusView>

function view<T extends Record<string, StatusView>>(map: T, value: string | null | undefined): StatusView {
  if (value && value in map) return map[value as keyof T]
  return { label: value ?? '—', tone: 'gray' }
}

export const documentStatusView = (v?: string | null) => view(documentStatusMap, v)
export const approvalTaskStatusView = (v?: string | null) => view(approvalTaskStatusMap, v)
export const approvalDecisionView = (v?: string | null) => view(approvalDecisionMap, v)
export const attachmentStorageView = (v?: string | null) => view(attachmentStorageMap, v)
export const attachmentParseView = (v?: string | null) => view(attachmentParseMap, v)
export const analysisStageView = (v?: string | null) => view(analysisStageMap, v)
export const riskLevelView = (v?: string | null) => view(riskLevelMap, v)
export const reviewStatusView = (v?: string | null) => view(reviewStatusMap, v)
export const reportStatusView = (v?: string | null) => view(reportStatusMap, v)
export const sessionStatusView = (v?: string | null) => view(sessionStatusMap, v)
export const configStatusView = (v?: string | null) => view(configStatusMap, v)
export const auditResultView = (v?: string | null) => view(auditResultMap, v)
