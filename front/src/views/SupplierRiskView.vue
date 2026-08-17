<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getSupplierRisk } from '@/api/suppliers'
import { safeErrorMessage } from '@/api/client'
import type { SupplierRisk } from '@/types/domain'
import { formatDate, formatMoney } from '@/utils/format'
import ApiHint from '@/components/ApiHint.vue'
import ErrorState from '@/components/ErrorState.vue'
import MetricCard from '@/components/MetricCard.vue'
import PageShell from '@/components/PageShell.vue'
import RiskLevelTag from '@/components/RiskLevelTag.vue'

const route = useRoute()
const supplierId = computed(() => String(route.params.id))

const supplier = ref<SupplierRisk | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    supplier.value = await getSupplierRisk(supplierId.value)
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageShell
    :title="`供应商风险 · ${supplier?.supplier_name ?? ''}`"
    description="供应商标签、黑名单状态、历史付款与异常记录"
  >
    <template #actions>
      <div class="row">
        <ApiHint text="GET /api/v1/suppliers/{supplier_code}/risks" />
        <RiskLevelTag :level="supplier?.risk_status" />
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <template v-if="supplier">
      <section
        class="grid grid-4"
        aria-label="供应商指标"
      >
        <MetricCard
          label="历史付款笔数"
          :value="supplier.payment_count"
          tone="primary"
        />
        <MetricCard
          label="累计付款金额"
          :value="formatMoney(supplier.total_paid)"
        />
        <MetricCard
          label="异常记录"
          :value="supplier.anomalies.length"
          tone="risk-medium"
        />
        <MetricCard
          label="黑名单"
          :value="supplier.blacklisted ? '是' : '否'"
          :tone="supplier.blacklisted ? 'risk-high' : 'risk-low'"
          :hint="supplier.blacklisted ? supplier.blacklist_reason : '未列入黑名单'"
        />
      </section>

      <section class="card">
        <h2 class="card-title">
          供应商信息
        </h2>
        <dl class="supplier-grid">
          <div class="supplier-item">
            <dt>供应商名称</dt><dd>{{ supplier.supplier_name }}</dd>
          </div>
          <div class="supplier-item">
            <dt>供应商编码</dt><dd class="mono">
              {{ supplier.supplier_code }}
            </dd>
          </div>
          <div class="supplier-item">
            <dt>风险等级</dt><dd><RiskLevelTag :level="supplier.risk_status" /></dd>
          </div>
          <div class="supplier-item">
            <dt>最近付款</dt><dd>{{ supplier.last_payment_at ? formatDate(supplier.last_payment_at) : '—' }}</dd>
          </div>
        </dl>
        <div class="tag-row">
          <span class="tag-row-label">风险标签</span>
          <div class="tag-list">
            <span
              v-for="tag in supplier.tags"
              :key="tag"
              class="pill supplier-tag"
            >{{ tag }}</span>
            <span
              v-if="supplier.tags.length === 0"
              class="weak"
            >无标签</span>
          </div>
        </div>
        <div
          v-if="supplier.blacklisted"
          class="blacklist-banner"
          role="alert"
        >
          该供应商已列入黑名单：{{ supplier.blacklist_reason ?? '命中黑名单规则' }}。相关单据将被拦截，需人工处理。
        </div>
      </section>

      <section class="card">
        <div class="card-title">
          <span>异常记录</span>
          <span class="card-title-sub">按时间倒序</span>
        </div>
        <ol class="anomaly-list">
          <li
            v-for="anomaly in supplier.anomalies"
            :key="anomaly.document_no"
            class="anomaly-item"
          >
            <span class="anomaly-dot" />
            <div class="anomaly-body">
              <div class="anomaly-head">
                <span class="anomaly-type">{{ anomaly.type }}</span>
                <RouterLink
                  :to="`/documents/${anomaly.document_no}`"
                  class="anomaly-doc"
                >
                  {{ anomaly.document_no }}
                </RouterLink>
                <span class="anomaly-date muted">{{ anomaly.occurred_at }}</span>
              </div>
              <p class="anomaly-desc">
                {{ anomaly.description }}
              </p>
            </div>
          </li>
        </ol>
        <p
          v-if="supplier.anomalies.length === 0"
          class="weak anomaly-empty"
        >
          近 12 个月无异常记录。
        </p>
      </section>
    </template>
  </PageShell>
</template>

<style scoped>
.supplier-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px 20px;
  margin: 0;
}

.supplier-item dt {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-bottom: 5px;
}

.supplier-item dd {
  margin: 0;
  font-size: 14px;
  color: var(--color-text);
}

.tag-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--color-border);
}

.tag-row-label {
  font-size: 12px;
  color: var(--color-text-weak);
  line-height: 24px;
  flex-shrink: 0;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.supplier-tag {
  background: var(--risk-medium-bg);
  color: var(--risk-medium-text);
}

.blacklist-banner {
  margin-top: 16px;
  background: var(--risk-high-bg);
  border: 1px solid rgba(240, 68, 56, 0.35);
  border-radius: var(--radius-btn);
  color: var(--risk-high-text);
  font-size: 13px;
  line-height: 20px;
  padding: 12px 16px;
}

.anomaly-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.anomaly-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}

.anomaly-item:last-child {
  border-bottom: none;
}

.anomaly-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--risk-medium);
  flex-shrink: 0;
  margin-top: 5px;
}

.anomaly-body {
  flex: 1;
  min-width: 0;
}

.anomaly-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.anomaly-type {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.anomaly-doc {
  font-size: 12px;
}

.anomaly-date {
  font-size: 12px;
}

.anomaly-desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
}

.anomaly-empty {
  padding: 12px 0;
}

@media (max-width: 1100px) {
  .supplier-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
