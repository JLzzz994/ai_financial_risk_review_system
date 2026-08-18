<script setup lang="ts">
const isApiHintsEnabled = import.meta.env.VITE_SHOW_API_HINTS === 'true'

defineProps<{ text: string }>()
</script>

<template>
  <span
    v-if="isApiHintsEnabled"
    class="api-hint"
    :title="text"
  >{{ text }}</span>
</template>
