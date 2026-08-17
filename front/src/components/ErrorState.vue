<script setup lang="ts">
defineProps<{ message?: string }>()

const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div
    class="card error-state"
    role="alert"
  >
    <p class="error-title">
      无法加载内容
    </p>
    <p class="error-desc">
      {{ message ?? '请求未完成，请稍后重试。' }}
    </p>
    <button
      type="button"
      class="btn btn-secondary"
      @click="emit('retry')"
    >
      重新加载
    </button>
  </div>
</template>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
}

.error-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.error-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}
</style>
