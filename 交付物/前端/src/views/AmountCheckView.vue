<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getAmountComparison } from '@/api/suppliers'
import { safeErrorMessage } from '@/api/client'
import type { AmountComparison } from '@/types/domain'
import { subtractAmount, compareAmount, formatMoney } from '@/utils/format'
import AmountText from '@/components/AmountText.vue'
import DataTable from '@/components/DataTable.vue'
import ErrorState from '@/components/ErrorState.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageShell from '@/components/PageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const route = useRoute()
const documentId = computed(() => String(route.params.id))

const comparison = ref<AmountComparison | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const refreshing = ref(false)

const rowColumns = [
  { key: 'ref_no', title: '核对项', width: '34%' },
  { key: 'amount', title: '金额', align: 'right' as const, width: '16%' },
  { key: 'difference', title: '差异', align: 'right' as const, width: '16%' },
  { key: 'result', title: '结果', width: '10%' },
  { key: 'note', title: '说明' },
]

const resultView: Record<string, { label: string; tone: 'green' | 'red' | 'orange' }> = {
  match: { label: '一致', tone: 'green' },
  mismatch: { label: '不一致', tone: 'red' },
  missing: { label: '缺失', tone: 'orange' },
}

const totalCards = computed(() => {
  if (!comparison.value) return []
  const doc = comparison.value.document_total
  const card = (label: string, value: string) => {
    const diff = subtractAmount(value, doc)
    const state = compareAmount(diff, '0') === 0 ? '与单据总额一致' : `与单据总额差异 ${formatMoney(diff)}`
    return { label, value, state, ok: compareAmount(diff, '0') === 0 }
  }
  return [
    card('单据总额', doc),
    card('明细合计', comparison.value.line_item_total),
    card('发票总额', comparison.value.invoice_total),
    card('合同总额', comparison.value.contract_total),
  ]
})

const mismatchCount = computed(() => {
  if (!comparison.value) return 0
  const all = [...comparison.value.invoice_rows, ...comparison.value.contract_rows, ...comparison.value.payment_rows]
  return all.filter((r) => r.result !== 'match').length
})

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    comparison.value = await getAmountComparison(documentId.value)
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  refreshing.value = true
  await load()
  refreshing.value = false
}

function rowsOf(key: 'invoice_rows' | 'contract_rows' | 'payment_rows'): Array<Record<string, unknown>> {
  return (comparison.value?.[key] ?? []) as unknown as Array<Record<string, unknown>>
}

function resultOf(row: Record<string, unknown>) {
  return resultView[String(row.result)] ?? { label: String(row.result), tone: 'gray' as const }
}

onMounted(load)
</script>

<template>
  <PageShell
    :title="`金额核对 · ${comparison?.document_no ?? ''}`"
    description="总额、明细、发票、合同与付款金额差异核对"
  >
    <template #actions>
      <div class="row">
        <button
          type="button"
          class="btn btn-secondary"
          :disabled="refreshing"
          @click="refresh"
        >
          {{ refreshing ? '核对中…' : '重新核对' }}
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <template v-if="comparison">
      <section
        class="grid grid-4"
        aria-label="总额核对"
      >
        <MetricCard
          v-for="cardItem in totalCards"
          :key="cardItem.label"
          :label="cardItem.label"
          :value="formatMoney(cardItem.value, comparison.currency)"
          :tone="cardItem.ok ? 'risk-low' : cardItem.label === '单据总额' ? 'default' : 'risk-medium'"
          :hint="cardItem.state"
        />
      </section>

      <section class="card">
        <div class="card-title">
          <span>发票核对</span>
          <span class="card-title-sub">发票金额与明细逐项比对</span>
        </div>
        <DataTable
          :columns="rowColumns"
          :rows="rowsOf('invoice_rows')"
          row-key="row_id"
          empty-text="暂无发票核对项"
        >
          <template #cell-amount="{ row }">
            <AmountText
              :value="String(row.amount)"
              :currency="comparison!.currency"
              strong
            />
          </template>
          <template #cell-difference="{ row }">
            <AmountText
              :value="String(row.difference)"
              :currency="comparison!.currency"
            />
          </template>
          <template #cell-result="{ row }">
            <StatusBadge
              :label="resultOf(row).label"
              :tone="resultOf(row).tone"
              :dot="false"
            />
          </template>
          <template #cell-note="{ row }">
            <span class="muted">{{ row.note ?? '—' }}</span>
          </template>
        </DataTable>
      </section>

      <section class="card">
        <div class="card-title">
          <span>合同核对</span>
          <span class="card-title-sub">合同金额与单据总额比对</span>
        </div>
        <DataTable
          :columns="rowColumns"
          :rows="rowsOf('contract_rows')"
          row-key="row_id"
          empty-text="暂无合同核对项"
        >
          <template #cell-amount="{ row }">
            <AmountText
              :value="String(row.amount)"
              :currency="comparison!.currency"
              strong
            />
          </template>
          <template #cell-difference="{ row }">
            <AmountText
              :value="String(row.difference)"
              :currency="comparison!.currency"
            />
          </template>
          <template #cell-result="{ row }">
            <StatusBadge
              :label="resultOf(row).label"
              :tone="resultOf(row).tone"
              :dot="false"
            />
          </template>
          <template #cell-note="{ row }">
            <span class="muted">{{ row.note ?? '—' }}</span>
          </template>
        </DataTable>
      </section>

      <section class="card">
        <div class="card-title">
          <span>付款核对</span>
          <span class="card-title-sub">已付款金额与应付款比对</span>
        </div>
        <DataTable
          :columns="rowColumns"
          :rows="rowsOf('payment_rows')"
          row-key="row_id"
          empty-text="暂无付款记录"
        >
          <template #cell-amount="{ row }">
            <AmountText
              :value="String(row.amount)"
              :currency="comparison!.currency"
              strong
            />
          </template>
          <template #cell-difference="{ row }">
            <AmountText
              :value="String(row.difference)"
              :currency="comparison!.currency"
            />
          </template>
          <template #cell-result="{ row }">
            <StatusBadge
              :label="resultOf(row).label"
              :tone="resultOf(row).tone"
              :dot="false"
            />
          </template>
          <template #cell-note="{ row }">
            <span class="muted">{{ row.note ?? '—' }}</span>
          </template>
        </DataTable>
      </section>

      <p
        class="compare-summary"
        :class="{ 'compare-summary-warn': mismatchCount > 0 }"
      >
        差异汇总：共 {{ mismatchCount }} 处不一致或缺失。金额核对基于同币种（{{ comparison.currency }}）Decimal 精确计算，不做汇率换算。
      </p>
    </template>
  </PageShell>
</template>

<style scoped>
.compare-summary {
  margin-top: 16px;
  font-size: 13px;
  line-height: 20px;
  color: var(--risk-low-text);
  background: var(--risk-low-bg);
  border-radius: var(--radius-input);
  padding: 12px 16px;
}

.compare-summary-warn {
  color: var(--risk-medium-text);
  background: var(--risk-medium-bg);
}
</style>
