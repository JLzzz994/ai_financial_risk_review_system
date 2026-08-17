<script setup lang="ts">
import { ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    message: string
    confirmText?: string
    tone?: 'primary' | 'danger'
    requireReason?: boolean
    reasonLabel?: string
    reasonPlaceholder?: string
  }>(),
  {
    confirmText: '确认',
    tone: 'primary',
    requireReason: false,
    reasonLabel: '操作原因',
    reasonPlaceholder: '请填写原因（必填）',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [reason: string]
}>()

const reason = ref('')
const reasonError = ref('')
const submitting = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      reason.value = ''
      reasonError.value = ''
      submitting.value = false
    }
  },
)

function handleConfirm(): void {
  if (props.requireReason && !reason.value.trim()) {
    reasonError.value = '请填写原因后再继续'
    return
  }
  submitting.value = true
  emit('confirm', reason.value.trim())
}

function close(): void {
  if (submitting.value) return
  emit('update:modelValue', false)
}

defineExpose({
  /** 请求结束后由父组件调用，解除按钮锁定 */
  done(): void {
    submitting.value = false
  },
})
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="title"
    width="440px"
    @update:model-value="close"
  >
    <p class="confirm-message">
      {{ message }}
    </p>
    <div
      v-if="requireReason"
      class="field"
    >
      <label for="confirm-reason">{{ reasonLabel }}</label>
      <textarea
        id="confirm-reason"
        v-model="reason"
        class="textarea"
        :placeholder="reasonPlaceholder"
        :aria-invalid="reasonError ? 'true' : undefined"
        rows="3"
      />
      <span
        v-if="reasonError"
        class="field-error"
      >{{ reasonError }}</span>
    </div>
    <template #footer>
      <button
        type="button"
        class="btn btn-secondary"
        :disabled="submitting"
        @click="close"
      >
        取消
      </button>
      <button
        type="button"
        class="btn"
        :class="tone === 'danger' ? 'btn-danger' : 'btn-primary'"
        :disabled="submitting"
        @click="handleConfirm"
      >
        {{ submitting ? '提交中…' : confirmText }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.confirm-message {
  font-size: 14px;
  line-height: 22px;
  color: var(--color-text);
}
</style>
