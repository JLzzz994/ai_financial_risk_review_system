<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  deleteAttachment,
  downloadAttachment,
  listAttachments,
  parseAttachment,
  uploadAttachment,
} from '@/api/attachments'
import { ApiError, handleApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { Attachment } from '@/types/domain'
import { attachmentParseView, attachmentStorageView } from '@/types/status'
import { formatDateTime, formatFileSize } from '@/utils/format'
import ConfirmDialog from './ConfirmDialog.vue'
import StatusBadge from './StatusBadge.vue'

const props = withDefaults(
  defineProps<{
    documentId: string
    readonly?: boolean
  }>(),
  { readonly: false },
)

const app = useAppStore()

const attachments = ref<Attachment[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const deleteTarget = ref<Attachment | null>(null)
const deleteDialogOpen = ref(false)
const deleteReason = ref('')
const deleting = ref(false)

const MAX_SIZE_MB = 20
const ACCEPT = '.pdf,.xlsx,.xls,.docx,.jpg,.jpeg,.png'

let pollTimer: number | null = null
let pollCount = 0

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    attachments.value = await listAttachments(props.documentId)
    schedulePoll()
  } catch (error) {
    loadError.value = safeErrorMessage(error)
  } finally {
    loading.value = false
  }
}

/** 存在 pending / parsing 附件时轮询解析状态（阶段状态，SPEC 09） */
function schedulePoll(): void {
  const active = attachments.value.some((a) => ['pending', 'parsing'].includes(a.parse_status))
  if (active && pollCount < 20) {
    pollTimer = window.setTimeout(async () => {
      pollCount += 1
      try {
        attachments.value = await listAttachments(props.documentId)
      } catch {
        return
      }
      schedulePoll()
    }, 1500)
  }
}

function stopPoll(): void {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer)
    pollTimer = null
  }
  pollCount = 0
}

function pickFile(): void {
  fileInput.value?.click()
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    app.push('error', `文件超过大小限制（${MAX_SIZE_MB}MB）：${file.name}`)
    return
  }
  uploading.value = true
  try {
    await uploadAttachment(props.documentId, file)
    app.push('success', `已上传：${file.name}，等待解析`)
    await load()
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      app.push('warning', '文件类型或数量不符合该单据的附件要求')
    } else {
      app.push('error', safeErrorMessage(error))
    }
    handleApiError(error)
  } finally {
    uploading.value = false
  }
}

function askDelete(attachment: Attachment): void {
  deleteTarget.value = attachment
  deleteReason.value = ''
  deleteDialogOpen.value = true
}

async function confirmDelete(reason: string): Promise<void> {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteAttachment(deleteTarget.value.attachment_id)
    app.push('success', reason ? `附件已删除：${reason}` : '附件已删除')
    deleteDialogOpen.value = false
    await load()
  } catch (error) {
    handleApiError(error)
    app.push('error', safeErrorMessage(error))
  } finally {
    deleting.value = false
  }
}

async function reparse(attachment: Attachment): Promise<void> {
  try {
    await parseAttachment(attachment.attachment_id)
    app.push('info', `已重新发起解析：${attachment.file_name}`)
    await load()
  } catch (error) {
    handleApiError(error)
  }
}

function download(attachment: Attachment): void {
  void downloadAttachment(attachment.attachment_id, attachment.file_name).catch((error: unknown) => {
    handleApiError(error)
  })
}

onMounted(load)
onBeforeUnmount(stopPoll)

defineExpose({ reload: load })
</script>

<template>
  <div class="uploader">
    <div class="uploader-toolbar">
      <p class="uploader-note">
        支持 PDF / Excel / Word / 图片，单文件不超过 {{ MAX_SIZE_MB }}MB；上传后将自动进行病毒扫描与解析。
      </p>
      <div class="row">
        <button
          v-if="!readonly"
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="uploading"
          @click="pickFile"
        >
          {{ uploading ? '上传中…' : '上传附件' }}
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        class="uploader-input"
        :accept="ACCEPT"
        aria-label="选择附件"
        @change="onFileChange"
      >
    </div>

    <div
      v-if="loading && attachments.length === 0"
      class="uploader-loading"
    >
      附件加载中…
    </div>
    <div
      v-else-if="loadError"
      class="uploader-error"
      role="alert"
    >
      {{ loadError }}
      <button
        type="button"
        class="btn-link"
        @click="load"
      >
        重试
      </button>
    </div>
    <p
      v-else-if="attachments.length === 0"
      class="uploader-empty"
    >
      尚未上传附件
    </p>

    <ul
      v-else
      class="attachment-list"
    >
      <li
        v-for="attachment in attachments"
        :key="attachment.attachment_id"
        class="attachment-item"
      >
        <div class="attachment-main">
          <span
            class="attachment-name"
            :title="attachment.file_name"
          >{{ attachment.file_name }}</span>
          <span class="attachment-meta">{{ formatFileSize(attachment.file_size) }} · {{ attachment.uploaded_by }} · {{ formatDateTime(attachment.uploaded_at) }}</span>
        </div>
        <div class="attachment-badges">
          <StatusBadge v-bind="attachmentStorageView(attachment.storage_status)" />
          <StatusBadge v-bind="attachmentParseView(attachment.parse_status)" />
        </div>
        <div class="attachment-actions">
          <button
            type="button"
            class="btn-link"
            @click="download(attachment)"
          >
            下载
          </button>
          <button
            v-if="!readonly && ['failed', 'succeeded', 'manual_review'].includes(attachment.parse_status)"
            type="button"
            class="btn-link"
            @click="reparse(attachment)"
          >
            重新解析
          </button>
          <button
            v-if="!readonly"
            type="button"
            class="btn-link btn-link-danger"
            @click="askDelete(attachment)"
          >
            删除
          </button>
        </div>
      </li>
    </ul>

    <ConfirmDialog
      v-model="deleteDialogOpen"
      title="删除附件"
      :message="`确认删除附件「${deleteTarget?.file_name ?? ''}」？该操作会写入审计日志。`"
      confirm-text="确认删除"
      tone="danger"
      require-reason
      reason-label="删除原因"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.uploader-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.uploader-note {
  font-size: 12px;
  line-height: 18px;
  color: var(--color-text-weak);
}

.uploader-input {
  display: none;
}

.uploader-loading,
.uploader-empty {
  font-size: 13px;
  color: var(--color-text-weak);
  padding: 8px 0;
}

.uploader-error {
  font-size: 13px;
  color: var(--risk-high-text);
  padding: 8px 0;
}

.attachment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 2px;
  border-bottom: 1px solid var(--color-border);
}

.attachment-item:last-child {
  border-bottom: none;
}

.attachment-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.attachment-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-meta {
  font-size: 12px;
  color: var(--color-text-weak);
}

.attachment-badges {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.attachment-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.btn-link-danger {
  color: var(--risk-high-text);
}

@media (max-width: 720px) {
  .attachment-item {
    flex-wrap: wrap;
  }
}
</style>
