<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="error-page">
    <div class="card error-card">
      <p class="error-code">
        403
      </p>
      <h1 class="error-title">
        无权访问
      </h1>
      <p class="error-desc">
        当前账号没有访问该页面的权限。如需开通，请联系管理员调整角色授权。
      </p>
      <div class="error-actions">
        <button
          type="button"
          class="btn btn-secondary"
          @click="router.back()"
        >
          返回上一页
        </button>
        <button
          type="button"
          class="btn btn-primary"
          @click="router.push('/')"
        >
          回到首页
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-page {
  min-height: calc(100vh - var(--nav-height));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
}

.error-card {
  width: 460px;
  max-width: 100%;
  text-align: center;
  padding: 48px 32px;
}

.error-code {
  font-size: 44px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--color-border-strong);
}

.error-title {
  margin-top: 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-brand-deep);
}

.error-desc {
  margin-top: 10px;
  font-size: 13px;
  line-height: 20px;
  color: var(--color-text-secondary);
}

.error-actions {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>
