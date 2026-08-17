<script setup lang="ts">
import type { StatusTone } from '@/types/status'
import StatusBadge from './StatusBadge.vue'
import { analysisStageMap, ANALYSIS_STAGE_ORDER } from '@/types/status'
import type { AnalysisTask } from '@/types/domain'
import { computed } from 'vue'

const props = defineProps<{
  task: AnalysisTask | null
  /** SSE 连接状态（由父组件维护） */
  streamState?: 'connecting' | 'open' | 'reconnecting' | 'closed'
}>()

const emit = defineEmits<{ retry: []; resume: [] }>()

const steps = computed(() =>
  ANALYSIS_STAGE_ORDER.map((stage) => ({
    stage,
    label: analysisStageMap[stage].label,
    state: stepState(stage),
  })),
)

function stepState(stage: string): 'done' | 'current' | 'pending' | 'failed' {
  if (!props.task) return 'pending'
  if (props.task.stage === 'failed') {
    return stage === 'analyzing' ? 'failed' : 'done'
  }
  const order = ANALYSIS_STAGE_ORDER
  const current = order.indexOf(props.task.stage as (typeof order)[number])
  const target = order.indexOf(stage as (typeof order)[number])
  if (current < 0) return 'pending'
  if (target < current) return 'done'
  if (target === current) return stage === 'succeeded' ? 'done' : 'current'
  return 'pending'
}
</script>

<template>
  <div class="task-progress">
    <ol
      v-if="task"
      class="steps"
    >
      <li
        v-for="step in steps"
        :key="step.stage"
        class="step"
        :class="`step-${step.state}`"
      >
        <span class="step-dot" />
        <span class="step-label">{{ step.label }}</span>
      </li>
    </ol>
    <div class="task-meta">
      <StatusBadge
        :label="analysisStageMap[task?.stage as keyof typeof analysisStageMap]?.label ?? '未知'"
        :tone="(analysisStageMap[task?.stage as keyof typeof analysisStageMap]?.tone ?? 'gray') as StatusTone"
        :dot="false"
      />
      <span
        v-if="streamState === 'open'"
        class="stream-hint stream-live"
      >实时推送中</span>
      <span
        v-else-if="streamState === 'reconnecting'"
        class="stream-hint stream-reconnecting"
      >
        连接中断
        <button
          type="button"
          class="btn-link"
          @click="emit('resume')"
        >恢复</button>
      </span>
      <span
        v-if="task?.stage === 'failed'"
        class="stream-hint stream-failed"
      >
        {{ task.error_message ?? '自动重试已达上限' }}
        <template v-if="task.manual_takeover">，已转人工接管</template>
      </span>
      <button
        v-if="task?.stage === 'failed'"
        type="button"
        class="btn btn-secondary btn-sm"
        @click="emit('retry')"
      >
        重试任务
      </button>
    </div>
  </div>
</template>

<style scoped>
.task-progress {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.steps {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 0;
  padding: 0;
  margin: 0;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-right: 16px;
  position: relative;
}

.step:not(:last-child)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 50%;
  width: 12px;
  height: 1px;
  background: var(--color-border);
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--color-border-strong);
}

.step-label {
  font-size: 12px;
  color: var(--color-text-weak);
  white-space: nowrap;
}

.step-done .step-dot {
  background: var(--risk-low);
}

.step-done .step-label {
  color: var(--risk-low-text);
}

.step-current .step-dot {
  background: var(--status-blue);
  box-shadow: 0 0 0 3px var(--status-blue-bg);
}

.step-current .step-label {
  color: var(--status-blue);
  font-weight: 600;
}

.step-failed .step-dot {
  background: var(--risk-high);
}

.step-failed .step-label {
  color: var(--risk-high-text);
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.stream-hint {
  font-size: 12px;
  color: var(--color-text-weak);
}

.stream-live::before {
  content: '';
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--risk-low);
  margin-right: 6px;
  animation: pulse 1.6s ease infinite;
}

.stream-reconnecting {
  color: var(--risk-medium-text);
}

.stream-failed {
  color: var(--risk-high-text);
}

@keyframes pulse {
  50% {
    opacity: 0.4;
  }
}
</style>
