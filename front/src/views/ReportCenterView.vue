<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listDocuments } from '@/api/documents'
import {
  downloadExport,
  exportReviewReport,
  getExportTask,
  getReviewReport,
  listReportVersions,
} from '@/api/reports'
import { safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { ReviewReport } from '@/types/domain'
import { reportStatusView } from '@/types/status'
import { formatDateTime } from '@/utils/format'
import DataTable from '@/components/DataTable.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageShell from '@/components/PageShell.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const documentVersionId = computed(() => String(route.params.documentVersionId ?? ''))
const isDetailMode = computed(() => documentVersionId.value !== '')

const report = ref<ReviewReport | null>(null)
const versionRows = ref<Array<{ document_version_id: string; version_no: number; report_status: string; overall_risk_level?: string; generated_at?: string }>>([])
const listRows = ref<Array<{ document_no: string; document_id: string; version_no: number; report_status: string; overall_risk_level?: string; generated_at?: string; document_version_id: string }>>([])
const keyword = ref('')
const loading = ref(true)
const loadError = ref<string | null>(null)

const exporting = ref(false)
let exportPollTimer: number | null = null

const listColumns = [
  { key: 'document_no', title: '单据编号', width: '20%' },
  { key: 'version_no', title: '报告版本', width: '10%' },
  { key: 'report_status', title: '状态', width: '10%' },
  { key: 'overall_risk_level', title: '整体风险', width: '10%' },
  { key: 'generated_at', title: '生成时间', width: '15%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

const versionColumns = [
  { key: 'version_no', title: '版本', width: '10%' },
  { key: 'report_status', title: '状态', width: '12%' },
  { key: 'overall_risk_level', title: '整体风险', width: '12%' },
  { key: 'generated_at', title: '生成时间', width: '18%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    if (isDetailMode.value) {
      report.value = await getReviewReport(documentVersionId.value)
      versionRows.value = await listReportVersions(report.value.document_id).catch(() => [])
    } else {
      const documents = await listDocuments({ page_size: 50 })
      const rows: typeof listRows.value = []
      for (const doc of documents.items.slice(0, 10)) {
        const versions = await listReportVersions(doc.document_id).catch(() => [])
        for (const version of versions) {
          rows.push({
            document_no: doc.document_no,
            document_id: doc.document_id,
            document_version_id: version.document_version_id,
            version_no: version.version_no,
            report_status: version.report_status,
            overall_risk_level: version.overall_risk_level,
            generated_at: version.generated_at,
          })
        }
      }
      listRows.value = rows
    }
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

const filteredListRows = computed(() => {
  const kw = keyword.value.trim()
  if (!kw) return listRows.value
  return listRows.value.filter((row) => row.document_no.includes(kw))
})

async function handleExport(format: 'pdf' | 'xlsx'): Promise<void> {
  if (!report.value || exporting.value) return
  exporting.value = true
  try {
    const task = await exportReviewReport(report.value.document_version_id, format)
    app.push('info', '导出任务已创建，正在生成文件…')
    pollExport(task.export_task_id)
  } catch (error) {
    app.push('error', safeErrorMessage(error))
    exporting.value = false
  }
}

function pollExport(exportTaskId: string): void {
  exportPollTimer = window.setTimeout(async () => {
    try {
      const task = await getExportTask(exportTaskId)
      if (task.status === 'succeeded') {
        await downloadExport(exportTaskId, task.file_name ?? '审核报告.pdf')
        app.push('success', '导出完成，已开始下载')
        exporting.value = false
        return
      }
      if (task.status === 'failed') {
        app.push('error', task.error_message ?? '导出失败，请稍后重试')
        exporting.value = false
        return
      }
      pollExport(exportTaskId)
    } catch (error) {
      app.push('error', safeErrorMessage(error))
      exporting.value = false
    }
  }, 900)
}

onMounted(load)
onBeforeUnmount(() => {
  if (exportPollTimer !== null) window.clearTimeout(exportPollTimer)
})
</script>

<template>
  <PageShell
    :title="isDetailMode ? `审核报告 · ${report?.document_no ?? ''}` : '报告中心'"
    :description="isDetailMode ? '按单据版本查看审核报告、导出与历史版本' : '全部单据的版本报告列表'"
  >
    <template #actions>
      <div class="row">
        <button
          v-if="isDetailMode"
          type="button"
          class="btn btn-secondary"
          @click="router.push('/reports')"
        >
          返回列表
        </button>
        <button
          v-if="isDetailMode"
          type="button"
          class="btn btn-primary"
          :disabled="exporting"
          @click="handleExport('pdf')"
        >
          {{ exporting ? '导出中…' : '导出 PDF' }}
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <!-- 列表模式 -->
    <div
      v-if="!isDetailMode && !loadError"
      class="card"
    >
      <div class="filter-bar">
        <input
          v-model="keyword"
          type="search"
          class="input filter-keyword"
          placeholder="搜索单据编号"
          aria-label="搜索单据编号"
        >
      </div>
      <DataTable
        :columns="listColumns"
        :rows="filteredListRows as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        row-key="document_version_id"
        empty-text="暂无报告（单据提交并完成分析后会生成草稿报告）"
        @retry="load"
      >
        <template #cell-document_no="{ row }">
          <RouterLink :to="`/documents/${row.document_id}`">
            {{ row.document_no }}
          </RouterLink>
        </template>
        <template #cell-version_no="{ row }">
          <span class="mono">v{{ row.version_no }}</span>
        </template>
        <template #cell-report_status="{ row }">
          <StatusBadge v-bind="reportStatusView(String(row.report_status))" />
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
        <template #cell-generated_at="{ row }">
          <span class="muted">{{ formatDateTime(String(row.generated_at)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <RouterLink
            :to="`/reports/${row.document_version_id}`"
            class="btn-link"
          >
            查看报告
          </RouterLink>
        </template>
      </DataTable>
    </div>

    <!-- 详情模式 -->
    <template v-if="isDetailMode && report && !loadError">
      <section class="card report-head">
        <div class="report-head-main">
          <div class="row report-head-tags">
            <span class="mono report-version">v{{ report.version_no }}</span>
            <StatusBadge v-bind="reportStatusView(report.report_status)" />
            <RiskLevelTag :level="report.overall_risk_level" />
          </div>
          <h2 class="report-doc">
            {{ report.document_no }}
          </h2>
          <p class="muted report-meta">
            规则版本 {{ report.rule_version }} · 生成时间 {{ formatDateTime(report.generated_at) }} · document_version_id
            <span class="mono">{{ report.document_version_id }}</span>
          </p>
        </div>
      </section>

      <section class="card">
        <h2 class="card-title">
          报告摘要
        </h2>
        <p class="report-summary">
          {{ report.content.summary }}
        </p>
      </section>

      <section
        v-for="section in report.content.sections"
        :key="section.heading"
        class="card"
      >
        <h2 class="card-title">
          {{ section.heading }}
        </h2>
        <ul class="report-items">
          <li
            v-for="item in section.items"
            :key="item"
            class="report-item"
          >
            {{ item }}
          </li>
        </ul>
      </section>

      <section class="card">
        <h2 class="card-title">
          历史版本
        </h2>
        <DataTable
          :columns="versionColumns"
          :rows="versionRows as unknown as Array<Record<string, unknown>>"
          row-key="document_version_id"
          empty-text="暂无历史版本"
        >
          <template #cell-version_no="{ row }">
            <span
              class="mono"
              :class="{ 'version-current': row.document_version_id === documentVersionId }"
            >v{{ row.version_no }}</span>
          </template>
          <template #cell-report_status="{ row }">
            <StatusBadge v-bind="reportStatusView(String(row.report_status))" />
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
          <template #cell-generated_at="{ row }">
            <span class="muted">{{ formatDateTime(String(row.generated_at)) }}</span>
          </template>
          <template #cell-actions="{ row }">
            <RouterLink
              v-if="row.document_version_id !== documentVersionId"
              :to="`/reports/${row.document_version_id}`"
              class="btn-link"
            >
              切换版本
            </RouterLink>
            <span
              v-else
              class="weak"
            >当前版本</span>
          </template>
        </DataTable>
      </section>
    </template>
  </PageShell>
</template>

<style scoped>
.filter-keyword {
  width: 240px !important;
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.report-head-tags {
  gap: 10px;
  flex-wrap: wrap;
}

.report-version {
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  padding: 2px 8px;
  color: var(--color-text-secondary);
}

.report-doc {
  margin-top: 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.report-meta {
  margin-top: 6px;
  font-size: 12px;
}

.report-summary {
  font-size: 14px;
  line-height: 24px;
  color: var(--color-text);
  background: var(--color-panel);
  border-radius: var(--radius-input);
  padding: 14px 16px;
}

.report-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.report-item {
  position: relative;
  padding: 8px 0 8px 16px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
}

.report-item:last-child {
  border-bottom: none;
}

.report-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 15px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
}

.version-current {
  color: var(--color-primary);
  font-weight: 600;
}
</style>
