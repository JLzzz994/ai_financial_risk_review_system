<script setup lang="ts">
const isDev = import.meta.env.DEV

defineProps<{ text: string }>()
</script>

<template>
  <span
    v-if="isDev"
    class="api-hint"
    :title="text"
  >{{ text }}</span>
</template>
