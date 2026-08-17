<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    width?: string
  }>(),
  { width: '560px' },
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
    <Transition name="drawer">
      <div
        v-if="modelValue"
        class="drawer-root"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <div
          class="drawer-mask"
          @click="close"
        />
        <aside
          class="drawer"
          :style="{ width }"
        >
          <header class="drawer-header">
            <h2 class="drawer-title">
              {{ title }}
            </h2>
            <button
              type="button"
              class="drawer-close"
              aria-label="关闭"
              @click="close"
            >
              ×
            </button>
          </header>
          <div class="drawer-body">
            <slot />
          </div>
          <footer
            v-if="$slots.footer"
            class="drawer-footer"
          >
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-root {
  position: fixed;
  inset: 0;
  z-index: 500;
}

.drawer-mask {
  position: absolute;
  inset: 0;
  background: rgba(18, 59, 109, 0.32);
}

.drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  box-shadow: var(--shadow-float);
  display: flex;
  flex-direction: column;
  max-width: 92vw;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid var(--color-border);
}

.drawer-title {
  font-size: 18px;
  line-height: 24px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.drawer-close {
  border: none;
  background: none;
  font-size: 20px;
  color: var(--color-text-weak);
  cursor: pointer;
  line-height: 1;
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--color-border);
}

.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 160ms ease;
}

.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 200ms ease;
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(24px);
}
</style>
