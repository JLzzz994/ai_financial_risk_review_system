<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, safeErrorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

const username = ref('')
const password = ref('')
const usernameError = ref('')
const passwordError = ref('')
const formError = ref('')
const submitting = ref(false)

const mockAccounts = import.meta.env.DEV
  ? [
      { username: 'li.qian', label: '申请人 · 李申请' },
      { username: 'zhou.shen', label: '审批人 · 周审批' },
      { username: 'li.caiwu', label: '财务 · 李财务' },
      { username: 'chen.admin', label: '管理员 · 陈管理' },
    ]
  : []

function validate(): boolean {
  usernameError.value = username.value.trim() ? '' : '请输入用户名'
  passwordError.value = password.value ? '' : '请输入密码'
  return !usernameError.value && !passwordError.value
}

async function handleSubmit(): Promise<void> {
  if (!validate() || submitting.value) return
  submitting.value = true
  formError.value = ''
  try {
    await auth.login(username.value.trim(), password.value)
    app.push('success', '登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    void router.replace(redirect)
  } catch (error) {
    if (error instanceof ApiError && error.status === 503) {
      formError.value = '认证服务暂未开放（后端联调中），开发模式可使用下方演示账号登录。'
    } else {
      formError.value = safeErrorMessage(error)
    }
  } finally {
    submitting.value = false
  }
}

function fillDemo(user: string): void {
  username.value = user
  password.value = 'demo1234'
}
</script>

<template>
  <div class="login-page">
    <main class="login-card">
      <header class="login-header">
        <h1 class="login-title">
          财务风险审核
        </h1>
        <p class="login-subtitle">
          财务单据智能风险审核系统
        </p>
      </header>

      <form
        class="login-form"
        novalidate
        @submit.prevent="handleSubmit"
      >
        <div
          v-if="formError"
          class="login-error"
          role="alert"
        >
          {{ formError }}
        </div>

        <div class="field">
          <label for="login-username">用户名</label>
          <input
            id="login-username"
            v-model="username"
            class="input"
            type="text"
            autocomplete="username"
            placeholder="请输入用户名"
            :aria-invalid="usernameError ? 'true' : undefined"
          >
          <span
            v-if="usernameError"
            class="field-error"
          >{{ usernameError }}</span>
        </div>

        <div class="field">
          <label for="login-password">密码</label>
          <input
            id="login-password"
            v-model="password"
            class="input"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            :aria-invalid="passwordError ? 'true' : undefined"
          >
          <span
            v-if="passwordError"
            class="field-error"
          >{{ passwordError }}</span>
        </div>

        <button
          type="submit"
          class="btn btn-primary login-submit"
          :disabled="submitting"
        >
          {{ submitting ? '登录中…' : '登录' }}
        </button>
      </form>

      <footer
        v-if="mockAccounts.length > 0"
        class="login-demo"
      >
        <p class="login-demo-title">
          演示账号（密码 demo1234）
        </p>
        <div class="login-demo-list">
          <button
            v-for="account in mockAccounts"
            :key="account.username"
            type="button"
            class="login-demo-item"
            @click="fillDemo(account.username)"
          >
            {{ account.label }}
          </button>
        </div>
      </footer>
    </main>
    <p class="login-footer">
      AI 辅助审核 · 审批决定由审批人员做出并留存审计记录
    </p>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 28px;
  background:
    radial-gradient(720px 320px at 18% 8%, rgba(24, 90, 189, 0.08), transparent 64%),
    radial-gradient(640px 300px at 85% 90%, rgba(18, 59, 109, 0.06), transparent 60%),
    var(--color-page-bg);
  padding: 32px 16px;
}

.login-card {
  width: 400px;
  max-width: 100%;
  background: var(--color-card);
  border-radius: var(--radius-card);
  outline: 1px solid var(--color-border);
  outline-offset: -0.5px;
  box-shadow: var(--shadow-float);
  padding: 40px 36px 28px;
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.login-title {
  font-size: 26px;
  line-height: 35px;
  font-weight: 600;
  color: var(--color-brand-deep);
  letter-spacing: 2px;
}

.login-subtitle {
  margin-top: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login-error {
  background: var(--risk-high-bg);
  color: var(--risk-high-text);
  border: 1px solid rgba(240, 68, 56, 0.35);
  border-radius: var(--radius-input);
  font-size: 13px;
  line-height: 20px;
  padding: 10px 14px;
}

.login-submit {
  width: 100%;
  margin-top: 4px;
  padding: 12px 18px;
  font-size: 14px;
}

.login-demo {
  margin-top: 24px;
  border-top: 1px dashed var(--color-border);
  padding-top: 16px;
}

.login-demo-title {
  font-size: 12px;
  color: var(--color-text-weak);
  margin-bottom: 10px;
}

.login-demo-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.login-demo-item {
  background: var(--color-panel);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  font-family: inherit;
  font-size: 12px;
  color: var(--color-text-secondary);
  padding: 8px 10px;
  cursor: pointer;
  transition: border-color var(--transition), color var(--transition);
}

.login-demo-item:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.login-footer {
  font-size: 12px;
  color: var(--color-text-weak);
}
</style>
