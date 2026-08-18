<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createDocument, listDocuments, voidDocument, withdrawDocument } from '@/api/documents'
import { handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { documentStatusMap, documentStatusView } from '@/types/status'
import { documentTypeLabels, type DocumentPayload, type DocumentSummary, type DocumentType } from '@/types/domain'
import AmountText from '@/components/AmountText.vue'
import ApiHint from '@/components/ApiHint.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DataTable from '@/components/DataTable.vue'
import PageShell from '@/components/PageShell.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { formatDate } from '@/utils/format'

const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const rows = ref<DocumentSummary[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref<string | null>(null)
const creating = ref(false)
const createType = ref<DocumentType>('expense_reimbursement')

const filters = reactive({
  document_type: '',
  document_status: '',
  keyword: '',
  date_from: '',
})

const page = ref(1)
const pageSize = 50

const statusOptions = Object.entries(documentStatusMap).map(([value, meta]) => ({ value, label: meta.label }))

const withdrawTarget = ref<DocumentSummary | null>(null)
const withdrawOpen = ref(false)
const voidTarget = ref<DocumentSummary | null>(null)
const voidOpen = ref(false)

const columns = [
  { key: 'document_no', title: '单据编号', width: '15%' },
  { key: 'document_type', title: '类型', width: '10%' },
  { key: 'expense_category', title: '费用类别', width: '10%' },
  { key: 'applicant_name', title: '申请人', width: '8%' },
  { key: 'total_amount', title: '金额', align: 'right' as const, width: '11%' },
  { key: 'current_version', title: '版本', align: 'center' as const, width: '7%' },
  { key: 'document_status', title: '状态', width: '9%' },
  { key: 'overall_risk_level', title: '风险', width: '9%' },
  { key: 'created_at', title: '创建时间', width: '11%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const result = await listDocuments({ ...filters, page: page.value, page_size: pageSize })
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

async function handleCreate(): Promise<void> {
  if (creating.value) return
  const principal = auth.principal
  if (!principal) {
    app.push('warning', '登录主体信息尚未加载，请刷新后重试')
    return
  }
  creating.value = true
  try {
    const today = new Date().toISOString().slice(0, 10)
    const type = createType.value
    const payload: DocumentPayload = type === 'expense_reimbursement'
      ? {
          document_type: type,
          currency: 'CNY',
          expense_details: [{
            expense_item: '待填写费用项目',
            consumption_date: today,
            consumption_location: '待填写',
            expense_category: '市场推广费',
            reimbursement_amount: '0.01',
            currency: 'CNY',
          }],
        }
      : type === 'batch_payment'
        ? {
            document_type: type,
            currency: 'CNY',
            payment_details: [{ payee_name: '待填写收款人', amount: '0.01' }],
            total_amount: '0.01',
            payment_count: 1,
          }
        : type === 'travel_reimbursement'
          ? {
              document_type: type,
              currency: 'CNY',
              travel_location: '待填写出差地点',
              travel_start_date: today,
              travel_end_date: today,
              transportation_amount: '0.01',
              accommodation_amount: '0.00',
              meal_amount: '0.00',
              allowance_amount: '0.00',
            }
          : {
              document_type: type,
              currency: 'CNY',
              contract_no: '待填写合同号',
              supplier_name: '待填写供应商',
              payment_ratio: '100',
              payment_terms: '待填写付款条款',
              planned_payment_date: today,
            }
    const draft = await createDocument(
      {
        applicant_id: principal.user_id,
        applicant_department: principal.department ?? '待填写部门',
        total_amount: '0.01',
        currency: 'CNY',
        apply_date: today,
        reason_text: '待填写申请事由',
        document_type: type,
        expense_category: type === 'expense_reimbursement' ? '市场推广费' : undefined,
        document_payload: payload,
      },
      crypto.randomUUID(),
    )
    app.push('success', '已创建草稿，请完善单据信息')
    void router.push(`/documents/${draft.document_id}/edit`)
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    creating.value = false
  }
}

function isApplicantOwn(doc: DocumentSummary): boolean {
  return auth.roles.includes('applicant') && doc.applicant_id === auth.principal?.user_id
}

function canEdit(doc: DocumentSummary): boolean {
  return isApplicantOwn(doc) && ['draft', 'returned'].includes(doc.document_status)
}

function canWithdraw(doc: DocumentSummary): boolean {
  return isApplicantOwn(doc) && ['pending_review', 'reviewing'].includes(doc.document_status)
}

function canVoid(doc: DocumentSummary): boolean {
  return isApplicantOwn(doc) && !['approved', 'voided'].includes(doc.document_status)
}

function askWithdraw(doc: DocumentSummary): void {
  withdrawTarget.value = doc
  withdrawOpen.value = true
}

function askVoid(doc: DocumentSummary): void {
  voidTarget.value = doc
  voidOpen.value = true
}

async function confirmWithdraw(reason: string): Promise<void> {
  if (!withdrawTarget.value) return
  try {
    await withdrawDocument(withdrawTarget.value.document_id, reason)
    app.push('success', `已撤回：${withdrawTarget.value.document_no}`)
    withdrawOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

async function confirmVoid(reason: string): Promise<void> {
  if (!voidTarget.value) return
  try {
    await voidDocument(voidTarget.value.document_id, reason)
    app.push('success', `已作废：${voidTarget.value.document_no}`)
    voidOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

onMounted(load)
</script>

<template>
  <PageShell
    title="我的单据"
    description="查询、新建、复制、撤回与作废本人权限范围内的单据"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="GET /api/v1/documents" />
        <button
          v-if="auth.roles.includes('applicant')"
          type="button"
          class="btn btn-primary"
          :disabled="creating"
          @click="handleCreate"
        >
          {{ creating ? '创建中…' : '新建单据' }}
        </button>
        <select
          v-if="auth.roles.includes('applicant')"
          v-model="createType"
          class="select create-type"
          aria-label="新建单据类型"
        >
          <option
            v-for="(label, value) in documentTypeLabels"
            :key="value"
            :value="value"
          >
            新建{{ label }}
          </option>
        </select>
      </div>
    </template>

    <div class="card">
      <div
        class="filter-bar"
        @change="onFilterChange"
      >
        <select
          v-model="filters.document_type"
          class="select"
          aria-label="单据类型"
        >
          <option value="">
            全部单据类型
          </option>
          <option
            v-for="(label, value) in documentTypeLabels"
            :key="value"
            :value="value"
          >
            {{ label }}
          </option>
        </select>
        <select
          v-model="filters.document_status"
          class="select"
          aria-label="单据状态"
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
          v-model="filters.date_from"
          type="date"
          class="input filter-date"
          aria-label="开始日期"
        >
        <input
          v-model="filters.keyword"
          type="search"
          class="input filter-keyword"
          placeholder="搜索单据编号 / 费用类别"
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
        row-key="document_id"
        empty-text="暂无单据"
        @retry="load"
      >
        <template #cell-document_no="{ row }">
          <RouterLink
            :to="`/documents/${row.document_id}`"
            class="doc-link"
          >
            {{ row.document_no }}
          </RouterLink>
          <div class="doc-hint muted">
            v{{ row.current_version || '—' }}
          </div>
        </template>
        <template #cell-document_type="{ row }">
          {{ documentTypeLabels[row.document_type as DocumentType] ?? '未知单据类型' }}
        </template>
        <template #cell-total_amount="{ row }">
          <AmountText
            :value="String(row.total_amount)"
            :currency="String(row.currency)"
            strong
          />
        </template>
        <template #cell-current_version="{ row }">
          <span class="muted">v{{ row.current_version || '—' }}</span>
        </template>
        <template #cell-document_status="{ row }">
          <StatusBadge v-bind="documentStatusView(String(row.document_status))" />
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
        <template #cell-created_at="{ row }">
          <span class="muted">{{ formatDate(String(row.created_at)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <RouterLink
            :to="`/documents/${row.document_id}`"
            class="btn-link"
          >
            查看
          </RouterLink>
          <RouterLink
            v-if="canEdit(row as unknown as DocumentSummary)"
            :to="`/documents/${row.document_id}/edit`"
            class="btn-link"
          >
            编辑
          </RouterLink>
          <RouterLink
            v-if="canEdit(row as unknown as DocumentSummary)"
            :to="`/documents/${row.document_id}/edit?copy=1`"
            class="btn-link"
          >
            复制
          </RouterLink>
          <button
            v-if="canWithdraw(row as unknown as DocumentSummary)"
            type="button"
            class="btn-link"
            @click="askWithdraw(row as unknown as DocumentSummary)"
          >
            撤回
          </button>
          <button
            v-if="canVoid(row as unknown as DocumentSummary)"
            type="button"
            class="btn-link btn-link-danger"
            @click="askVoid(row as unknown as DocumentSummary)"
          >
            作废
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

    <ConfirmDialog
      v-model="withdrawOpen"
      title="撤回单据"
      :message="`确认撤回「${withdrawTarget?.document_no ?? ''}」？撤回后单据回到草稿状态，可修改后重新提交。`"
      confirm-text="确认撤回"
      require-reason
      reason-label="撤回原因"
      @confirm="confirmWithdraw"
    />
    <ConfirmDialog
      v-model="voidOpen"
      title="作废单据"
      :message="`确认作废「${voidTarget?.document_no ?? ''}」？作废后不可恢复，操作将写入审计日志。`"
      confirm-text="确认作废"
      tone="danger"
      require-reason
      reason-label="作废原因"
      @confirm="confirmVoid"
    />
  </PageShell>
</template>

<style scoped>
.filter-date {
  width: 150px !important;
}

.filter-keyword {
  width: 240px !important;
}

.create-type {
  min-width: 150px;
}

.doc-link {
  display: inline-block;
}

.doc-hint {
  font-size: 12px;
  margin-top: 2px;
}

.btn-link-danger {
  color: var(--risk-high-text);
}
</style>
