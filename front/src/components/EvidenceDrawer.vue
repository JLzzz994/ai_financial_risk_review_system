<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { downloadAttachment } from '@/api/attachments'
import { handleApiError } from '@/api/client'
import type { Evidence, RiskFinding } from '@/types/domain'
import { formatConfidence, formatDateTime } from '@/utils/format'
import BaseDrawer from './BaseDrawer.vue'
import RiskLevelTag from './RiskLevelTag.vue'
import StatusBadge from './StatusBadge.vue'
import { reviewStatusView } from '@/types/status'

const props = defineProps<{
  modelValue: boolean
  finding: RiskFinding | null
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const selectedEvidenceId = ref<string | null>(null)

const selectedEvidence = computed<Evidence | null>(() => {
  if (!props.finding) return null
  return props.finding.evidence.find((e) => e.evidence_id === selectedEvidenceId.value) ?? props.finding.evidence[0] ?? null
})

watch(
  () => props.finding,
  (finding) => {
    selectedEvidenceId.value = finding?.evidence[0]?.evidence_id ?? null
  },
)

function handleDownload(evidence: Evidence): void {
  if (!evidence.attachment_id) return
  void downloadAttachment(evidence.attachment_id, evidence.attachment_name ?? '附件').catch((error: unknown) => {
    handleApiError(error)
  })
}
</script>

<template>
  <BaseDrawer
    :model-value="modelValue"
    title="风险证据"
    width="760px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template v-if="finding">
      <div class="finding-head">
        <div class="finding-head-text">
          <div class="row">
            <RiskLevelTag :level="finding.risk_level" />
            <span class="finding-rule">{{ finding.rule_code }} · {{ finding.rule_name }}</span>
          </div>
          <p class="finding-title">
            {{ finding.title }}
          </p>
          <p class="finding-desc">
            {{ finding.description }}
          </p>
        </div>
        <StatusBadge v-bind="reviewStatusView(finding.review_status)" />
      </div>

      <div
        v-if="finding.evidence.length === 0"
        class="evidence-empty"
        role="alert"
      >
        <p class="evidence-empty-title">
          证据不足，需要人工确认
        </p>
        <p class="evidence-empty-desc">
          该风险未绑定可核对的证据（附件、页码或原文片段缺失），不能显示为已确认风险。请结合原始材料人工判断。
        </p>
      </div>

      <div
        v-else
        class="evidence-layout"
      >
        <div class="evidence-list">
          <button
            v-for="item in finding.evidence"
            :key="item.evidence_id"
            type="button"
            class="evidence-item"
            :class="{ selected: selectedEvidence?.evidence_id === item.evidence_id }"
            @click="selectedEvidenceId = item.evidence_id"
          >
            <span class="evidence-item-kind">{{ item.attachment_name ?? '附件' }}</span>
            <span class="evidence-item-page">第 {{ item.page_no ?? '—' }} 页</span>
          </button>
          <p class="evidence-list-hint">
            共 {{ finding.evidence.length }} 条证据，点击切换
          </p>
        </div>

        <div
          v-if="selectedEvidence"
          class="evidence-detail"
        >
          <div class="evidence-preview">
            <div class="evidence-preview-box">
              <span class="evidence-preview-name">{{ selectedEvidence.attachment_name ?? '附件' }}</span>
              <button
                type="button"
                class="btn btn-secondary btn-sm"
                :disabled="!selectedEvidence.attachment_id"
                @click="handleDownload(selectedEvidence)"
              >
                查看附件
              </button>
            </div>
            <p class="evidence-preview-note">
              附件预览需后端预览服务支持，当前提供安全下载
            </p>
          </div>

          <dl class="evidence-fields">
            <div class="evidence-field">
              <dt>页码 / 位置</dt>
              <dd>
                第 {{ selectedEvidence.page_no ?? '—' }} 页
                <template v-if="selectedEvidence.position">
                  · {{ selectedEvidence.position }}
                </template>
              </dd>
            </div>
            <div class="evidence-field">
              <dt>字段路径</dt>
              <dd class="mono">
                {{ selectedEvidence.field_path ?? '—' }}
              </dd>
            </div>
            <div class="evidence-field">
              <dt>置信度</dt>
              <dd>{{ formatConfidence(selectedEvidence.confidence) }}</dd>
            </div>
            <div class="evidence-field">
              <dt>规则版本</dt>
              <dd>{{ selectedEvidence.rule_version ?? '—' }}</dd>
            </div>
            <div class="evidence-field">
              <dt>分析时间</dt>
              <dd>{{ formatDateTime(selectedEvidence.analyzed_at) }}</dd>
            </div>
            <div class="evidence-field evidence-field-full">
              <dt>原文片段</dt>
              <dd>
                <blockquote class="evidence-snippet">
                  {{ selectedEvidence.snippet }}
                </blockquote>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </template>
  </BaseDrawer>
</template>

<style scoped>
.finding-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 16px;
}

.finding-rule {
  font-size: 12px;
  color: var(--color-text-weak);
}

.finding-title {
  margin-top: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-title);
}

.finding-desc {
  margin-top: 6px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
}

.evidence-empty {
  background: var(--risk-medium-bg);
  border: 1px solid rgba(247, 144, 9, 0.35);
  border-radius: var(--radius-btn);
  padding: 20px;
}

.evidence-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--risk-medium-text);
}

.evidence-empty-desc {
  margin-top: 6px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
}

.evidence-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-btn);
  padding: 10px 12px;
  cursor: pointer;
  font-family: inherit;
}

.evidence-item:hover {
  border-color: var(--color-primary);
}

.evidence-item.selected {
  border-color: var(--color-primary);
  background: var(--color-selected);
}

.evidence-item-kind {
  font-size: 13px;
  color: var(--color-text);
  word-break: break-all;
}

.evidence-item-page {
  font-size: 12px;
  color: var(--color-text-weak);
}

.evidence-list-hint {
  font-size: 12px;
  color: var(--color-text-weak);
  text-align: center;
}

.evidence-preview-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-btn);
  padding: 14px 16px;
}

.evidence-preview-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  word-break: break-all;
}

.evidence-preview-note {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-weak);
}

.evidence-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  margin: 16px 0 0;
}

.evidence-field dt {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-bottom: 4px;
}

.evidence-field dd {
  margin: 0;
  font-size: 13px;
  color: var(--color-text);
  word-break: break-all;
}

.evidence-field-full {
  grid-column: 1 / -1;
}

.evidence-snippet {
  margin: 0;
  background: var(--color-selected);
  border-left: 3px solid var(--color-primary);
  border-radius: 0 var(--radius-input) var(--radius-input) 0;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 22px;
  color: var(--color-text);
  white-space: pre-wrap;
}

@media (max-width: 720px) {
  .evidence-layout {
    grid-template-columns: 1fr;
  }
}
</style>
