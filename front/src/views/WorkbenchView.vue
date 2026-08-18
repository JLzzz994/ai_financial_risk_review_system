<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listApprovalTasks } from '@/api/approval-tasks'
import { listDocuments } from '@/api/documents'
import { listDocumentFindings } from '@/api/analysis-tasks'
import { safeErrorMessage } from '@/api/client'
import type { ApprovalTask, DocumentSummary, RiskFinding } from '@/types/domain'
import { documentStatusView } from '@/types/status'
import { formatDate } from '@/utils/format'
import AmountText from '@/components/AmountText.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageShell from '@/components/PageShell.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import DataTable from '@/components/DataTable.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const tasks = ref<ApprovalTask[]>([])
const documents = ref<DocumentSummary[]>([])
const findings = ref<RiskFinding[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)

const canCreate = computed(() => auth.roles.includes('applicant'))

const metrics = computed(() => {
  const weekStart = Date.now() - 7 * 24 * 3600 * 1000
  const approvedThisWeek = documents.value.filter(
    (d) => d.document_status === 'approved' && Date.parse(d.updated_at) >= weekStart,
  ).length
  const parsing = documents.value.filter((d) => ['pending_review', 'reviewing'].includes(d.document_status)).length
  const manualReview = findings.value.filter((f) => f.review_status === 'manual_review' || f.review_status === 'pending').length
  return {
    pendingTasks: tasks.value.filter((t) => t.task_status === 'pending').length,
    parsing,
    approvedThisWeek,
    manualReview,
  }
})

const riskOverview = computed(() => {
  const count = (level: string) => findings.value.filter((f) => f.risk_level === level).length
  return [
    { level: 'high', label: '高风险', note: '证据充分，提交审批前建议处理', count: count('high') },
    { level: 'medium', label: '中风险', note: '需要人工确认差异原因', count: count('medium') },
    { level: 'low', label: '低风险', note: '补充说明后可放行', count: count('low') },
  ]
})

const featuredDocumentId = computed(() => findings.value[0] ? 'd-20260815' : documents.value[0]?.document_id ?? '')

const taskColumns = [
  { key: 'document_no', title: '单据编号', width: '16%' },
  { key: 'applicant_name', title: '申请人', width: '10%' },
  { key: 'applicant_department', title: '部门', width: '12%' },
  { key: 'node_name', title: '当前节点', width: '12%' },
  { key: 'total_amount', title: '金额', align: 'right' as const, width: '12%' },
  { key: 'overall_risk_level', title: '风险', width: '10%' },
  { key: 'created_at', title: '分配时间', width: '13%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [taskPage, documentPage, findingList] = await Promise.all([
      listApprovalTasks({ task_status: 'pending', page_size: 50 }),
      listDocuments({ page_size: 50 }),
      listDocumentFindings(featuredDocumentId.value || 'd-20260815').catch(() => [] as RiskFinding[]),
    ])
    tasks.value = taskPage.items
    documents.value = documentPage.items
    findings.value = findingList
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function statusOf(row: Record<string, unknown>): string {
  const task = row as unknown as ApprovalTask
  return documentStatusView(documents.value.find((d) => d.document_id === task.document_id)?.document_status).label
}

onMounted(load)
</script>

<template>
  <PageShell
    title="审核工作台"
    description="待办任务、风险概览与待人工复核事项一览"
  >
    <template #actions>
      <RouterLink
        v-if="canCreate"
        to="/documents"
        class="btn btn-primary"
      >
        新建费用报销单
      </RouterLink>
    </template>

    <section
      class="grid grid-4 metric-area"
      aria-label="关键指标"
    >
      <MetricCard
        label="待我审批"
        :value="metrics.pendingTasks"
        tone="primary"
        hint="分配给当前用户的待处理任务"
      />
      <MetricCard
        label="解析中"
        :value="metrics.parsing"
        hint="单据正在解析或复核中"
      />
      <MetricCard
        label="本周已通过"
        :value="metrics.approvedThisWeek"
        tone="risk-low"
      />
      <MetricCard
        label="待人工复核"
        :value="metrics.manualReview"
        tone="risk-medium"
        hint="证据不足或待确认的风险项"
      />
    </section>

    <section class="card workbench-main">
      <div class="card-title">
        <span>待处理单据</span>
        <div class="row">
          <RouterLink
            to="/approval-tasks"
            class="btn-link"
          >
            查看全部
          </RouterLink>
        </div>
      </div>
      <DataTable
        :columns="taskColumns"
        :rows="tasks as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        :error="loadError"
        row-key="task_id"
        empty-text="暂无待处理任务"
        @retry="load"
      >
        <template #cell-document_no="{ row }">
          <RouterLink
            :to="`/documents/${row.document_id}`"
            class="doc-link"
          >
            {{ row.document_no }}
          </RouterLink>
          <div class="doc-status">
            {{ statusOf(row) }}
          </div>
        </template>
        <template #cell-total_amount="{ row }">
          <AmountText
            :value="String(row.total_amount)"
            :currency="String(row.currency)"
            strong
          />
        </template>
        <template #cell-overall_risk_level="{ row }">
          <RiskLevelTag :level="String(row.overall_risk_level)" />
        </template>
        <template #cell-created_at="{ row }">
          <span class="muted">{{ formatDate(String(row.created_at)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <RouterLink
            :to="`/approval-tasks?focus=${row.task_id}`"
            class="btn-link"
          >
            处理审批
          </RouterLink>
          <RouterLink
            :to="`/documents/${row.document_id}/risk-analysis`"
            class="btn-link"
          >
            风险分析
          </RouterLink>
        </template>
      </DataTable>
    </section>

    <section class="card risk-overview">
      <div class="card-title">
        <span>风险概览</span>
        <div class="row">
          <RouterLink
            v-if="featuredDocumentId"
            :to="`/documents/${featuredDocumentId}/risk-analysis`"
            class="btn-link"
          >
            查看风险分析
          </RouterLink>
        </div>
      </div>
      <div class="risk-rows">
        <div
          v-for="item in riskOverview"
          :key="item.level"
          class="risk-row"
          :class="`risk-row-${item.level}`"
        >
          <span class="risk-dot" />
          <div class="risk-row-text">
            <span class="risk-row-label">{{ item.label }}</span>
            <span class="risk-row-note">{{ item.note }}</span>
          </div>
          <span class="risk-row-count">{{ item.count }}</span>
        </div>
      </div>
      <p class="risk-hint">
        风险提示：共 {{ findings.length }} 条风险，其中 {{ findings.filter((f) => f.evidence.length === 0).length }} 条证据不足需人工确认；AI 结果仅为辅助参考。
      </p>
    </section>
  </PageShell>
</template>

<style scoped>
.metric-area {
  margin-bottom: 16px;
}

.risk-overview {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.risk-rows {
  display: flex;
  flex-direction: column;
}

.risk-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 4px;
  border-bottom: 1px solid var(--color-border);
}

.risk-row:last-of-type {
  border-bottom: none;
}

.risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  /* 圆点严格限制在容器边界内（SPEC 19 §2） */
  margin: 0 2px;
}

.risk-row-high .risk-dot {
  background: var(--risk-high);
}

.risk-row-medium .risk-dot {
  background: var(--risk-medium);
}

.risk-row-low .risk-dot {
  background: var(--risk-low);
}

.risk-row-text {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.risk-row-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-deep);
  white-space: nowrap;
}

.risk-row-note {
  font-size: 12px;
  color: #5b6b83;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-row-count {
  font-size: 24px;
  line-height: 32px;
  font-weight: 600;
  color: var(--color-brand-deep);
  font-variant-numeric: tabular-nums;
}

.risk-hint {
  margin-top: 14px;
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-secondary);
  background: var(--color-panel);
  border-radius: var(--radius-input);
  padding: 10px 12px;
}

.doc-link {
  display: inline-block;
}

.doc-status {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-top: 2px;
}
</style>
