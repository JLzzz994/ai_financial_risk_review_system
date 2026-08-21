<script setup lang="ts">
export interface TableColumn {
  key: string
  title: string
  width?: string
  align?: 'left' | 'right' | 'center'
}

withDefaults(
  defineProps<{
    columns: TableColumn[]
    rows: Array<Record<string, unknown>>
    loading?: boolean
    error?: string | null
    emptyText?: string
    rowKey?: string
  }>(),
  { loading: false, error: null, emptyText: '暂无数据', rowKey: 'id' },
)

const emit = defineEmits<{ retry: [] }>()

function slotName(key: string): string {
  return `cell-${key}`
}
</script>

<template>
  <div class="table-wrap">
    <table
      class="table"
      :aria-busy="loading"
    >
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :style="{ width: column.width, textAlign: column.align ?? 'left' }"
          >
            {{ column.title }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td
            v-for="column in columns"
            :key="column.key"
          >
            <span class="skeleton" />
          </td>
        </tr>
        <tr v-else-if="error">
          <td :colspan="columns.length">
            <div class="state">
              <p class="state-title">
                加载失败
              </p>
              <p class="state-desc">
                {{ error }}
              </p>
              <button
                type="button"
                class="btn btn-secondary btn-sm"
                @click="emit('retry')"
              >
                重试
              </button>
            </div>
          </td>
        </tr>
        <tr v-else-if="rows.length === 0">
          <td :colspan="columns.length">
            <div class="state">
              <p class="state-title">
                {{ emptyText }}
              </p>
              <p class="state-desc">
                当前筛选条件下没有记录
              </p>
            </div>
          </td>
        </tr>
        <tr
          v-for="(row, index) in rows"
          v-else
          :key="String(row[rowKey] ?? index)"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            :style="{ textAlign: column.align ?? 'left' }"
            :class="{
              'cell-money': column.align === 'right',
              'cell-center': column.align === 'center',
            }"
          >
            <slot
              :name="slotName(column.key)"
              :row="row"
              :index="index"
            >
              {{ row[column.key] ?? '—' }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.skeleton {
  display: inline-block;
  width: 72%;
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #eef2f8 25%, #f7fafd 45%, #eef2f8 65%);
  background-size: 200% 100%;
  animation: skeleton-wave 1.2s ease infinite;
}

@keyframes skeleton-wave {
  from {
    background-position: 200% 0;
  }
}

.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 28px 0;
}

.state-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.state-desc {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-bottom: 4px;
}
</style>
