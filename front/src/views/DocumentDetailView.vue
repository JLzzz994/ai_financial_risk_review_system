<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAnalysisTask, listDocumentFindings, subscribeTaskEvents, type TaskEventFrame, type TaskEventState } from '@/api/analysis-tasks'
import { getApprovalHistory } from '@/api/approval-tasks'
import { getDocument, listVersions } from '@/api/documents'
import { listReportVersions } from '@/api/reports'
import { safeErrorMessage } from '@/api/client'
import { listApprovalTasks } from '@/api/approval-tasks'
import { useAuthStore } from '@/stores/auth'
import type {
  ApprovalHistoryNode,
  ApprovalTask,
  AnalysisTask,
  DocumentDetail,
  DocumentVersionInfo,
  RiskFinding,
} from '@/types/domain'
import {
  approvalTaskStatusView,
  approvalDecisionView,
  documentStatusView,
  reportStatusView,
  reviewStatusView,
} from '@/types/status'
import { formatDateTime } from '@/utils/format'
import AmountText from '@/components/AmountText.vue'
import ApiHint from '@/components/ApiHint.vue'
import ApprovalDecisionDialog from '@/components/ApprovalDecisionDialog.vue'
import AttachmentUploader from '@/components/AttachmentUploader.vue'
import EvidenceDrawer from '@/components/EvidenceDrawer.vue'
import PageShell from '@/components/PageShell.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import ErrorState from '@/components/ErrorState.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const documentId = computed(() => String(route.params.id))

const document = ref<DocumentDetail | null>(null)
const versions = ref<DocumentVersionInfo[]>([])
const findings = ref<RiskFinding[]>([])
const history = ref<ApprovalHistoryNode[]>([])
const reports = ref<Array<{ document_version_id: string; version_no: number; report_status: string; overall_risk_level?: string }>>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

const activeTask = ref<AnalysisTask | null>(null)
const myTask = ref<ApprovalTask | null>(null)
const streamState = ref<TaskEventState>('closed')
let subscription: { close: () => void } | null = null

const evidenceFinding = ref<RiskFinding | null>(null)
const evidenceOpen = ref(false)
const decisionOpen = ref(false)
const decisionPreset = ref<'approve' | 'return' | 'reject' | null>(null)

const isApplicant = computed(() => document.value?.applicant_id === auth.principal?.user_id)
const canDecide = computed(
  () =>
    auth.roles.includes('approver') &&
    myTask.value !== null &&
    myTask.value.task_status === 'pending' &&
    myTask.value.assignee_id === auth.principal?.user_id,
)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [doc, versionList, findingList, historyList, reportList] = await Promise.all([
      getDocument(documentId.value),
      listVersions(documentId.value),
      listDocumentFindings(documentId.value),
      getApprovalHistory(documentId.value).catch(() => [] as ApprovalHistoryNode[]),
      listReportVersions(documentId.value).catch(() => []),
    ])
    document.value = doc
    versions.value = versionList
    findings.value = findingList
    history.value = historyList
    reports.value = reportList
    if (auth.roles.includes('approver')) {
      const taskPage = await listApprovalTasks({ page_size: 50 }).catch(() => null)
      myTask.value =
        taskPage?.items.find((t) => t.document_id === documentId.value && t.task_status === 'pending') ?? null
    }
    // URL 中带分析任务时订阅进度（提交后跳转场景）
    const taskId = typeof route.query.task === 'string' ? route.query.task : doc.analysis_task_id
    if (taskId) await watchTask(taskId)
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function watchTask(taskId: string): Promise<void> {
  subscription?.close()
  try {
    activeTask.value = await getAnalysisTask(taskId)
  } catch {
    activeTask.value = null
    return
  }
  if (activeTask.value.stage === 'succeeded' || activeTask.value.stage === 'failed') {
    streamState.value = 'closed'
    return
  }
  subscribe()
}

function subscribe(): void {
  if (!activeTask.value) return
  subscription = subscribeTaskEvents(
    activeTask.value.task_id,
    (frame: TaskEventFrame) => {
      if (frame.type === 'progress' && frame.step) {
        activeTask.value = { ...(activeTask.value as AnalysisTask), stage: frame.step }
      } else if (frame.type === 'result') {
        activeTask.value = { ...(activeTask.value as AnalysisTask), stage: 'succeeded', progress: 100 }
        void refreshAfterAnalysis()
      } else if (frame.type === 'error') {
        activeTask.value = { ...(activeTask.value as AnalysisTask), stage: 'failed' }
      }
    },
    (state) => {
      streamState.value = state
    },
  )
}

async function refreshAfterAnalysis(): Promise<void> {
  try {
    const [findingList, doc] = await Promise.all([
      listDocumentFindings(documentId.value),
      getDocument(documentId.value),
    ])
    findings.value = findingList
    document.value = doc
  } catch {
    // 静默：主内容已加载
  }
}

function openEvidence(finding: RiskFinding): void {
  evidenceFinding.value = finding
  evidenceOpen.value = true
}

function openDecision(preset?: 'approve' | 'return' | 'reject'): void {
  decisionPreset.value = preset ?? null
  decisionOpen.value = true
}

function goRiskAnalysis(): void {
  void router.push(`/documents/${documentId.value}/risk-analysis`)
}

function goAmountComparison(): void {
  void router.push(`/documents/${documentId.value}/amount-comparison`)
}

function goSession(): void {
  const sessionId = document.value?.review_session_id
  if (sessionId) void router.push(`/review-sessions/${sessionId}`)
}

const currentReport = computed(() => reports.value[0] ?? null)

onMounted(load)
onBeforeUnmount(() => subscription?.close())
</script>

<template>
  <PageShell
    :title="document?.document_no ?? '单据详情'"
    description="单据摘要、附件证据、风险复核、版本历史与审批进度"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="GET /api/v1/documents/{document_id}" />
        <StatusBadge
          v-if="document"
          v-bind="documentStatusView(document.document_status)"
        />
        <RiskLevelTag
          v-if="document?.overall_risk_level"
          :level="document.overall_risk_level"
        />
        <button
          v-if="canDecide"
          type="button"
          class="btn btn-secondary"
          @click="openDecision('return')"
        >
          退回
        </button>
        <button
          v-if="canDecide"
          type="button"
          class="btn btn-primary"
          @click="openDecision('approve')"
        >
          审批通过
        </button>
        <RouterLink
          v-else-if="isApplicant && ['draft', 'returned'].includes(document?.document_status ?? '')"
          :to="`/documents/${documentId}/edit`"
          class="btn btn-primary"
        >
          编辑单据
        </RouterLink>
      </div>
    </template>

    <ErrorState
      v-if="loadError && !document"
      :message="loadError"
      @retry="load"
    />

    <template v-if="document">
      <!-- 分析进度（提交后） -->
      <section
        v-if="activeTask"
        class="card"
      >
        <div class="card-title">
          <span>分析进度</span>
          <ApiHint text="GET /api/v1/analysis-tasks/{task_id} · SSE events" />
        </div>
        <TaskProgress
          :task="activeTask"
          :stream-state="streamState"
          @resume="subscribe"
          @retry="watchTask(activeTask!.task_id)"
        />
      </section>

      <!-- 单据摘要 -->
      <section class="card">
        <h2 class="card-title">
          单据摘要
        </h2>
        <dl class="summary-grid">
          <div class="summary-item">
            <dt>单据类型</dt>
            <dd>费用报销单</dd>
          </div>
          <div class="summary-item">
            <dt>费用类别</dt>
            <dd>{{ document.expense_category }}</dd>
          </div>
          <div class="summary-item">
            <dt>报销金额</dt>
            <dd>
              <AmountText
                :value="document.total_amount"
                :currency="document.currency"
                strong
              />
            </dd>
          </div>
          <div class="summary-item">
            <dt>费用发生日期</dt>
            <dd>{{ document.apply_date }}</dd>
          </div>
          <div class="summary-item">
            <dt>所属组织</dt>
            <dd>
              {{ document.applicant_department }}<template v-if="document.budget_department">
                / {{ document.budget_department }}
              </template>
            </dd>
          </div>
          <div class="summary-item">
            <dt>申请人</dt>
            <dd>{{ document.applicant_name }}</dd>
          </div>
          <div class="summary-item">
            <dt>当前版本</dt>
            <dd>v{{ document.current_version || '—' }}</dd>
          </div>
          <div class="summary-item">
            <dt>收款方</dt>
            <dd>{{ document.payee_name ?? '—' }}</dd>
          </div>
          <div class="summary-item summary-item-full">
            <dt>事由</dt>
            <dd>{{ document.reason_text || '—' }}</dd>
          </div>
        </dl>
        <div class="summary-links">
          <button
            type="button"
            class="btn-link"
            @click="goRiskAnalysis"
          >
            查看风险分析
          </button>
          <button
            v-if="auth.roles.includes('approver') || auth.roles.includes('finance')"
            type="button"
            class="btn-link"
            @click="goAmountComparison"
          >
            金额核对
          </button>
          <button
            type="button"
            class="btn-link"
            @click="goSession"
          >
            审核会话
          </button>
        </div>
      </section>

      <div class="detail-columns">
        <div class="detail-main">
          <!-- 附件证据 -->
          <section class="card">
            <div class="card-title">
              <span>附件证据</span>
              <ApiHint text="GET /api/v1/documents/{document_id}/attachments" />
            </div>
            <AttachmentUploader
              :document-id="documentId"
              :readonly="!isApplicant"
              :hint="false"
            />
          </section>

          <!-- 风险复核 -->
          <section class="card">
            <div class="card-title">
              <span>风险复核 <span class="card-title-sub">共 {{ findings.length }} 条</span></span>
              <div class="row">
                <ApiHint text="GET /api/v1/documents/{document_id}/risk-findings" />
                <RouterLink
                  :to="`/documents/${documentId}/risk-analysis`"
                  class="btn-link"
                >
                  进入复核
                </RouterLink>
              </div>
            </div>
            <ul class="finding-list">
              <li
                v-for="finding in findings"
                :key="finding.finding_id"
                class="finding-item"
              >
                <div class="finding-item-head">
                  <RiskLevelTag :level="finding.risk_level" />
                  <span class="finding-item-title">{{ finding.title }}</span>
                  <StatusBadge v-bind="reviewStatusView(finding.review_status)" />
                </div>
                <p class="finding-item-desc">
                  {{ finding.description }}
                </p>
                <div class="finding-item-foot">
                  <span class="finding-item-rule">{{ finding.rule_code }} · {{ finding.rule_name }}</span>
                  <button
                    type="button"
                    class="btn-link"
                    @click="openEvidence(finding)"
                  >
                    {{ finding.evidence.length > 0 ? `证据（${finding.evidence.length}）` : '待人工确认' }}
                  </button>
                </div>
              </li>
            </ul>
          </section>
        </div>

        <div class="detail-side">
          <!-- 版本历史 -->
          <section class="card">
            <div class="card-title">
              <span>版本历史</span>
              <ApiHint text="GET /api/v1/documents/{document_id}/versions" />
            </div>
            <ul class="version-list">
              <li
                v-for="version in versions"
                :key="version.document_version_id"
                class="version-item"
              >
                <span class="version-no">v{{ version.version_no }}</span>
                <span class="version-meta">{{ version.created_by }} · {{ formatDateTime(version.created_at) }}</span>
                <span class="version-desc">{{ version.change_summary ?? (version.trigger === 'submit' ? '首次提交' : '重新提交') }}</span>
                <div class="version-links">
                  <RouterLink
                    :to="`/reports/${version.document_version_id}`"
                    class="btn-link"
                  >
                    查看报告
                  </RouterLink>
                </div>
              </li>
            </ul>
          </section>

          <!-- 审批进度 -->
          <section class="card">
            <div class="card-title">
              <span>审批进度</span>
              <ApiHint text="GET /api/v1/documents/{document_id}/approval-history" />
            </div>
            <ol class="timeline">
              <li
                v-for="node in history"
                :key="node.node_order"
                class="timeline-node"
              >
                <span
                  class="timeline-dot"
                  :class="`timeline-${approvalTaskStatusView(node.task_status).tone}`"
                />
                <div class="timeline-body">
                  <div class="timeline-head">
                    <span class="timeline-title">{{ node.node_name }}</span>
                    <StatusBadge
                      v-bind="approvalTaskStatusView(node.task_status)"
                      :dot="false"
                    />
                  </div>
                  <p class="timeline-meta">
                    {{ node.assignee_name }}
                  </p>
                  <p
                    v-if="node.review_comment"
                    class="timeline-comment"
                  >
                    <template v-if="node.decision">
                      [{{ approvalDecisionView(node.decision).label }}]
                    </template>{{ node.review_comment }}
                  </p>
                  <p
                    v-if="node.processed_at"
                    class="timeline-meta weak"
                  >
                    {{ formatDateTime(node.processed_at) }}
                  </p>
                </div>
              </li>
            </ol>
          </section>

          <!-- 报告 -->
          <section class="card">
            <div class="card-title">
              <span>审核报告</span>
              <ApiHint text="GET /api/v1/review-reports/{document_version_id}" />
            </div>
            <template v-if="currentReport">
              <div class="report-row">
                <span>当前版本报告</span>
                <StatusBadge v-bind="reportStatusView(currentReport.report_status)" />
                <RiskLevelTag :level="currentReport.overall_risk_level" />
              </div>
              <RouterLink
                :to="`/reports/${currentReport.document_version_id}`"
                class="btn btn-secondary btn-sm report-link"
              >
                打开报告中心
              </RouterLink>
            </template>
            <p
              v-else
              class="weak report-empty"
            >
              当前版本尚未生成报告（分析完成后自动生成草稿）。
            </p>
          </section>
        </div>
      </div>
    </template>

    <EvidenceDrawer
      v-model="evidenceOpen"
      :finding="evidenceFinding"
    />
    <ApprovalDecisionDialog
      v-model="decisionOpen"
      :task="myTask"
      :preset="decisionPreset"
      @decided="load"
      @open-risk="goRiskAnalysis"
    />
  </PageShell>
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px 20px;
  margin: 0;
}

.summary-item dt {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-bottom: 5px;
}

.summary-item dd {
  margin: 0;
  font-size: 14px;
  line-height: 20px;
  color: var(--color-text);
  word-break: break-all;
}

.summary-item-full {
  grid-column: 1 / -1;
}

.summary-links {
  display: flex;
  gap: 14px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--color-border);
}

.detail-columns {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  margin-top: 16px;
  align-items: start;
}

.detail-main,
.detail-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.detail-main :deep(.card + .card),
.detail-side :deep(.card + .card) {
  margin-top: 0;
}

.finding-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.finding-item {
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border);
}

.finding-item:last-child {
  border-bottom: none;
}

.finding-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.finding-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.finding-item-desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
}

.finding-item-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
}

.finding-item-rule {
  font-size: 12px;
  color: var(--color-text-weak);
}

.version-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.version-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}

.version-item:last-child {
  border-bottom: none;
}

.version-no {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.version-meta {
  font-size: 12px;
  color: var(--color-text-weak);
  text-align: right;
}

.version-desc {
  grid-column: 1 / -1;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.version-links {
  grid-column: 1 / -1;
}

.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}

.timeline-node {
  position: relative;
  padding: 0 0 18px 22px;
}

.timeline-node:last-child {
  padding-bottom: 4px;
}

.timeline-node::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 14px;
  bottom: 0;
  width: 1px;
  background: var(--color-border);
}

.timeline-node:last-child::before {
  display: none;
}

.timeline-dot {
  position: absolute;
  left: 0;
  top: 4px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.timeline-blue {
  background: var(--status-blue);
}

.timeline-green {
  background: var(--risk-low);
}

.timeline-orange {
  background: var(--risk-medium);
}

.timeline-red {
  background: var(--risk-high);
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.timeline-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}

.timeline-meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-weak);
}

.timeline-comment {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-secondary);
  background: var(--color-panel);
  border-radius: var(--radius-input);
  padding: 8px 10px;
}

.report-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--color-text);
}

.report-link {
  margin-top: 12px;
}

.report-empty {
  font-size: 13px;
}

@media (max-width: 1100px) {
  .detail-columns {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
