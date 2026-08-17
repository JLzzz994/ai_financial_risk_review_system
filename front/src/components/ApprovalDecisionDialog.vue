<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, handleApiError, safeErrorMessage } from '@/api/client'
import { submitDecision, type DecisionValue } from '@/api/approval-tasks'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { ApprovalTask } from '@/types/domain'
import { approvalDecisionMap } from '@/types/status'
import { formatMoney } from '@/utils/format'
import BaseModal from './BaseModal.vue'
import RiskLevelTag from './RiskLevelTag.vue'

const props = defineProps<{
  modelValue: boolean
  task: ApprovalTask | null
  /** 打开时预设的决定（如详情页「退回 / 审批通过」按钮） */
  preset?: 'approve' | 'return' | 'reject' | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  decided: [task: ApprovalTask]
  'open-risk': [documentId: string]
}>()

const auth = useAuthStore()
const app = useAppStore()

const decision = ref<DecisionValue | null>(null)
const comment = ref('')
const commentError = ref('')
const submitting = ref(false)
let idempotencyKey = ''

const isAssignee = computed(
  () => props.task?.assignee_id === auth.principal?.user_id,
)
const canSubmit = computed(
  () =>
    decision.value !== null &&
    comment.value.trim().length > 0 &&
    isAssignee.value &&
    props.task?.task_status === 'pending' &&
    !submitting.value,
)

const decisionMeta = computed(() => {
  switch (decision.value) {
    case 'approve':
      return {
        title: '确认审批通过',
        text: `确认通过「${props.task?.document_no}」？通过后单据将进入下一审批节点。`,
        button: '确认通过',
        danger: false,
      }
    case 'return':
      return {
        title: '确认退回修改',
        text: `确认退回「${props.task?.document_no}」？申请人修改后重新提交将生成新版本，历史记录保留。`,
        button: '确认退回',
        danger: false,
      }
    case 'reject':
      return {
        title: '确认驳回',
        text: `确认驳回「${props.task?.document_no}」？驳回后本单流程终止，且不可恢复。`,
        button: '确认驳回',
        danger: true,
      }
    default:
      return null
  }
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      decision.value = props.preset ?? null
      comment.value = ''
      commentError.value = ''
      submitting.value = false
      // 同一弹窗会话内重试复用同一幂等键，避免重复提交
      idempotencyKey = crypto.randomUUID()
    }
  },
)

function choose(value: DecisionValue): void {
  decision.value = value
  commentError.value = ''
}

function validateComment(): boolean {
  if (!comment.value.trim()) {
    commentError.value = '审批意见必填（通过 / 退回 / 驳回均需填写）'
    return false
  }
  commentError.value = ''
  return true
}

function close(): void {
  if (submitting.value) return
  emit('update:modelValue', false)
}

async function handleConfirm(): Promise<void> {
  if (!props.task || !decision.value) return
  if (!validateComment()) return
  submitting.value = true
  try {
    const updated = await submitDecision(props.task.task_id, {
      decision: decision.value,
      review_comment: comment.value.trim(),
    }, idempotencyKey)
    app.push('success', `已提交决定：${approvalDecisionMap[decision.value].label}`)
    emit('decided', updated)
    emit('update:modelValue', false)
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      // 任务已被处理：提示并关闭，由父组件刷新
      emit('update:modelValue', false)
    }
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="task ? `审批决定 · ${task.document_no}` : '审批决定'"
    width="560px"
    @update:model-value="close"
  >
    <template v-if="task">
      <!-- 风险摘要：决定前必须可见 -->
      <section
        class="risk-summary"
        aria-label="风险摘要"
      >
        <div class="risk-summary-row">
          <span class="risk-summary-label">单据金额</span>
          <span class="risk-summary-value">{{ formatMoney(task.total_amount, task.currency) }}</span>
        </div>
        <div class="risk-summary-row">
          <span class="risk-summary-label">整体风险</span>
          <RiskLevelTag :level="task.overall_risk_level" />
        </div>
        <div class="risk-summary-row">
          <span class="risk-summary-label">未处理风险</span>
          <span
            class="risk-summary-value"
            :class="{ 'risk-pending': task.pending_finding_count > 0 }"
          >
            {{ task.pending_finding_count }} 条
          </span>
          <button
            type="button"
            class="btn-link"
            @click="emit('open-risk', task.document_id)"
          >
            查看风险与证据
          </button>
        </div>
        <p class="risk-summary-note">
          AI 结果仅为辅助参考，最终通过 / 退回 / 驳回由审批人员决定。
        </p>
      </section>

      <div
        v-if="!isAssignee"
        class="assignee-warning"
        role="alert"
      >
        当前任务未分配给你，不能提交决定。
      </div>
      <div
        v-else-if="task.task_status !== 'pending'"
        class="assignee-warning"
        role="alert"
      >
        该任务当前状态为「{{ task.task_status }}」，不能重复处理。
      </div>

      <!-- 三种决定：不同文案与颜色 -->
      <fieldset
        class="decision-picker"
        :disabled="!isAssignee || task.task_status !== 'pending'"
      >
        <legend class="decision-legend">
          选择审批决定
        </legend>
        <div class="decision-options">
          <button
            v-for="(meta, value) in approvalDecisionMap"
            :key="value"
            type="button"
            class="decision-option"
            :class="[`decision-${value}`, { selected: decision === value }]"
            @click="choose(value)"
          >
            <span class="decision-option-dot" />
            <span class="decision-option-label">{{ meta.label }}</span>
          </button>
        </div>
      </fieldset>

      <div
        v-if="decisionMeta"
        class="decision-confirm-text"
        :class="{ 'decision-confirm-danger': decisionMeta.danger }"
      >
        {{ decisionMeta.text }}
      </div>

      <div class="field">
        <label for="decision-comment">审批意见 <span class="field-required" /></label>
        <textarea
          id="decision-comment"
          v-model="comment"
          class="textarea"
          rows="3"
          placeholder="请填写审批意见（必填），将随审计记录留存"
          :aria-invalid="commentError ? 'true' : undefined"
          :disabled="!isAssignee || task.task_status !== 'pending'"
          @blur="validateComment"
        />
        <span
          v-if="commentError"
          class="field-error"
        >{{ commentError }}</span>
      </div>
    </template>
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
        :class="decisionMeta?.danger ? 'btn-danger' : 'btn-primary'"
        :disabled="!canSubmit"
        @click="handleConfirm"
      >
        {{ submitting ? '提交中…' : decisionMeta?.button ?? '提交决定' }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.risk-summary {
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-btn);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.risk-summary-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.risk-summary-label {
  width: 76px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.risk-summary-value {
  font-weight: 600;
  color: var(--color-text);
}

.risk-pending {
  color: var(--risk-high-text);
}

.risk-summary-note {
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-weak);
  border-top: 1px dashed var(--color-border);
  padding-top: 8px;
}

.assignee-warning {
  margin-top: 14px;
  background: var(--risk-high-bg);
  color: var(--risk-high-text);
  border: 1px solid rgba(240, 68, 56, 0.35);
  border-radius: var(--radius-btn);
  padding: 10px 14px;
  font-size: 13px;
}

.decision-picker {
  border: none;
  margin: 18px 0 0;
  padding: 0;
}

.decision-legend {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 0;
  margin-bottom: 10px;
}

.decision-options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.decision-option {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--color-card);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-btn);
  padding: 12px 10px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}

.decision-option-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.decision-approve.selected {
  border-color: var(--risk-low);
  background: var(--risk-low-bg);
  color: var(--risk-low-text);
}

.decision-approve.selected .decision-option-dot {
  background: var(--risk-low);
}

.decision-return.selected {
  border-color: var(--risk-medium);
  background: var(--risk-medium-bg);
  color: var(--risk-medium-text);
}

.decision-return.selected .decision-option-dot {
  background: var(--risk-medium);
}

.decision-reject.selected {
  border-color: var(--risk-high);
  background: var(--risk-high-bg);
  color: var(--risk-high-text);
}

.decision-reject.selected .decision-option-dot {
  background: var(--risk-high);
}

.decision-confirm-text {
  margin-top: 14px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text);
  background: var(--color-selected);
  border-radius: var(--radius-input);
  padding: 10px 14px;
}

.decision-confirm-danger {
  background: var(--risk-high-bg);
  color: var(--risk-high-text);
}

.field {
  margin-top: 16px;
}
</style>
