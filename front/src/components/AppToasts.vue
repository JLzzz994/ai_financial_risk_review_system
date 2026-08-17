<script setup lang="ts">
import { useAppStore } from '@/stores/app'

const app = useAppStore()
</script>

<template>
  <div
    class="toasts"
    aria-live="polite"
  >
    <div
      v-for="toast in app.toasts"
      :key="toast.id"
      class="toast"
      :class="`toast-${toast.type}`"
      role="status"
    >
      <span class="toast-dot" />
      <span class="toast-message">{{ toast.message }}</span>
      <button
        type="button"
        class="toast-close"
        aria-label="关闭提示"
        @click="app.remove(toast.id)"
      >
        ×
      </button>
    </div>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  top: 68px;
  right: 24px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 420px;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-btn);
  box-shadow: var(--shadow-float);
  padding: 12px 14px;
  font-size: 13px;
  line-height: 18px;
  animation: toast-in 200ms ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
}

.toast-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.toast-success .toast-dot {
  background: var(--risk-low);
}

.toast-error .toast-dot {
  background: var(--risk-high);
}

.toast-warning .toast-dot {
  background: var(--risk-medium);
}

.toast-info .toast-dot {
  background: var(--status-blue);
}

.toast-message {
  flex: 1;
  color: var(--color-text);
  word-break: break-all;
}

.toast-close {
  border: none;
  background: none;
  color: var(--color-text-weak);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
}
</style>
