<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    hint?: string
    tone?: 'default' | 'risk-high' | 'risk-medium' | 'risk-low' | 'primary'
  }>(),
  { tone: 'default' },
)
</script>

<template>
  <div
    class="card metric-card"
    :class="`metric-${tone}`"
  >
    <span class="metric-label">{{ label }}</span>
    <span class="metric-value">{{ value }}</span>
    <span
      v-if="hint"
      class="metric-hint"
    >{{ hint }}</span>
  </div>
</template>

<style scoped>
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px;
}

.metric-label {
  font-size: 14px;
  line-height: 19px;
  color: var(--color-text-secondary);
}

.metric-value {
  font-size: 26px;
  line-height: 35px;
  font-weight: 600;
  color: var(--color-brand-deep);
  font-variant-numeric: tabular-nums;
}

.metric-hint {
  font-size: 12px;
  line-height: 16px;
  color: var(--color-text-weak);
}

.metric-risk-high .metric-value {
  color: var(--risk-high-text);
}

.metric-risk-medium .metric-value {
  color: var(--risk-medium-text);
}

.metric-risk-low .metric-value {
  color: var(--risk-low-text);
}

.metric-primary .metric-value {
  color: var(--color-primary);
}
</style>
