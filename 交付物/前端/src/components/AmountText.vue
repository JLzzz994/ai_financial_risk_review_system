<script setup lang="ts">
import { formatMoney } from '@/utils/format'

withDefaults(
  defineProps<{
    value?: string | number | null
    currency?: string
    strong?: boolean
  }>(),
  { value: null, currency: 'CNY', strong: false },
)
</script>

<template>
  <span
    class="amount"
    :class="{ strong }"
  >{{ formatMoney(value, currency) }}</span>
</template>

<style scoped>
.amount {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.strong {
  font-weight: 600;
  color: var(--color-brand-deep);
}
</style>
