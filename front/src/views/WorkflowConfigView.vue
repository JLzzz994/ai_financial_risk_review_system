<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createWorkflowDraft, listWorkflows, patchWorkflow, publishWorkflow } from '@/api/workflows'
import { ApiError, handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { WorkflowTemplate } from '@/types/domain'
import { configStatusView } from '@/types/status'
import { formatDateTime } from '@/utils/format'
import ApiHint from '@/components/ApiHint.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DataTable from '@/components/DataTable.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageShell from '@/components/PageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const app = useAppStore()

const workflows = ref<WorkflowTemplate[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const selected = ref<WorkflowTemplate | null>(null)

const publishDialogOpen = ref(false)
const publishTarget = ref<WorkflowTemplate | null>(null)
const disableDialogOpen = ref(false)
const disableTarget = ref<WorkflowTemplate | null>(null)
const creating = ref(false)

const columns = [
  { key: 'name', title: '模板名称', width: '18%' },
  { key: 'version', title: '版本', width: '8%' },
  { key: 'match_condition', title: '匹配条件', width: '30%' },
  { key: 'approval_mode', title: '执行模式', width: '10%' },
  { key: 'status', title: '状态', width: '9%' },
  { key: 'updated_at', title: '更新时间', width: '13%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    workflows.value = await listWorkflows()
    if (!selected.value || !workflows.value.some((w) => w.workflow_id === selected.value?.workflow_id)) {
      selected.value = workflows.value[0] ?? null
    }
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function select(workflow: WorkflowTemplate): void {
  selected.value = workflow
}

async function handleCreateDraft(): Promise<void> {
  if (creating.value) return
  const published = workflows.value.find((w) => w.status === 'published')
  if (!published) return
  creating.value = true
  try {
    const draft = await createWorkflowDraft({
      name: published.name,
      match_condition: published.match_condition,
      nodes: published.nodes.map((n) => ({
        order: n.order,
        name: n.name,
        approver_role: n.approver_role,
        approver_names: n.approver_names,
      })),
    })
    // mock 场景下直接使用返回模板刷新
    app.push('success', `已基于 v${published.version} 创建草稿`)
    selected.value = draft
    await load()
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      app.push('warning', '已存在未发布的草稿版本，请先处理该草稿')
      return
    }
    handleApiError(error)
  } finally {
    creating.value = false
  }
}

function askPublish(workflow: WorkflowTemplate): void {
  publishTarget.value = workflow
  publishDialogOpen.value = true
}

async function confirmPublish(reason: string): Promise<void> {
  if (!publishTarget.value) return
  try {
    const updated = await publishWorkflow(publishTarget.value.workflow_id, reason)
    app.push('success', `已发布 ${updated.name} v${updated.version}`)
    publishDialogOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  }
}

function askDisable(workflow: WorkflowTemplate): void {
  disableTarget.value = workflow
  disableDialogOpen.value = true
}

async function confirmDisable(reason: string): Promise<void> {
  if (!disableTarget.value) return
  try {
    const updated = await patchWorkflow(disableTarget.value.workflow_id, { status: 'disabled' })
    app.push('success', `已停用 ${updated.name} v${updated.version}：${reason}`)
    disableDialogOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

onMounted(load)
</script>

<template>
  <PageShell
    title="流程配置"
    description="版本化审批流程模板：仅支持顺序（sequential）执行模式，节点调整需发布新版本"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="GET/POST /api/v1/approval-workflows" />
        <button
          type="button"
          class="btn btn-primary"
          :disabled="creating"
          @click="handleCreateDraft"
        >
          {{ creating ? '创建中…' : '新建草稿版本' }}
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <div class="card">
      <DataTable
        :columns="columns"
        :rows="workflows as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        row-key="workflow_id"
        empty-text="暂无流程模板"
        @retry="load"
      >
        <template #cell-name="{ row }">
          <button
            type="button"
            class="btn-link wf-name"
            @click="select(row as unknown as WorkflowTemplate)"
          >
            {{ row.name }}
          </button>
        </template>
        <template #cell-version="{ row }">
          <span class="mono">v{{ row.version }}</span>
        </template>
        <template #cell-match_condition="{ row }">
          <span class="mono match-condition">{{ row.match_condition }}</span>
        </template>
        <template #cell-approval_mode>
          <span class="pill mode-pill">sequential</span>
        </template>
        <template #cell-status="{ row }">
          <StatusBadge v-bind="configStatusView(String(row.status))" />
        </template>
        <template #cell-updated_at="{ row }">
          <span class="muted">{{ formatDateTime(String(row.updated_at)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'draft'"
            type="button"
            class="btn-link"
            @click="askPublish(row as unknown as WorkflowTemplate)"
          >
            发布
          </button>
          <button
            v-if="row.status === 'published'"
            type="button"
            class="btn-link btn-link-danger"
            @click="askDisable(row as unknown as WorkflowTemplate)"
          >
            停用
          </button>
        </template>
      </DataTable>
    </div>

    <section
      v-if="selected"
      class="card"
    >
      <div class="card-title">
        <span>节点配置 · {{ selected.name }} v{{ selected.version }}</span>
        <StatusBadge
          v-bind="configStatusView(selected.status)"
          :dot="false"
        />
      </div>
      <p
        v-if="selected.status === 'published'"
        class="muted wf-note"
      >
        已发布模板不可直接修改；调整节点请「新建草稿版本」，审核通过后发布生效。
      </p>
      <ol class="node-list">
        <li
          v-for="node in selected.nodes"
          :key="node.node_id"
          class="node-item"
        >
          <span class="node-order">{{ node.order }}</span>
          <div class="node-body">
            <div class="node-head">
              <span class="node-name">{{ node.name }}</span>
              <span class="node-role pill">{{ node.approver_role }}</span>
            </div>
            <p class="node-meta">
              审批人：{{ node.approver_names }}<template v-if="node.sla_hours">
                · 时限 {{ node.sla_hours }} 小时
              </template>
            </p>
          </div>
          <span
            class="node-arrow"
            aria-hidden="true"
          >→</span>
        </li>
      </ol>
      <p class="muted wf-sequential-hint">
        顺序执行：上一节点通过后，下一节点才会生成审批任务；退回重提将生成新版本并从第一个节点重新开始。
      </p>
    </section>

    <ConfirmDialog
      v-model="publishDialogOpen"
      title="发布流程版本"
      :message="`确认发布「${publishTarget?.name ?? ''} v${publishTarget?.version ?? ''}」？发布后新提交的单据将按该版本执行审批。`"
      confirm-text="确认发布"
      require-reason
      reason-label="发布说明"
      @confirm="confirmPublish"
    />
    <ConfirmDialog
      v-model="disableDialogOpen"
      title="停用流程"
      :message="`确认停用「${disableTarget?.name ?? ''} v${disableTarget?.version ?? ''}」？停用后新单据将无法匹配该流程。`"
      confirm-text="确认停用"
      tone="danger"
      require-reason
      reason-label="停用原因"
      @confirm="confirmDisable"
    />
  </PageShell>
</template>

<style scoped>
.wf-name {
  font-weight: 600;
}

.match-condition {
  color: var(--color-text-secondary);
}

.mode-pill {
  background: var(--status-purple-bg);
  color: var(--status-purple);
}

.wf-note {
  margin-bottom: 14px;
  font-size: 13px;
}

.node-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 4px;
  border-bottom: 1px solid var(--color-border);
}

.node-item:last-child {
  border-bottom: none;
}

.node-order {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--color-selected);
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.node-body {
  flex: 1;
  min-width: 0;
}

.node-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.node-role {
  background: var(--status-gray-bg);
  color: var(--status-gray);
}

.node-meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-weak);
}

.node-arrow {
  color: var(--color-text-weak);
  flex-shrink: 0;
}

.node-item:last-child .node-arrow {
  display: none;
}

.wf-sequential-hint {
  margin-top: 14px;
  font-size: 12px;
  line-height: 18px;
}

.btn-link-danger {
  color: var(--risk-high-text);
}
</style>
