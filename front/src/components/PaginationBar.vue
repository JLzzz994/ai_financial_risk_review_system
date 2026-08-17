<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    page: number
    pageSize: number
    total: number
  }>(),
  { page: 1, pageSize: 50, total: 0 },
)

const emit = defineEmits<{ 'update:page': [page: number] }>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const rangeStart = computed(() => (props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1))
const rangeEnd = computed(() => Math.min(props.page * props.pageSize, props.total))

function go(page: number): void {
  if (page < 1 || page > totalPages.value || page === props.page) return
  emit('update:page', page)
}
</script>

<template>
  <div class="pagination">
    <span class="pagination-info">
      第 {{ rangeStart }}–{{ rangeEnd }} 条，共 {{ total }} 条
    </span>
    <div class="pagination-controls">
      <button
        type="button"
        class="btn btn-secondary btn-sm"
        :disabled="page <= 1"
        @click="go(page - 1)"
      >
        上一页
      </button>
      <span class="pagination-page">{{ page }} / {{ totalPages }}</span>
      <button
        type="button"
        class="btn btn-secondary btn-sm"
        :disabled="page >= totalPages"
        @click="go(page + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 14px;
  flex-wrap: wrap;
}

.pagination-info {
  font-size: 12px;
  color: var(--color-text-weak);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pagination-page {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
