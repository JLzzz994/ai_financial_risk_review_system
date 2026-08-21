<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div class="page-header-text">
        <h1>{{ title }}</h1>
        <p
          v-if="description"
          class="page-desc"
        >
          {{ description }}
        </p>
        <slot name="header-extra" />
      </div>
      <div class="page-actions">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.page-header-text {
  min-width: 0;
}
</style>
