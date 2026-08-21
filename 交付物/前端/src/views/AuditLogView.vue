<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { exportAuditLogs, listAuditLogs } from '@/api/audit-logs'
import { handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { AuditLog } from '@/types/domain'
import { auditResultView } from '@/types/status'
import { formatDateTime } from '@/utils/format'
import BaseDrawer from '@/components/BaseDrawer.vue'
import DataTable from '@/components/DataTable.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageShell from '@/components/PageShell.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const app = useAppStore()

const rows = ref<AuditLog[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref<string | null>(null)
const page = ref(1)
const pageSize = 50
const exporting = ref(false)

const filters = reactive({
  action: '',
  actor: '',
  request_id: '',
  date_from: '',
})

const detailLog = ref<AuditLog | null>(null)
const detailOpen = ref(false)

const actionOptions = [
  'document.submit',
  'document.withdraw',
  'document.void',
  'attachment.upload',
  'attachment.download',
  'attachment.delete',
  'analysis_task.create',
  'analysis_task.retry',
  'risk_finding.review',
  'approval_task.decision',
  'rule.update',
  'rule.publish',
  'approval_workflow.publish',
  'review_report.export',
]

const columns = [
  { key: 'occurred_at', title: '时间', width: '13%' },
  { key: 'actor_name', title: '操作人', width: '9%' },
  { key: 'action', title: '操作', width: '15%' },
  { key: 'resource_no', title: '对象', width: '18%' },
  { key: 'result', title: '结果', width: '8%' },
  { key: 'request_id', title: '请求 ID', width: '11%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const result = await listAuditLogs({ ...filters, page: page.value, page_size: pageSize })
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

function openDetail(log: AuditLog): void {
  detailLog.value = log
  detailOpen.value = true
}

async function handleExport(): Promise<void> {
  if (exporting.value) return
  exporting.value = true
  try {
    await exportAuditLogs({ ...filters, page: page.value, page_size: pageSize })
    app.push('success', '审计日志导出已开始下载')
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell
    title="审计日志"
    description="状态变更、人工复核、审批决定、外部调用与敏感下载的审计记录（授权范围）"
  >
    <template #actions>
      <div class="row">
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="exporting"
          @click="handleExport"
        >
          {{ exporting ? '导出中…' : '导出' }}
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <div
      v-if="!loadError"
      class="card"
    >
      <div class="filter-bar">
        <select
          v-model="filters.action"
          class="select"
          aria-label="操作类型"
          @change="onFilterChange"
        >
          <option value="">
            全部操作
          </option>
          <option
            v-for="action in actionOptions"
            :key="action"
            :value="action"
          >
            {{ action }}
          </option>
        </select>
        <input
          v-model="filters.actor"
          type="search"
          class="input filter-actor"
          placeholder="操作人"
          aria-label="操作人"
          @keyup.enter="onFilterChange"
        >
        <input
          v-model="filters.request_id"
          type="search"
          class="input filter-request"
          placeholder="请求 ID（request_id）"
          aria-label="请求 ID"
          @keyup.enter="onFilterChange"
        >
        <input
          v-model="filters.date_from"
          type="date"
          class="input filter-date"
          aria-label="开始日期"
          @change="onFilterChange"
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
        row-key="log_id"
        empty-text="当前范围内没有审计记录"
        @retry="load"
      >
        <template #cell-occurred_at="{ row }">
          <span class="muted">{{ formatDateTime(String(row.occurred_at)) }}</span>
        </template>
        <template #cell-action="{ row }">
          <span class="mono">{{ row.action }}</span>
        </template>
        <template #cell-resource_no="{ row }">
          <span>{{ row.resource_no ?? '—' }}</span>
        </template>
        <template #cell-result="{ row }">
          <StatusBadge
            v-bind="auditResultView(String(row.result))"
            :dot="false"
          />
        </template>
        <template #cell-request_id="{ row }">
          <span class="mono">{{ row.request_id }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            type="button"
            class="btn-link"
            @click="openDetail(row as unknown as AuditLog)"
          >
            详情
          </button>
        </template>
      </DataTable>

      <PaginationBar
        v-model:page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="load"
      />
    </div>

    <BaseDrawer
      v-model="detailOpen"
      title="审计详情"
      width="480px"
    >
      <template v-if="detailLog">
        <dl class="detail-fields">
          <div><dt>时间</dt><dd>{{ formatDateTime(detailLog.occurred_at) }}</dd></div>
          <div><dt>操作人</dt><dd>{{ detailLog.actor_name }}</dd></div>
          <div>
            <dt>操作</dt><dd class="mono">
              {{ detailLog.action }}
            </dd>
          </div>
          <div>
            <dt>对象类型</dt><dd class="mono">
              {{ detailLog.resource_type }}
            </dd>
          </div>
          <div><dt>对象</dt><dd>{{ detailLog.resource_no ?? detailLog.resource_id ?? '—' }}</dd></div>
          <div>
            <dt>结果</dt><dd>
              <StatusBadge
                v-bind="auditResultView(detailLog.result)"
                :dot="false"
              />
            </dd>
          </div>
          <div>
            <dt>请求 ID</dt><dd class="mono">
              {{ detailLog.request_id }}
            </dd>
          </div>
          <div v-if="detailLog.detail">
            <dt>详情</dt><dd>{{ detailLog.detail }}</dd>
          </div>
        </dl>
        <p class="detail-note">
          审计记录不可修改；导出操作本身也会写入审计日志。
        </p>
      </template>
    </BaseDrawer>
  </PageShell>
</template>

<style scoped>
.filter-actor {
  width: 140px !important;
}

.filter-request {
  width: 200px !important;
}

.filter-date {
  width: 150px !important;
}

.detail-fields > div {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
}

.detail-fields > div:last-child {
  border-bottom: none;
}

.detail-fields dt {
  color: var(--color-text-secondary);
}

.detail-fields dd {
  margin: 0;
  color: var(--color-text);
  word-break: break-all;
}

.detail-note {
  margin-top: 16px;
  font-size: 12px;
  color: var(--color-text-weak);
  background: var(--color-panel);
  border-radius: var(--radius-input);
  padding: 10px 12px;
}
</style>
