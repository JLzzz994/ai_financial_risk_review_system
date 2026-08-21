<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getAnalysisTask, subscribeTaskEvents, type TaskEventFrame, type TaskEventState } from '@/api/analysis-tasks'
import { closeSession, getReviewSession, listMessages, postMessage, type SessionIntent } from '@/api/review-sessions'
import { safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { AnalysisTask, ReviewSession, SessionMessage } from '@/types/domain'
import { sessionStatusView } from '@/types/status'
import { formatDateTime } from '@/utils/format'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageShell from '@/components/PageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskProgress from '@/components/TaskProgress.vue'

const route = useRoute()
const app = useAppStore()

const sessionId = computed(() => String(route.params.id))

const session = ref<ReviewSession | null>(null)
const messages = ref<SessionMessage[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

const draft = ref('')
const sending = ref(false)
const messageList = ref<HTMLElement | null>(null)

const task = ref<AnalysisTask | null>(null)
const streamState = ref<TaskEventState>('closed')
let subscription: { close: () => void } | null = null

const closeDialogOpen = ref(false)
const closing = ref(false)

const isClosed = computed(() => session.value?.session_status === 'closed')

const quickIntents: Array<{ intent: SessionIntent; label: string; text: string }> = [
  { intent: 'start_analysis', label: '开始风险分析', text: '开始风险分析' },
  { intent: 'query_result', label: '查询分析结果', text: '查询当前分析结果' },
]

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [sessionData, messageList] = await Promise.all([
      getReviewSession(sessionId.value),
      listMessages(sessionId.value),
    ])
    session.value = sessionData
    messages.value = messageList
    if (sessionData.analysis_task_id) await watchTask(sessionData.analysis_task_id)
    await scrollToBottom()
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: 'smooth' })
}

async function watchTask(taskId: string): Promise<void> {
  subscription?.close()
  try {
    task.value = await getAnalysisTask(taskId)
  } catch {
    task.value = null
    return
  }
  if (['succeeded', 'failed'].includes(task.value.stage)) {
    streamState.value = 'closed'
    return
  }
  subscription = subscribeTaskEvents(
    taskId,
    (frame: TaskEventFrame) => {
      if (!task.value) return
      if (frame.type === 'progress' && frame.step) {
        task.value = { ...task.value, stage: frame.step }
      } else if (frame.type === 'result') {
        task.value = { ...task.value, stage: 'succeeded', progress: 100 }
        void pushLocalAssistant('分析已完成，结果可在风险分析页或报告中心查看。')
      } else if (frame.type === 'error') {
        task.value = { ...task.value, stage: 'failed' }
        void pushLocalAssistant('分析任务失败，可在任务进度中重试或转人工处理。')
      }
    },
    (state) => {
      streamState.value = state
    },
  )
}

async function pushLocalAssistant(content: string): Promise<void> {
  messages.value.push({
    message_id: `local-${Date.now()}`,
    role: 'assistant',
    content,
    created_at: new Date().toISOString(),
  })
  await scrollToBottom()
}

async function send(text?: string, intent?: SessionIntent): Promise<void> {
  const content = (text ?? draft.value).trim()
  if (!content || sending.value || isClosed.value) return
  sending.value = true
  try {
    messages.value.push({
      message_id: `local-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    })
    draft.value = ''
    await scrollToBottom()
    const updated = await postMessage(sessionId.value, content, intent)
    messages.value = updated
    await scrollToBottom()
    if (session.value?.analysis_task_id) await watchTask(session.value.analysis_task_id)
  } catch (error) {
    app.push('error', safeErrorMessage(error))
  } finally {
    sending.value = false
  }
}

function askClose(): void {
  closeDialogOpen.value = true
}

async function confirmClose(reason: string): Promise<void> {
  if (!session.value) return
  closing.value = true
  try {
    session.value = await closeSession(sessionId.value, reason)
    app.push('success', '会话已关闭')
    closeDialogOpen.value = false
  } catch (error) {
    app.push('error', safeErrorMessage(error))
  } finally {
    closing.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => subscription?.close())
</script>

<template>
  <PageShell
    :title="`审核会话 · ${session?.document_no ?? sessionId}`"
    description="与审核助手的会话：意图识别、槽位确认与分析任务进度"
  >
    <template #actions>
      <div class="row">
        <StatusBadge
          v-if="session"
          v-bind="sessionStatusView(session.session_status)"
        />
        <button
          v-if="session && !isClosed"
          type="button"
          class="btn btn-secondary"
          @click="askClose"
        >
          结束会话
        </button>
      </div>
    </template>

    <ErrorState
      v-if="loadError"
      :message="loadError"
      @retry="load"
    />

    <div
      v-else
      class="session-layout"
    >
      <!-- 左：会话区 -->
      <section class="card session-panel">
        <div
          ref="messageList"
          class="message-list"
          aria-live="polite"
        >
          <div
            v-for="message in messages"
            :key="message.message_id"
            class="message"
            :class="message.role === 'user' ? 'message-user' : 'message-assistant'"
          >
            <div class="message-bubble">
              <p class="message-text">
                {{ message.content }}
              </p>
              <span class="message-time">{{ formatDateTime(message.created_at) }}</span>
            </div>
          </div>
        </div>

        <div class="session-input">
          <div class="quick-intents">
            <button
              v-for="option in quickIntents"
              :key="option.intent"
              type="button"
              class="btn btn-secondary btn-sm"
              :disabled="isClosed || sending"
              @click="send(option.text, option.intent)"
            >
              {{ option.label }}
            </button>
            <span
              v-if="isClosed"
              class="muted session-closed-hint"
            >会话已关闭，仅可查看历史消息</span>
          </div>
          <div class="input-row">
            <textarea
              v-model="draft"
              class="textarea"
              rows="2"
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              :disabled="isClosed || sending"
              @keydown.enter.exact.prevent="send()"
            />
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!draft.trim() || sending || isClosed"
              @click="send()"
            >
              {{ sending ? '发送中…' : '发送' }}
            </button>
          </div>
        </div>
      </section>

      <!-- 右：信息区 -->
      <aside class="session-side">
        <section class="card">
          <h2 class="card-title">
            单据信息
          </h2>
          <dl class="side-fields">
            <div>
              <dt>单据</dt><dd>
                <RouterLink
                  v-if="session"
                  :to="`/documents/${session.document_id}`"
                >
                  {{ session.document_no ?? session.document_id }}
                </RouterLink>
              </dd>
            </div>
            <div>
              <dt>会话状态</dt><dd>
                <StatusBadge
                  v-if="session"
                  v-bind="sessionStatusView(session.session_status)"
                />
              </dd>
            </div>
            <div><dt>创建时间</dt><dd>{{ formatDateTime(session?.created_at) }}</dd></div>
          </dl>
        </section>

        <section class="card">
          <h2 class="card-title">
            已确认槽位
          </h2>
          <ul class="slot-list">
            <li
              v-for="slot in session?.slots ?? []"
              :key="slot.name"
              class="slot"
              :class="{ confirmed: slot.confirmed }"
            >
              <span class="slot-label">{{ slot.label }}</span>
              <span class="slot-value">{{ slot.value }}</span>
              <span class="slot-state">{{ slot.confirmed ? '已确认' : '待确认' }}</span>
            </li>
          </ul>
        </section>

        <section class="card">
          <div class="card-title">
            <span>任务进度</span>
          </div>
          <TaskProgress
            v-if="task"
            :task="task"
            :stream-state="streamState"
            @resume="watchTask(task!.task_id)"
            @retry="watchTask(task!.task_id)"
          />
          <p
            v-else
            class="weak"
          >
            当前会话没有进行中的分析任务。
          </p>
        </section>
      </aside>
    </div>

    <ConfirmDialog
      v-model="closeDialogOpen"
      title="结束会话"
      message="确认结束该审核会话？结束后仅可查看历史消息，不能再发送消息。"
      confirm-text="确认结束"
      require-reason
      reason-label="结束原因"
      @confirm="confirmClose"
    />
  </PageShell>
</template>

<style scoped>
.session-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  align-items: start;
}

.session-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 260px);
  min-height: 420px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 2px 14px;
}

.message {
  display: flex;
}

.message-user {
  justify-content: flex-end;
}

.message-assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 76%;
  border-radius: 10px;
  padding: 10px 14px;
}

.message-user .message-bubble {
  background: var(--color-selected);
  border: 1px solid rgba(24, 90, 189, 0.2);
}

.message-assistant .message-bubble {
  background: var(--color-panel);
  border: 1px solid var(--color-border);
}

.message-text {
  font-size: 13px;
  line-height: 21px;
  color: var(--color-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-time {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-text-weak);
  text-align: right;
}

.session-input {
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.quick-intents {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.session-closed-hint {
  font-size: 12px;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-row .textarea {
  flex: 1;
  min-height: 56px;
}

.session-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.side-fields > div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 0;
  font-size: 13px;
}

.side-fields dt {
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.side-fields dd {
  margin: 0;
  text-align: right;
  word-break: break-all;
}

.slot-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.slot {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  padding: 8px 10px;
  font-size: 12px;
}

.slot.confirmed {
  background: var(--risk-low-bg);
  border-color: rgba(50, 213, 131, 0.4);
}

.slot-label {
  color: var(--color-text-secondary);
}

.slot-value {
  color: var(--color-text);
  font-weight: 600;
  word-break: break-all;
}

.slot-state {
  color: var(--color-text-weak);
}

.slot.confirmed .slot-state {
  color: var(--risk-low-text);
}

@media (max-width: 1100px) {
  .session-layout {
    grid-template-columns: 1fr;
  }

  .session-panel {
    height: 60vh;
  }
}
</style>
