<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createAnalysisTask,
  getAnalysisTask,
  listDocumentFindings,
  patchFindingReviewStatus,
  subscribeTaskEvents,
  type TaskEventFrame,
  type TaskEventState,
} from '@/api/analysis-tasks'
import { getDocument } from '@/api/documents'
import { ApiError, handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { AnalysisTask, DocumentDetail, RiskFinding } from '@/types/domain'
import { reviewStatusView } from '@/types/status'
import ApiHint from '@/components/ApiHint.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorState from '@/components/ErrorState.vue'
import EvidenceDrawer from '@/components/EvidenceDrawer.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageShell from '@/components/PageShell.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskProgress from '@/components/TaskProgress.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const documentId = computed(() => String(route.params.id))

const document = ref<DocumentDetail | null>(null)
const findings = ref<RiskFinding[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

const task = ref<AnalysisTask | null>(null)
const streamState = ref<TaskEventState>('closed')
let subscription: { close: () => void } | null = null

const evidenceFinding = ref<RiskFinding | null>(null)
const evidenceOpen = ref(false)

const reviewTarget = ref<RiskFinding | null>(null)
const reviewAction = ref<'confirmed' | 'dismissed'>('confirmed')
const reviewOpen = ref(false)
const reviewing = ref(false)

const canReview = computed(() => auth.roles.includes('approver') || auth.roles.includes('finance'))

const levelFilter = ref<'' | 'high' | 'medium' | 'low'>('')

const counts = computed(() => ({
  high: findings.value.filter((f) => f.risk_level === 'high').length,
  medium: findings.value.filter((f) => f.risk_level === 'medium').length,
  low: findings.value.filter((f) => f.risk_level === 'low').length,
  pendingReview: findings.value.filter((f) => ['pending', 'manual_review'].includes(f.review_status)).length,
}))

const visibleFindings = computed(() =>
  levelFilter.value ? findings.value.filter((f) => f.risk_level === levelFilter.value) : findings.value,
)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [doc, findingList] = await Promise.all([
      getDocument(documentId.value),
      listDocumentFindings(documentId.value),
    ])
    document.value = doc
    findings.value = findingList
    if (doc.analysis_task_id) await watchTask(doc.analysis_task_id)
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function watchTask(taskId: string): Promise<void> {
  subscription?.close()
  try {
    task.value = await getAnalysisTask(taskId)
  } catch {
    task.value = null
    return
  }
  if (['succeeded', 'failed'].includes(task.value.stage)) {
    streamState.value = 'closed'
    return
  }
  subscription = subscribeTaskEvents(
    taskId,
    (frame: TaskEventFrame) => {
      if (!task.value) return
      if (frame.type === 'progress' && frame.step) {
        task.value = { ...task.value, stage: frame.step }
      } else if (frame.type === 'result') {
        task.value = { ...task.value, stage: 'succeeded', progress: 100 }
        void refreshFindings()
      } else if (frame.type === 'error') {
        task.value = { ...task.value, stage: 'failed' }
      }
    },
    (state) => {
      streamState.value = state
    },
  )
}

async function refreshFindings(): Promise<void> {
  try {
    findings.value = await listDocumentFindings(documentId.value)
  } catch {
    // 静默
  }
}

async function rerunAnalysis(): Promise<void> {
  try {
    const newTask = await createAnalysisTask(documentId.value, crypto.randomUUID())
    app.push('info', '已发起重新分析')
    await watchTask(newTask.task_id)
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      app.push('warning', '已有分析任务进行中，不重复创建')
      return
    }
    handleApiError(error)
  }
}

function openEvidence(finding: RiskFinding): void {
  evidenceFinding.value = finding
  evidenceOpen.value = true
}

function askReview(finding: RiskFinding, action: 'confirmed' | 'dismissed'): void {
  reviewTarget.value = finding
  reviewAction.value = action
  reviewOpen.value = true
}

async function confirmReview(reason: string): Promise<void> {
  if (!reviewTarget.value) return
  reviewing.value = true
  try {
    await patchFindingReviewStatus(reviewTarget.value.finding_id, {
      review_status: reviewAction.value,
      review_comment: reason,
    })
    app.push('success', reviewAction.value === 'confirmed' ? '已确认该风险' : '已排除该风险')
    reviewOpen.value = false
    await refreshFindings()
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    reviewing.value = false
  }
}

function backToDetail(): void {
  void router.push(`/documents/${documentId.value}`)
}

onMounted(load)
onBeforeUnmount(() => subscription?.close())
</script>

<template>
  <PageShell
    :title="`风险分析 · ${document?.document_no ?? ''}`"
    description="规则命中、证据定位与人工复核"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="GET /api/v1/documents/{document_id}/risk-findings" />
        <button
          type="button"
          class="btn btn-secondary"
          @click="backToDetail"
        >
          返回详情
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="task !== null && !['succeeded', 'failed'].includes(task.stage)"
          @click="rerunAnalysis"
        >
          重新分析
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <template v-else>
      <section
        v-if="task && !['succeeded', 'failed'].includes(task.stage)"
        class="card"
      >
        <div class="card-title">
          <span>分析进行中</span>
          <ApiHint text="SSE GET /api/v1/analysis-tasks/{task_id}/events" />
        </div>
        <TaskProgress
          :task="task"
          :stream-state="streamState"
          @resume="watchTask(task!.task_id)"
          @retry="watchTask(task!.task_id)"
        />
      </section>

      <section
        class="grid grid-4"
        aria-label="风险概览"
      >
        <MetricCard
          label="高风险"
          :value="counts.high"
          tone="risk-high"
          hint="证据充分，建议处理后再审批"
        />
        <MetricCard
          label="中风险"
          :value="counts.medium"
          tone="risk-medium"
          hint="需要人工确认"
        />
        <MetricCard
          label="低风险"
          :value="counts.low"
          tone="risk-low"
          hint="补充说明后可放行"
        />
        <MetricCard
          label="待人工复核"
          :value="counts.pendingReview"
          tone="primary"
        />
      </section>

      <section class="card">
        <div class="card-title">
          <span>风险项（{{ visibleFindings.length }}）</span>
          <div class="row level-filter">
            <button
              v-for="option in [
                { value: '', label: '全部' },
                { value: 'high', label: '高风险' },
                { value: 'medium', label: '中风险' },
                { value: 'low', label: '低风险' },
              ]"
              :key="option.value"
              type="button"
              class="btn btn-sm"
              :class="levelFilter === option.value ? 'btn-primary' : 'btn-secondary'"
              @click="levelFilter = option.value as typeof levelFilter"
            >
              {{ option.label }}
            </button>
          </div>
        </div>

        <p
          v-if="loading"
          class="muted"
        >
          风险项加载中…
        </p>
        <p
          v-else-if="visibleFindings.length === 0"
          class="muted empty-findings"
        >
          当前筛选条件下没有风险项。
        </p>

        <ul
          v-else
          class="finding-list"
        >
          <li
            v-for="finding in visibleFindings"
            :key="finding.finding_id"
            class="finding-card"
          >
            <div class="finding-head">
              <div class="row finding-title-row">
                <RiskLevelTag :level="finding.risk_level" />
                <span class="finding-title">{{ finding.title }}</span>
              </div>
              <StatusBadge v-bind="reviewStatusView(finding.review_status)" />
            </div>
            <p class="finding-desc">
              {{ finding.description }}
            </p>
            <div
              v-if="finding.suggestion"
              class="finding-suggestion"
            >
              <span class="finding-suggestion-tag">AI 建议</span>
              <span>{{ finding.suggestion }}</span>
            </div>
            <dl class="finding-meta">
              <div><dt>命中规则</dt><dd>{{ finding.rule_code }} · {{ finding.rule_name }}</dd></div>
              <div><dt>证据</dt><dd>{{ finding.evidence.length > 0 ? `${finding.evidence.length} 条（附件 / 页码 / 原文）` : '证据不足' }}</dd></div>
              <div v-if="finding.reviewed_by">
                <dt>复核人</dt><dd>{{ finding.reviewed_by }}</dd>
              </div>
              <div v-if="finding.review_comment">
                <dt>复核意见</dt><dd>{{ finding.review_comment }}</dd>
              </div>
            </dl>
            <div class="finding-actions">
              <button
                type="button"
                class="btn btn-secondary btn-sm"
                @click="openEvidence(finding)"
              >
                {{ finding.evidence.length > 0 ? '查看证据' : '待人工确认' }}
              </button>
              <template v-if="canReview && ['pending', 'manual_review'].includes(finding.review_status)">
                <button
                  type="button"
                  class="btn btn-danger btn-sm"
                  @click="askReview(finding, 'confirmed')"
                >
                  确认风险
                </button>
                <button
                  type="button"
                  class="btn btn-secondary btn-sm"
                  @click="askReview(finding, 'dismissed')"
                >
                  排除风险
                </button>
              </template>
            </div>
          </li>
        </ul>
        <p class="review-note">
          复核说明：确认 / 排除必须填写意见并写入审计日志；证据不足的风险只能保持「待人工确认」，不能显示为已确认风险。
        </p>
      </section>
    </template>

    <EvidenceDrawer
      v-model="evidenceOpen"
      :finding="evidenceFinding"
    />

    <ConfirmDialog
      v-model="reviewOpen"
      :title="reviewAction === 'confirmed' ? '确认风险' : '排除风险'"
      :message="`对「${reviewTarget?.title ?? ''}」提交${reviewAction === 'confirmed' ? '确认' : '排除'}意见？该操作将写入审计日志。`"
      :confirm-text="reviewAction === 'confirmed' ? '确认风险' : '排除风险'"
      :tone="reviewAction === 'confirmed' ? 'danger' : 'primary'"
      require-reason
      reason-label="复核意见"
      @confirm="confirmReview"
    />
  </PageShell>
</template>

<style scoped>
.finding-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-findings {
  padding: 20px 0;
}

.finding-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-btn);
  padding: 16px;
}

.finding-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.finding-title-row {
  flex-wrap: wrap;
}

.finding-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.finding-desc {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 21px;
  color: var(--color-text-secondary);
}

.finding-suggestion {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  align-items: baseline;
  background: var(--color-selected);
  border-radius: var(--radius-input);
  padding: 8px 12px;
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text);
}

.finding-suggestion-tag {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--color-primary);
}

.finding-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin: 12px 0 0;
}

.finding-meta dt {
  font-size: 12px;
  color: var(--color-text-weak);
  display: inline;
}

.finding-meta dd {
  margin: 0 0 0 6px;
  display: inline;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.finding-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.review-note {
  margin-top: 16px;
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-weak);
}

.level-filter {
  gap: 8px;
}
</style>
