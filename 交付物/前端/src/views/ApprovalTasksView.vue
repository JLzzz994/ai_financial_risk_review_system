<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listApprovalTasks } from '@/api/approval-tasks'
import { safeErrorMessage } from '@/api/client'
import type { ApprovalTask } from '@/types/domain'
import { approvalTaskStatusMap, approvalTaskStatusView } from '@/types/status'
import { formatDate } from '@/utils/format'
import AmountText from '@/components/AmountText.vue'
import ApprovalDecisionDialog from '@/components/ApprovalDecisionDialog.vue'
import DataTable from '@/components/DataTable.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageShell from '@/components/PageShell.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const route = useRoute()

const rows = ref<ApprovalTask[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref<string | null>(null)
const page = ref(1)
const pageSize = 50

const filters = reactive({ task_status: '', keyword: '' })

const decisionOpen = ref(false)
const activeTask = ref<ApprovalTask | null>(null)

const statusOptions = Object.entries(approvalTaskStatusMap).map(([value, meta]) => ({ value, label: meta.label }))

const metrics = computed(() => ({
  pending: rows.value.filter((t) => t.task_status === 'pending').length,
  highRisk: rows.value.filter((t) => t.task_status === 'pending' && t.overall_risk_level === 'high').length,
  processed: rows.value.filter((t) => t.task_status !== 'pending').length,
}))

const columns = [
  { key: 'document_no', title: '单据编号', width: '16%' },
  { key: 'applicant_name', title: '申请人', width: '9%' },
  { key: 'applicant_department', title: '部门', width: '11%' },
  { key: 'node_name', title: '审批节点', width: '12%' },
  { key: 'total_amount', title: '金额', align: 'right' as const, width: '11%' },
  { key: 'overall_risk_level', title: '风险', width: '9%' },
  { key: 'task_status', title: '状态', width: '9%' },
  { key: 'created_at', title: '分配时间', width: '11%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const result = await listApprovalTasks({ ...filters, page: page.value, page_size: pageSize })
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function onFilterChange(): void {
  page.value = 1
  void load()
}

function openDecision(task: ApprovalTask): void {
  activeTask.value = task
  decisionOpen.value = true
}

/** URL 带 focus=task_id 时自动打开审批弹窗（工作台跳转） */
function handleFocus(): void {
  const focusId = typeof route.query.focus === 'string' ? route.query.focus : ''
  if (!focusId) return
  const task = rows.value.find((t) => t.task_id === focusId)
  if (task) openDecision(task)
}

onMounted(async () => {
  await load()
  handleFocus()
})
</script>

<template>
  <PageShell
    title="审批任务"
    description="本人名下的顺序审批任务：通过、退回与驳回"
  >
    <section
      class="grid grid-3"
      aria-label="状态摘要"
    >
      <MetricCard
        label="待处理"
        :value="metrics.pending"
        tone="primary"
      />
      <MetricCard
        label="高风险待审"
        :value="metrics.highRisk"
        tone="risk-high"
      />
      <MetricCard
        label="已处理"
        :value="metrics.processed"
        tone="risk-low"
      />
    </section>

    <div class="card">
      <div class="filter-bar">
        <select
          v-model="filters.task_status"
          class="select"
          aria-label="任务状态"
          @change="onFilterChange"
        >
          <option value="">
            全部状态
          </option>
          <option
            v-for="option in statusOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <input
          v-model="filters.keyword"
          type="search"
          class="input filter-keyword"
          placeholder="搜索单据编号"
          aria-label="搜索"
          @keyup.enter="onFilterChange"
        >
        <button
          type="button"
          class="btn btn-secondary"
          @click="onFilterChange"
        >
          查询
        </button>
      </div>

      <DataTable
        :columns="columns"
        :rows="rows as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        :error="loadError"
        row-key="task_id"
        empty-text="暂无审批任务"
        @retry="load"
      >
        <template #cell-document_no="{ row }">
          <RouterLink
            :to="`/documents/${row.document_id}`"
            class="task-doc"
          >
            {{ row.document_no }}
          </RouterLink>
          <div class="task-node muted">
            {{ row.node_order }}. {{ row.node_name }}
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
          <RiskLevelTag
            v-if="row.overall_risk_level"
            :level="String(row.overall_risk_level)"
          />
          <span
            v-else
            class="weak"
          >—</span>
        </template>
        <template #cell-task_status="{ row }">
          <StatusBadge v-bind="approvalTaskStatusView(String(row.task_status))" />
        </template>
        <template #cell-created_at="{ row }">
          <span class="muted">{{ formatDate(String(row.created_at)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.task_status === 'pending'"
            type="button"
            class="btn-link"
            @click="openDecision(row as unknown as ApprovalTask)"
          >
            处理审批
          </button>
          <RouterLink
            :to="`/documents/${row.document_id}/risk-analysis`"
            class="btn-link"
          >
            风险分析
          </RouterLink>
        </template>
      </DataTable>

      <PaginationBar
        v-model:page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="load"
      />
    </div>

    <ApprovalDecisionDialog
      v-model="decisionOpen"
      :task="activeTask"
      @decided="load"
      @open-risk="(docId: string) => $router.push(`/documents/${docId}/risk-analysis`)"
    />
  </PageShell>
</template>

<style scoped>
.filter-keyword {
  width: 220px !important;
}

.task-doc {
  display: inline-block;
}

.task-node {
  font-size: 12px;
  margin-top: 2px;
}
</style>
