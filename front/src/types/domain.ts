/**
 * 领域类型 —— 字段名与 04-SPEC 各模块接口表及 05-数据对象文档保持一致。
 * 金额一律为字符串（后端 Decimal 序列化），前端禁止 float 运算。
 */

export type RoleCode = 'applicant' | 'approver' | 'finance' | 'admin'

export type Money = string

export interface AuthToken {
  access_token: string
  token_type: string
  expires_in?: number
}

export interface Principal {
  user_id: string
  username: string
  display_name?: string
  department?: string
  roles: RoleCode[]
  org_scope?: string[]
}

export interface PageQuery {
  page?: number
  page_size?: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/* ---------------- 单据 ---------------- */

export type DocumentType =
  | 'public_payment'
  | 'prepayment'
  | 'batch_payment'
  | 'expense_reimbursement'
  | 'travel_reimbursement'

/** 五类单据的专属载荷；金额保持字符串，避免前端浮点精度丢失。 */
export interface BaseDocumentPayload {
  document_type: DocumentType
  currency: 'CNY'
}

export interface PaymentDocumentPayload extends BaseDocumentPayload {
  document_type: 'public_payment' | 'prepayment'
  contract_no: string
  supplier_name: string
  payment_ratio: string
  payment_terms: string
  planned_payment_date: string
}

export interface BatchPaymentDetail {
  payee_name: string
  amount: Money
}

export interface BatchPaymentPayload extends BaseDocumentPayload {
  document_type: 'batch_payment'
  payment_details: BatchPaymentDetail[]
  total_amount: Money
  payment_count: number
}

export interface ExpenseReimbursementPayload extends BaseDocumentPayload {
  document_type: 'expense_reimbursement'
  expense_details: Array<{
    expense_item: string
    consumption_date: string
    consumption_location: string
    expense_category: string
    reimbursement_amount: Money
    currency: 'CNY'
  }>
}

export interface TravelReimbursementPayload extends BaseDocumentPayload {
  document_type: 'travel_reimbursement'
  travel_location: string
  travel_start_date: string
  travel_end_date: string
  transportation_amount: Money
  accommodation_amount: Money
  meal_amount: Money
  allowance_amount: Money
}

export type DocumentPayload =
  | PaymentDocumentPayload
  | BatchPaymentPayload
  | ExpenseReimbursementPayload
  | TravelReimbursementPayload

export const documentTypeLabels: Record<DocumentType, string> = {
  public_payment: '对公付款单',
  prepayment: '预付款单',
  batch_payment: '批量付款单',
  expense_reimbursement: '费用报销单',
  travel_reimbursement: '差旅报销单',
}

export interface DocumentSummary {
  document_id: string
  document_no: string
  document_type: DocumentType
  expense_category: string
  applicant_id: string
  applicant_name: string
  applicant_department: string
  budget_department?: string
  total_amount: Money
  currency: string
  document_status: string
  current_version: number
  overall_risk_level?: string
  pending_finding_count?: number
  created_at: string
  updated_at: string
}

export interface LineItem {
  item_id: string
  expense_item: string
  expense_date: string
  amount: Money
  currency: string
  invoice_no?: string
  remark?: string
}

export interface DocumentDetail extends DocumentSummary {
  apply_date: string
  payee_name?: string
  payee_account?: string
  payee_bank?: string
  reason_text: string
  line_items: LineItem[]
  analysis_task_id?: string
  review_session_id?: string
  /** 老版本接口可能不返回该字段，页面需展示明确空状态。 */
  document_payload?: DocumentPayload | null
}

export interface DocumentVersionInfo {
  document_version_id: string
  version_no: number
  created_by: string
  created_at: string
  trigger: 'submit' | 'resubmit'
  change_summary?: string
  finding_count: number
  overall_risk_level?: string
}

/* ---------------- 附件 ---------------- */

export interface Attachment {
  attachment_id: string
  file_name: string
  file_size: number
  mime_type: string
  storage_status: string
  parse_status: string
  required_kind?: string
  uploaded_by: string
  uploaded_at: string
}

/* ---------------- 风险与证据 ---------------- */

export interface Evidence {
  evidence_id: string
  attachment_id?: string
  attachment_name?: string
  page_no?: number
  position?: string
  snippet: string
  field_path?: string
  confidence: number
  rule_version?: string
  analyzed_at?: string
}

export interface RiskFinding {
  finding_id: string
  document_version_id: string
  rule_code: string
  rule_name: string
  risk_level: string
  title: string
  description: string
  suggestion?: string
  evidence: Evidence[]
  review_status: string
  reviewed_by?: string
  reviewed_at?: string
  review_comment?: string
}

/* ---------------- 分析任务 ---------------- */

export interface AnalysisTask {
  task_id: string
  document_id: string
  document_version_id: string
  stage: string
  progress?: number
  retry_count: number
  error_message?: string
  manual_takeover?: boolean
  started_at: string
  finished_at?: string
}

/* ---------------- 审批 ---------------- */

export interface ApprovalTask {
  task_id: string
  document_id: string
  document_no: string
  document_type: DocumentType
  node_id: string
  node_name: string
  node_order: number
  assignee_id: string
  assignee_name: string
  task_status: string
  decision?: string
  review_comment?: string
  total_amount: Money
  currency: string
  overall_risk_level?: string
  pending_finding_count: number
  applicant_name: string
  applicant_department: string
  created_at: string
  processed_at?: string
}

export interface ApprovalHistoryNode {
  node_order: number
  node_name: string
  assignee_name: string
  task_status: string
  decision?: string
  review_comment?: string
  processed_at?: string
}

/* ---------------- 审核会话 ---------------- */

export interface SessionSlot {
  name: string
  label: string
  value: string
  confirmed: boolean
}

export interface SessionMessage {
  message_id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  created_at: string
}

export interface ReviewSession {
  session_id: string
  document_id: string
  document_no?: string
  session_status: string
  slots: SessionSlot[]
  analysis_task_id?: string
  created_at: string
}

/* ---------------- 报告 ---------------- */

export interface ReportSection {
  heading: string
  items: string[]
}

export interface ReviewReport {
  report_id: string
  document_id: string
  document_no: string
  document_version_id: string
  version_no: number
  report_status: string
  overall_risk_level?: string
  rule_version: string
  generated_at?: string
  content: {
    summary: string
    sections: ReportSection[]
  }
  export_task_id?: string
}

/* ---------------- 配置：规则 / 流程 ---------------- */

export interface RuleItem {
  rule_id: string
  rule_code: string
  rule_name: string
  rule_type: 'amount' | 'duplicate' | 'completeness' | 'supplier' | 'behavior'
  params: Record<string, string>
  rule_version: string
  status: string
  hit_count_30d: number
  updated_at: string
}

export interface MarketPriceItem {
  id: string
  category: string
  item_name: string
  unit: string
  reference_price: Money
  source: string
  effective_from: string
}

export interface SupplierRuleItem {
  id: string
  supplier_code: string
  supplier_name: string
  rule_name: string
  threshold: Money
  enabled: boolean
}

export interface WorkflowNode {
  node_id: string
  order: number
  name: string
  approver_role: string
  approver_names: string
  sla_hours?: number
}

export interface WorkflowTemplate {
  workflow_id: string
  name: string
  version: number
  match_condition: string
  approval_mode: 'sequential'
  status: string
  nodes: WorkflowNode[]
  published_at?: string
  updated_at: string
}

/* ---------------- 供应商风险 ---------------- */

export interface SupplierAnomaly {
  occurred_at: string
  document_no: string
  type: string
  description: string
}

export interface SupplierRisk {
  supplier_id: string
  supplier_code: string
  supplier_name: string
  risk_status: string
  tags: string[]
  blacklisted: boolean
  blacklist_reason?: string
  payment_count: number
  total_paid: Money
  last_payment_at?: string
  anomalies: SupplierAnomaly[]
}

/* ---------------- 金额核对 ---------------- */

export interface AmountRow {
  row_id: string
  source: string
  ref_no: string
  amount: Money
  difference: Money
  result: 'match' | 'mismatch' | 'missing'
  note?: string
}

export interface AmountComparison {
  document_id: string
  document_no: string
  currency: string
  document_total: Money
  line_item_total: Money
  invoice_total: Money
  contract_total: Money
  payment_total: Money
  invoice_rows: AmountRow[]
  contract_rows: AmountRow[]
  payment_rows: AmountRow[]
}

/* ---------------- 审计 ---------------- */

export interface AuditLog {
  log_id: string
  occurred_at: string
  actor_id?: string
  actor_name: string
  action: string
  resource_type: string
  resource_id?: string
  resource_no?: string
  result: string
  request_id: string
  detail?: string
}
