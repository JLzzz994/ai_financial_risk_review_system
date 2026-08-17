<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { riskLevelView } from '@/types/status'

const props = defineProps<{
  level?: string | null
}>()

const view = computed(() => riskLevelView(props.level))
</script>

<template>
  <StatusBadge
    :label="view.label"
    :tone="view.tone"
  />
</template>
