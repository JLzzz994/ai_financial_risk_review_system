<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  listMarketPrices,
  listRules,
  listSupplierRules,
  listSystemParameters,
  patchMarketPrice,
  patchRule,
  patchSupplierRule,
  publishRule,
} from '@/api/rules'
import { handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { MarketPriceItem, RuleItem, SupplierRuleItem } from '@/types/domain'
import { configStatusView } from '@/types/status'
import { formatDate } from '@/utils/format'
import AmountText from '@/components/AmountText.vue'
import BaseModal from '@/components/BaseModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import DataTable from '@/components/DataTable.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageShell from '@/components/PageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'

const app = useAppStore()

type TabKey = 'rules' | 'market-prices' | 'supplier-rules' | 'system-parameters'

const activeTab = ref<TabKey>('rules')

const rules = ref<RuleItem[]>([])
const marketPrices = ref<MarketPriceItem[]>([])
const supplierRules = ref<SupplierRuleItem[]>([])
const systemParameters = ref<Array<{ key: string; value: string; description: string; updated_at: string }>>([])
const loading = ref(false)
const loadError = ref<string | null>(null)

const publishDialogOpen = ref(false)
const publishTarget = ref<RuleItem | null>(null)

const editPriceTarget = ref<MarketPriceItem | null>(null)
const editPriceValue = ref('')
const editPriceOpen = ref(false)

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'rules', label: '风险规则' },
  { key: 'market-prices', label: '市场价参考' },
  { key: 'supplier-rules', label: '供应商规则' },
  { key: 'system-parameters', label: '系统参数' },
]

const ruleTypeLabels: Record<string, string> = {
  amount: '金额类',
  duplicate: '重复类',
  completeness: '完整性',
  supplier: '供应商',
  behavior: '行为类',
}

const ruleColumns = [
  { key: 'rule_code', title: '编号', width: '9%' },
  { key: 'rule_name', title: '规则名称', width: '17%' },
  { key: 'rule_type', title: '类型', width: '8%' },
  { key: 'params', title: '参数', width: '27%' },
  { key: 'rule_version', title: '版本', width: '7%' },
  { key: 'hit_count_30d', title: '近30天命中', align: 'right' as const, width: '10%' },
  { key: 'status', title: '状态', width: '8%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

const priceColumns = [
  { key: 'category', title: '费用类别', width: '14%' },
  { key: 'item_name', title: '项目', width: '26%' },
  { key: 'unit', title: '单位', width: '8%' },
  { key: 'reference_price', title: '参考价', align: 'right' as const, width: '13%' },
  { key: 'source', title: '来源', width: '20%' },
  { key: 'effective_from', title: '生效日期', width: '11%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

const supplierRuleColumns = [
  { key: 'supplier_name', title: '供应商', width: '26%' },
  { key: 'rule_name', title: '规则', width: '24%' },
  { key: 'threshold', title: '阈值', align: 'right' as const, width: '16%' },
  { key: 'enabled', title: '启用', width: '10%' },
  { key: 'actions', title: '操作', align: 'right' as const },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [rulePage, prices, supplierRuleList, parameters] = await Promise.all([
      listRules({ page_size: 50 }),
      listMarketPrices(),
      listSupplierRules(),
      listSystemParameters().catch(() => []),
    ])
    rules.value = rulePage.items
    marketPrices.value = prices
    supplierRules.value = supplierRuleList
    systemParameters.value = parameters
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function toggleRule(rule: RuleItem): Promise<void> {
  try {
    await patchRule(rule.rule_id, { status: rule.status === 'published' ? 'disabled' : 'published' })
    app.push('success', `已${rule.status === 'published' ? '停用' : '启用'}规则 ${rule.rule_code}`)
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

function askPublish(rule: RuleItem): void {
  publishTarget.value = rule
  publishDialogOpen.value = true
}

async function confirmPublish(reason: string): Promise<void> {
  if (!publishTarget.value) return
  try {
    const updated = await publishRule(publishTarget.value.rule_id, reason)
    app.push('success', `已发布规则 ${updated.rule_code} ${updated.rule_version}`)
    publishDialogOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

function askEditPrice(item: MarketPriceItem): void {
  editPriceTarget.value = item
  editPriceValue.value = item.reference_price
  editPriceOpen.value = true
}

async function confirmEditPrice(): Promise<void> {
  if (!editPriceTarget.value) return
  if (!/^\d+(\.\d{1,2})?$/.test(editPriceValue.value.trim())) {
    app.push('warning', '参考价格式不正确（最多两位小数）')
    return
  }
  try {
    await patchMarketPrice(editPriceTarget.value.id, editPriceValue.value.trim())
    app.push('success', '参考价已更新')
    editPriceOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

async function toggleSupplierRule(item: SupplierRuleItem): Promise<void> {
  try {
    await patchSupplierRule(item.id, !item.enabled)
    app.push('success', `已${item.enabled ? '停用' : '启用'}：${item.rule_name}`)
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

function paramsText(rule: RuleItem): string {
  return Object.entries(rule.params)
    .map(([key, value]) => `${key}=${value}`)
    .join('　')
}

onMounted(load)
</script>

<template>
  <PageShell
    title="规则中心"
    description="风险规则、市场价参考、供应商规则与系统参数（配置变更全部版本化并写入审计）"
  >
    <div class="rule-version-banner">
      <span class="rule-version-title">当前规则版本 v3.2</span>
      <span class="muted">风险判断由确定性规则引擎负责；LLM 仅做解释与建议，规则变更需发布新版本并回归评估。</span>
    </div>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <div
      v-if="!loadError"
      class="card"
    >
      <div
        class="tabs"
        role="tablist"
      >
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          role="tab"
          class="tab"
          :class="{ active: activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 风险规则 -->
      <DataTable
        v-if="activeTab === 'rules'"
        :columns="ruleColumns"
        :rows="rules as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        row-key="rule_id"
        empty-text="暂无规则"
        @retry="load"
      >
        <template #cell-rule_code="{ row }">
          <span class="mono">{{ row.rule_code }}</span>
        </template>
        <template #cell-rule_type="{ row }">
          {{ ruleTypeLabels[String(row.rule_type)] ?? row.rule_type }}
        </template>
        <template #cell-params="{ row }">
          <span class="mono params-text">{{ paramsText(row as unknown as RuleItem) }}</span>
        </template>
        <template #cell-rule_version="{ row }">
          <span class="mono">{{ row.rule_version }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusBadge v-bind="configStatusView(String(row.status))" />
        </template>
        <template #cell-actions="{ row }">
          <button
            type="button"
            class="btn-link"
            @click="toggleRule(row as unknown as RuleItem)"
          >
            {{ row.status === 'published' ? '停用' : '启用' }}
          </button>
          <button
            type="button"
            class="btn-link"
            @click="askPublish(row as unknown as RuleItem)"
          >
            发布新版本
          </button>
        </template>
      </DataTable>

      <!-- 市场价参考 -->
      <DataTable
        v-else-if="activeTab === 'market-prices'"
        :columns="priceColumns"
        :rows="marketPrices as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        row-key="id"
        empty-text="暂无市场价参考"
        @retry="load"
      >
        <template #cell-reference_price="{ row }">
          <AmountText
            :value="String(row.reference_price)"
            strong
          />
        </template>
        <template #cell-effective_from="{ row }">
          <span class="muted">{{ formatDate(String(row.effective_from)) }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            type="button"
            class="btn-link"
            @click="askEditPrice(row as unknown as MarketPriceItem)"
          >
            更新参考价
          </button>
        </template>
      </DataTable>

      <!-- 供应商规则 -->
      <DataTable
        v-else-if="activeTab === 'supplier-rules'"
        :columns="supplierRuleColumns"
        :rows="supplierRules as unknown as Array<Record<string, unknown>>"
        :loading="loading"
        row-key="id"
        empty-text="暂无供应商规则"
        @retry="load"
      >
        <template #cell-threshold="{ row }">
          <AmountText
            :value="String(row.threshold)"
            strong
          />
        </template>
        <template #cell-enabled="{ row }">
          <StatusBadge
            :label="row.enabled ? '已启用' : '已停用'"
            :tone="row.enabled ? 'green' : 'gray'"
            :dot="false"
          />
        </template>
        <template #cell-actions="{ row }">
          <button
            type="button"
            class="btn-link"
            @click="toggleSupplierRule(row as unknown as SupplierRuleItem)"
          >
            {{ row.enabled ? '停用' : '启用' }}
          </button>
          <RouterLink
            :to="`/suppliers/${row.supplier_code}/risks`"
            class="btn-link"
          >
            查看供应商
          </RouterLink>
        </template>
      </DataTable>

      <!-- 系统参数 -->
      <div
        v-else
        class="param-list"
      >
        <p
          v-if="systemParameters.length === 0 && !loading"
          class="weak"
        >
          暂无系统参数。
        </p>
        <div
          v-for="parameter in systemParameters"
          :key="parameter.key"
          class="param-item"
        >
          <span class="mono param-key">{{ parameter.key }}</span>
          <span class="param-desc">{{ parameter.description }}</span>
          <span class="param-value">{{ parameter.value }}</span>
        </div>
      </div>
    </div>

    <ConfirmDialog
      v-model="publishDialogOpen"
      title="发布规则新版本"
      :message="`确认发布规则「${publishTarget?.rule_name ?? ''}」的新版本？发布后立即对后续分析生效。`"
      confirm-text="确认发布"
      require-reason
      reason-label="发布说明"
      @confirm="confirmPublish"
    />

    <BaseModal
      :model-value="editPriceOpen"
      :title="`更新参考价 · ${editPriceTarget?.item_name ?? ''}`"
      width="420px"
      @update:model-value="editPriceOpen = $event"
    >
      <p class="price-edit-note">
        参考价用于市场价偏离规则（PRICE-007），更新后对后续分析生效。
      </p>
      <div class="field">
        <label for="price-input">参考价（CNY / {{ editPriceTarget?.unit ?? '单位' }}）</label>
        <input
          id="price-input"
          v-model="editPriceValue"
          class="input"
          inputmode="decimal"
          placeholder="0.00"
        >
      </div>
      <template #footer>
        <button
          type="button"
          class="btn btn-secondary"
          @click="editPriceOpen = false"
        >
          取消
        </button>
        <button
          type="button"
          class="btn btn-primary"
          @click="confirmEditPrice"
        >
          更新参考价
        </button>
      </template>
    </BaseModal>
  </PageShell>
</template>

<style scoped>
.rule-version-banner {
  display: flex;
  align-items: baseline;
  gap: 14px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 14px 20px;
  margin-bottom: 16px;
  font-size: 13px;
  flex-wrap: wrap;
}

.rule-version-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 16px;
  overflow-x: auto;
}

.tab {
  border: none;
  background: none;
  font-family: inherit;
  font-size: 14px;
  color: var(--color-text-secondary);
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}

.tab:hover {
  color: var(--color-primary);
}

.tab.active {
  color: var(--color-primary);
  font-weight: 600;
  border-bottom-color: var(--color-primary);
}

.params-text {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.param-list {
  display: flex;
  flex-direction: column;
}

.param-item {
  display: grid;
  grid-template-columns: 220px 1fr 140px;
  gap: 12px;
  padding: 12px 2px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
  align-items: center;
}

.param-item:last-child {
  border-bottom: none;
}

.param-key {
  color: var(--color-text);
}

.param-desc {
  color: var(--color-text-weak);
  font-size: 12px;
}

.param-value {
  font-weight: 600;
  color: var(--color-brand-deep);
  text-align: right;
}

.price-edit-note {
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
  margin-bottom: 14px;
}
</style>
