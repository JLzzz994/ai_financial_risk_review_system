<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    width?: string
  }>(),
  { width: '520px' },
)

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

function close(): void {
  emit('update:modelValue', false)
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-root"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <div
          class="modal-mask"
          @click="close"
        />
        <div
          class="modal"
          :style="{ width }"
        >
          <header class="modal-header">
            <h2 class="modal-title">
              {{ title }}
            </h2>
            <button
              type="button"
              class="modal-close"
              aria-label="关闭"
              @click="close"
            >
              ×
            </button>
          </header>
          <div class="modal-body">
            <slot />
          </div>
          <footer
            v-if="$slots.footer"
            class="modal-footer"
          >
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-root {
  position: fixed;
  inset: 0;
  z-index: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal-mask {
  position: absolute;
  inset: 0;
  background: rgba(18, 59, 109, 0.32);
}

.modal {
  position: relative;
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-float);
  display: flex;
  flex-direction: column;
  max-width: 94vw;
  max-height: 88vh;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px 0;
}

.modal-title {
  font-size: 18px;
  line-height: 24px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.modal-close {
  border: none;
  background: none;
  font-size: 20px;
  color: var(--color-text-weak);
  cursor: pointer;
  line-height: 1;
}

.modal-body {
  padding: 16px 24px 20px;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 0 24px 20px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 160ms ease;
}

.modal-enter-active .modal,
.modal-leave-active .modal {
  transition: transform 200ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal,
.modal-leave-to .modal {
  transform: translateY(10px) scale(0.98);
}
</style>
