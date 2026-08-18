<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createLineItem, deleteLineItem, getDocument, submitDocument, updateDocument, updateLineItem } from '@/api/documents'
import { handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type {
  BatchPaymentDetail,
  DocumentDetail,
  DocumentPayload,
  DocumentType,
  LineItem,
} from '@/types/domain'
import { documentStatusView } from '@/types/status'
import { addAmounts, formatMoney, isValidAmountInput, isZeroAmount } from '@/utils/format'
import ApiHint from '@/components/ApiHint.vue'
import AttachmentUploader from '@/components/AttachmentUploader.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import PageShell from '@/components/PageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'

interface EditableLineItem {
  item_id: string | null
  expense_item: string
  expense_date: string
  amount: string
  invoice_no: string
  remark: string
  _origin?: LineItem
}

const route = useRoute()
const router = useRouter()
const app = useAppStore()

const documentId = computed(() => String(route.params.id))
const document = ref<DocumentDetail | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const saving = ref(false)

const form = reactive({
  document_type: 'expense_reimbursement' as DocumentType,
  expense_category: '市场推广费',
  apply_date: new Date().toISOString().slice(0, 10),
  applicant_department: '市场部',
  budget_department: '',
  payee_name: '',
  payee_account: '',
  payee_bank: '',
  reason_text: '',
  contract_no: '',
  supplier_name: '',
  payment_ratio: '100',
  payment_terms: '',
  planned_payment_date: new Date().toISOString().slice(0, 10),
  payment_amount: '0.01',
  travel_location: '',
  travel_start_date: new Date().toISOString().slice(0, 10),
  travel_end_date: new Date().toISOString().slice(0, 10),
  transportation_amount: '',
  accommodation_amount: '',
  meal_amount: '',
  allowance_amount: '',
})

const items = ref<EditableLineItem[]>([])
const itemErrors = ref<Record<number, string>>({})
const paymentDetails = ref<Array<BatchPaymentDetail & { _id: number }>>([])

const submitDialogOpen = ref(false)
const submitReason = ref('')
const submitting = ref(false)

const categoryOptions = ['市场推广费', '差旅费', '办公用品', '业务招待费', '培训费']

const totalAmount = computed(() => addAmounts(...items.value.map((i) => i.amount || '0')))
const specializedTotalAmount = computed(() => {
  if (form.document_type === 'public_payment' || form.document_type === 'prepayment') {
    return form.payment_amount || '0.00'
  }
  if (form.document_type === 'batch_payment') {
    return addAmounts(...paymentDetails.value.map((item) => item.amount || '0'))
  }
  if (form.document_type === 'travel_reimbursement') {
    return addAmounts(
      form.transportation_amount || '0',
      form.accommodation_amount || '0',
      form.meal_amount || '0',
      form.allowance_amount || '0',
    )
  }
  return '0.00'
})
const effectiveTotalAmount = computed(() =>
  form.document_type === 'expense_reimbursement' ? totalAmount.value : specializedTotalAmount.value,
)
const documentTypeLabel = computed(() => ({
  public_payment: '对公付款单',
  prepayment: '预付款单',
  batch_payment: '批量付款单',
  expense_reimbursement: '费用报销单',
  travel_reimbursement: '差旅报销单',
}[form.document_type]))

const isEditable = computed(() =>
  ['draft', 'returned'].includes(document.value?.document_status ?? 'draft'),
)

const canSubmit = computed(
  () =>
    isEditable.value &&
    !isZeroAmount(effectiveTotalAmount.value) &&
    form.reason_text.trim().length > 0 &&
    (form.document_type !== 'expense_reimbursement' ||
      (items.value.length > 0 && form.payee_name.trim().length > 0)),
)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const doc = await getDocument(documentId.value)
    document.value = doc
    form.expense_category = doc.expense_category || '市场推广费'
    form.apply_date = doc.apply_date
    form.applicant_department = doc.applicant_department
    form.budget_department = doc.budget_department ?? ''
    form.payee_name = doc.payee_name ?? ''
    form.payee_account = doc.payee_account ?? ''
    form.payee_bank = doc.payee_bank ?? ''
    form.reason_text = doc.reason_text
    form.payment_amount = doc.total_amount || '0.01'
    form.document_type = doc.document_type as DocumentType
    const payload = doc.document_payload
    if (payload?.document_type === 'public_payment' || payload?.document_type === 'prepayment') {
      form.contract_no = payload.contract_no
      form.supplier_name = payload.supplier_name
      form.payment_ratio = payload.payment_ratio
      form.payment_terms = payload.payment_terms
      form.planned_payment_date = payload.planned_payment_date
    } else if (payload?.document_type === 'batch_payment') {
      paymentDetails.value = payload.payment_details.map((item, index) => ({ ...item, _id: index }))
    } else if (payload?.document_type === 'travel_reimbursement') {
      form.travel_location = payload.travel_location
      form.travel_start_date = payload.travel_start_date
      form.travel_end_date = payload.travel_end_date
      form.transportation_amount = payload.transportation_amount
      form.accommodation_amount = payload.accommodation_amount
      form.meal_amount = payload.meal_amount
      form.allowance_amount = payload.allowance_amount
    }
    items.value = (doc.line_items ?? []).map((item) => ({
      item_id: item.item_id,
      expense_item: item.expense_item,
      expense_date: item.expense_date,
      amount: item.amount,
      invoice_no: item.invoice_no ?? '',
      remark: item.remark ?? '',
      _origin: item,
    }))
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function addItem(): void {
  items.value.push({
    item_id: null,
    expense_item: '',
    expense_date: new Date().toISOString().slice(0, 10),
    amount: '',
    invoice_no: '',
    remark: '',
  })
}

function removeItem(index: number): void {
  items.value.splice(index, 1)
  delete itemErrors.value[index]
}

function validateItems(): boolean {
  itemErrors.value = {}
  items.value.forEach((item, index) => {
    if (!item.expense_item.trim()) itemErrors.value[index] = '请填写费用项目'
    else if (!item.amount.trim() || !isValidAmountInput(item.amount)) itemErrors.value[index] = '金额格式不正确（最多两位小数）'
    else if (item.amount.trim() === '0' || item.amount.trim() === '0.00') itemErrors.value[index] = '金额必须大于 0'
  })
  return Object.keys(itemErrors.value).length === 0
}

/** 校验专属表单，金额仅按字符串规则检查，不进行浮点运算。 */
function validateSpecialized(): boolean {
  if (form.document_type === 'public_payment' || form.document_type === 'prepayment') {
    return Boolean(
      form.contract_no.trim() && form.supplier_name.trim() && form.payment_terms.trim() &&
      form.planned_payment_date && /^(100(?:\.0{1,2})?|(?:[0-9]|[1-9][0-9])(?:\.\d{1,2})?)$/.test(form.payment_ratio.trim()) &&
      isValidAmountInput(form.payment_amount) && !isZeroAmount(form.payment_amount),
    )
  }
  if (form.document_type === 'batch_payment') {
    return paymentDetails.value.length > 0 && paymentDetails.value.every(
      (item) => item.payee_name.trim() && isValidAmountInput(item.amount) && !isZeroAmount(item.amount),
    )
  }
  if (form.document_type === 'travel_reimbursement') {
    return Boolean(
      form.travel_location.trim() && form.travel_start_date && form.travel_end_date &&
      form.travel_end_date >= form.travel_start_date &&
      [form.transportation_amount, form.accommodation_amount, form.meal_amount, form.allowance_amount]
        .every((amount) => isValidAmountInput(amount || '0')) && !isZeroAmount(specializedTotalAmount.value),
    )
  }
  return true
}

/** 按后端五类契约组装专属载荷，所有金额字段原样以字符串发送。 */
function buildDocumentPayload(): DocumentPayload | undefined {
  const currency = 'CNY' as const
  if (form.document_type === 'public_payment' || form.document_type === 'prepayment') {
    return {
      document_type: form.document_type,
      currency,
      contract_no: form.contract_no,
      supplier_name: form.supplier_name,
      payment_ratio: form.payment_ratio,
      payment_terms: form.payment_terms,
      planned_payment_date: form.planned_payment_date,
    }
  }
  if (form.document_type === 'batch_payment') {
    return {
      document_type: form.document_type,
      currency,
      payment_details: paymentDetails.value.map(({ _id, ...item }) => item),
      total_amount: specializedTotalAmount.value,
      payment_count: paymentDetails.value.length,
    }
  }
  if (form.document_type === 'travel_reimbursement') {
    return {
      document_type: form.document_type,
      currency,
      travel_location: form.travel_location,
      travel_start_date: form.travel_start_date,
      travel_end_date: form.travel_end_date,
      transportation_amount: form.transportation_amount || '0.00',
      accommodation_amount: form.accommodation_amount || '0.00',
      meal_amount: form.meal_amount || '0.00',
      allowance_amount: form.allowance_amount || '0.00',
    }
  }
  return {
    document_type: 'expense_reimbursement',
    currency,
    expense_details: items.value.map((item) => ({
      expense_item: item.expense_item,
      consumption_date: item.expense_date,
      consumption_location: '未填写',
      expense_category: form.expense_category,
      reimbursement_amount: item.amount,
      currency,
    })),
  }
}

function addPaymentDetail(): void {
  paymentDetails.value.push({ payee_name: '', amount: '', _id: Date.now() })
}

function removePaymentDetail(index: number): void {
  paymentDetails.value.splice(index, 1)
}

async function saveDraft(): Promise<boolean> {
  if (form.document_type === 'expense_reimbursement' && !validateItems()) {
    app.push('warning', '费用明细存在校验错误，请修正后保存')
    return false
  }
  if (form.document_type !== 'expense_reimbursement' && !validateSpecialized()) {
    app.push('warning', '请完善单据专属字段并检查金额格式')
    return false
  }
  if (isZeroAmount(effectiveTotalAmount.value)) {
    app.push('warning', '金额必须大于 0，不能保存 0.00')
    return false
  }
  saving.value = true
  try {
    // 1. 同步单据公共字段
    const updated = await updateDocument(documentId.value, {
      document_type: form.document_type,
      expense_category: form.expense_category,
      apply_date: form.apply_date,
      applicant_department: form.applicant_department,
      budget_department: form.budget_department || undefined,
      payee_name: form.payee_name,
      payee_account: form.payee_account || undefined,
      payee_bank: form.payee_bank || undefined,
      reason_text: form.reason_text,
      total_amount: effectiveTotalAmount.value,
      document_payload: buildDocumentPayload(),
    }, crypto.randomUUID())
    document.value = updated
    // 2. 同步明细行：删除 → 新增 → 更新
    for (const item of items.value) {
      if (item.item_id && item._origin) {
        await updateLineItem(documentId.value, item.item_id, {
          expense_item: item.expense_item,
          expense_date: item.expense_date,
          amount: item.amount,
          invoice_no: item.invoice_no || undefined,
          remark: item.remark || undefined,
        })
      } else if (!item.item_id) {
        await createLineItem(documentId.value, {
          expense_item: item.expense_item,
          expense_date: item.expense_date,
          amount: item.amount,
          currency: 'CNY',
          invoice_no: item.invoice_no || undefined,
          remark: item.remark || undefined,
        })
      }
    }
    const removed = (updated.line_items ?? []).filter(
      (origin) => !items.value.some((item) => item.item_id === origin.item_id),
    )
    for (const origin of removed) {
      await deleteLineItem(documentId.value, origin.item_id)
    }
    app.push('success', '草稿已保存')
    await load()
    return true
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
    return false
  } finally {
    saving.value = false
  }
}

function askSubmit(): void {
  if (!canSubmit.value || (form.document_type === 'expense_reimbursement' && !validateItems()) ||
      (form.document_type !== 'expense_reimbursement' && !validateSpecialized())) {
    app.push('warning', '提交前请完善：费用明细、收款方与报销事由为必填')
    return
  }
  submitReason.value = ''
  submitDialogOpen.value = true
}

async function confirmSubmit(reason: string): Promise<void> {
  if (submitting.value) return
  submitting.value = true
  try {
    // 先保存再提交，保证提交的是当前编辑内容（幂等键一次性使用）
    if (!await saveDraft()) return
    const result = await submitDocument(documentId.value, reason, crypto.randomUUID())
    app.push('success', '已提交，进入解析与风险分析')
    submitDialogOpen.value = false
    void router.push({ path: `/documents/${result.document_id}`, query: { task: result.analysis_task_id } })
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell
    :title="document ? `编辑 ${document.document_no}` : '编辑单据'"
    :description="document ? '费用报销单草稿编辑，提交后将生成不可变版本并触发风险分析' : '费用报销单草稿编辑'"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="PATCH /api/v1/documents/{document_id}" />
        <StatusBadge
          v-if="document"
          v-bind="documentStatusView(document.document_status)"
        />
      </div>
    </template>

    <div
      v-if="loading"
      class="card loading-card"
    >
      单据加载中…
    </div>
    <div
      v-else-if="loadError"
      class="card loading-card"
    >
      {{ loadError }}
      <button
        type="button"
        class="btn-link"
        @click="load"
      >
        重试
      </button>
    </div>
    <div
      v-else-if="!isEditable"
      class="card loading-card"
    >
      当前状态为「{{ documentStatusView(document?.document_status).label }}」，仅草稿与退回状态可编辑。
      <RouterLink
        :to="`/documents/${documentId}`"
        class="btn-link"
      >
        返回详情
      </RouterLink>
    </div>

    <template v-else>
      <section class="card">
        <h2 class="card-title">
          基本信息
        </h2>
        <div class="form-grid">
          <div class="field">
            <label>单据类型</label>
            <input
              class="input"
              :value="documentTypeLabel"
              disabled
            >
          </div>
          <div
            v-if="form.document_type === 'expense_reimbursement'"
            class="field"
          >
            <label for="edit-category">费用类别 <span class="field-required" /></label>
            <select
              id="edit-category"
              v-model="form.expense_category"
              class="select"
            >
              <option
                v-for="option in categoryOptions"
                :key="option"
                :value="option"
              >
                {{ option }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="edit-date">费用发生日期 <span class="field-required" /></label>
            <input
              id="edit-date"
              v-model="form.apply_date"
              type="date"
              class="input"
            >
          </div>
          <div class="field">
            <label for="edit-department">申请部门 <span class="field-required" /></label>
            <input
              id="edit-department"
              v-model="form.applicant_department"
              type="text"
              class="input"
            >
          </div>
          <div class="field">
            <label for="edit-budget">预算部门</label>
            <input
              id="edit-budget"
              v-model="form.budget_department"
              type="text"
              class="input"
              placeholder="如：市场部-推广"
            >
          </div>
        </div>
      </section>

      <section
        v-if="form.document_type === 'expense_reimbursement'"
        class="card"
      >
        <h2 class="card-title">
          收款方信息
        </h2>
        <div class="form-grid">
          <div class="field">
            <label for="edit-payee-name">收款人 <span class="field-required" /></label>
            <input
              id="edit-payee-name"
              v-model="form.payee_name"
              type="text"
              class="input"
              placeholder="个人或单位名称"
            >
          </div>
          <div class="field">
            <label for="edit-payee-account">收款账号</label>
            <input
              id="edit-payee-account"
              v-model="form.payee_account"
              type="text"
              class="input"
              placeholder="银行卡号 / 对公账号"
            >
          </div>
          <div class="field">
            <label for="edit-payee-bank">开户行</label>
            <input
              id="edit-payee-bank"
              v-model="form.payee_bank"
              type="text"
              class="input"
              placeholder="开户支行"
            >
          </div>
        </div>
      </section>

      <section
        v-if="form.document_type !== 'expense_reimbursement'"
        class="card"
      >
        <h2 class="card-title">
          {{ documentTypeLabel }}专属信息
        </h2>
        <div
          v-if="form.document_type === 'public_payment' || form.document_type === 'prepayment'"
          class="form-grid"
        >
          <div class="field">
            <label>合同号 <span class="field-required" /></label><input
              v-model="form.contract_no"
              class="input"
            >
          </div>
          <div class="field">
            <label>供应商 <span class="field-required" /></label><input
              v-model="form.supplier_name"
              class="input"
            >
          </div>
          <div class="field">
            <label>付款比例（%） <span class="field-required" /></label><input
              v-model="form.payment_ratio"
              class="input"
              inputmode="decimal"
            >
          </div>
          <div class="field">
            <label>付款金额（CNY） <span class="field-required" /></label><input
              v-model="form.payment_amount"
              class="input input-amount"
              inputmode="decimal"
            >
          </div>
          <div class="field">
            <label>计划付款日期 <span class="field-required" /></label><input
              v-model="form.planned_payment_date"
              type="date"
              class="input"
            >
          </div>
          <div class="field field-wide">
            <label>付款条款 <span class="field-required" /></label><textarea
              v-model="form.payment_terms"
              class="textarea"
              rows="3"
            />
          </div>
        </div>
        <template v-else-if="form.document_type === 'batch_payment'">
          <div class="card-title">
            <span>收款明细</span><button
              type="button"
              class="btn btn-secondary btn-sm"
              @click="addPaymentDetail"
            >
              添加收款人
            </button>
          </div>
          <p
            v-if="paymentDetails.length === 0"
            class="muted empty-items"
          >
            暂无收款明细，请添加至少一笔付款。
          </p>
          <div
            v-for="(item, index) in paymentDetails"
            :key="item._id"
            class="form-grid payment-row"
          >
            <div class="field">
              <label>收款人 <span class="field-required" /></label><input
                v-model="item.payee_name"
                class="input"
              >
            </div>
            <div class="field">
              <label>金额（CNY） <span class="field-required" /></label><input
                v-model="item.amount"
                class="input input-amount"
                inputmode="decimal"
              >
            </div>
            <button
              type="button"
              class="btn-link btn-link-danger"
              @click="removePaymentDetail(index)"
            >
              删除
            </button>
          </div>
        </template>
        <div
          v-else-if="form.document_type === 'travel_reimbursement'"
          class="form-grid"
        >
          <div class="field">
            <label>出差地点 <span class="field-required" /></label><input
              v-model="form.travel_location"
              class="input"
            >
          </div>
          <div class="field">
            <label>开始日期 <span class="field-required" /></label><input
              v-model="form.travel_start_date"
              type="date"
              class="input"
            >
          </div>
          <div class="field">
            <label>结束日期 <span class="field-required" /></label><input
              v-model="form.travel_end_date"
              type="date"
              class="input"
            >
          </div>
          <div class="field">
            <label>交通费（CNY）</label><input
              v-model="form.transportation_amount"
              class="input input-amount"
              inputmode="decimal"
            >
          </div>
          <div class="field">
            <label>住宿费（CNY）</label><input
              v-model="form.accommodation_amount"
              class="input input-amount"
              inputmode="decimal"
            >
          </div>
          <div class="field">
            <label>餐费（CNY）</label><input
              v-model="form.meal_amount"
              class="input input-amount"
              inputmode="decimal"
            >
          </div>
          <div class="field">
            <label>补贴（CNY）</label><input
              v-model="form.allowance_amount"
              class="input input-amount"
              inputmode="decimal"
            >
          </div>
        </div>
        <div class="items-total">
          <span>合计金额</span><span class="items-total-value">{{ formatMoney(effectiveTotalAmount) }}</span><span class="muted">（仅支持人民币 CNY 单币种）</span>
        </div>
      </section>

      <section
        v-if="form.document_type === 'expense_reimbursement'"
        class="card"
      >
        <div class="card-title">
          <span>费用明细</span>
          <button
            type="button"
            class="btn btn-secondary btn-sm"
            @click="addItem"
          >
            添加明细
          </button>
        </div>
        <p
          v-if="items.length === 0"
          class="muted empty-items"
        >
          尚未添加明细，点击「添加明细」开始填写。
        </p>
        <div
          v-else
          class="table-wrap"
        >
          <table class="table">
            <thead>
              <tr>
                <th style="width: 24%">
                  费用项目
                </th>
                <th style="width: 14%">
                  日期
                </th>
                <th style="width: 14%; text-align: right">
                  金额（CNY）
                </th>
                <th style="width: 18%">
                  发票号
                </th>
                <th>备注</th>
                <th style="width: 50px; text-align: right">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in items"
                :key="index"
              >
                <td>
                  <input
                    v-model="item.expense_item"
                    type="text"
                    class="input input-cell"
                    placeholder="如：线下推广物料制作"
                  >
                </td>
                <td>
                  <input
                    v-model="item.expense_date"
                    type="date"
                    class="input input-cell"
                  >
                </td>
                <td>
                  <input
                    v-model="item.amount"
                    type="text"
                    class="input input-cell input-amount"
                    :aria-invalid="itemErrors[index] ? 'true' : undefined"
                    placeholder="0.00"
                    inputmode="decimal"
                  >
                  <span
                    v-if="itemErrors[index]"
                    class="field-error"
                  >{{ itemErrors[index] }}</span>
                </td>
                <td>
                  <input
                    v-model="item.invoice_no"
                    type="text"
                    class="input input-cell"
                    placeholder="可先不填"
                  >
                </td>
                <td>
                  <input
                    v-model="item.remark"
                    type="text"
                    class="input input-cell"
                  >
                </td>
                <td style="text-align: right">
                  <button
                    type="button"
                    class="btn-link btn-link-danger"
                    @click="removeItem(index)"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="items-total">
          <span>合计金额</span>
          <span class="items-total-value">{{ formatMoney(effectiveTotalAmount) }}</span>
          <span class="muted">（仅支持人民币 CNY 单币种）</span>
        </div>
      </section>

      <section class="card">
        <div class="card-title">
          <span>附件</span>
          <ApiHint text="POST /api/v1/documents/{document_id}/attachments" />
        </div>
        <AttachmentUploader :document-id="documentId" />
      </section>

      <section class="card">
        <h2 class="card-title">
          报销事由
        </h2>
        <div class="field">
          <label for="edit-reason">事由说明 <span class="field-required" /></label>
          <textarea
            id="edit-reason"
            v-model="form.reason_text"
            class="textarea"
            rows="4"
            placeholder="请说明费用背景、活动内容等（提交后随版本留存）"
          />
        </div>
      </section>

      <div class="edit-footer">
        <p class="muted edit-footer-hint">
          提交后将生成不可变版本（document_version），并自动触发附件解析与风险分析。
        </p>
        <div class="row">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="saving"
            @click="saveDraft"
          >
            {{ saving ? '保存中…' : '保存草稿' }}
          </button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!canSubmit"
            @click="askSubmit"
          >
            提交
          </button>
        </div>
      </div>
    </template>

    <ConfirmDialog
      v-model="submitDialogOpen"
      title="提交单据"
      message="提交后将生成新版本并自动开始风险分析，分析期间单据不可编辑。确认提交？"
      confirm-text="确认提交"
      require-reason
      reason-label="提交说明"
      reason-placeholder="请填写提交说明（必填）"
      @confirm="confirmSubmit"
    />
  </PageShell>
</template>

<style scoped>
.loading-card {
  color: var(--color-text-secondary);
  display: flex;
  gap: 8px;
  align-items: center;
}

.empty-items {
  padding: 12px 0;
}

.input-cell {
  padding: 8px 10px;
}

.input-amount {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.items-total {
  display: flex;
  align-items: baseline;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 14px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.items-total-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-brand-deep);
  font-variant-numeric: tabular-nums;
}

.edit-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.edit-footer-hint {
  font-size: 12px;
}
</style>
