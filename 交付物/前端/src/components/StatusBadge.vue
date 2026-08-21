<script setup lang="ts">
import { computed } from 'vue'
import type { StatusTone } from '@/types/status'

const props = defineProps<{
  label: string
  tone: StatusTone
  dot?: boolean
}>()

const toneClass = computed(() => `tone-${props.tone}`)
</script>

<template>
  <span
    class="pill status-badge"
    :class="toneClass"
  >
    <span
      v-if="dot !== false"
      class="dot"
    />
    {{ label }}
  </span>
</template>

<style scoped>
.status-badge {
  background: var(--tone-bg);
  color: var(--tone-fg);
}

.tone-gray {
  --tone-bg: var(--status-gray-bg);
  --tone-fg: var(--status-gray);
}

.tone-blue {
  --tone-bg: var(--status-blue-bg);
  --tone-fg: var(--status-blue);
}

.tone-green {
  --tone-bg: var(--status-green-bg);
  --tone-fg: var(--status-green);
}

.tone-orange {
  --tone-bg: var(--status-orange-bg);
  --tone-fg: var(--status-orange);
}

.tone-red {
  --tone-bg: var(--status-red-bg);
  --tone-fg: var(--status-red);
}

.tone-purple {
  --tone-bg: var(--status-purple-bg);
  --tone-fg: var(--status-purple);
}

.tone-gray .dot {
  background: var(--status-gray);
}

.tone-blue .dot {
  background: var(--status-blue);
}

.tone-green .dot {
  background: var(--risk-low);
}

.tone-orange .dot {
  background: var(--risk-medium);
}

.tone-red .dot {
  background: var(--risk-high);
}

.tone-purple .dot {
  background: var(--status-purple);
}
</style>
