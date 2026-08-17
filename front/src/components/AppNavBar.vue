<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const app = useAppStore()

interface NavItem {
  path: string
  label: string
  order: number
}

const navItems = computed<NavItem[]>(() => {
  return router
    .getRoutes()
    .filter((r) => r.meta.navLabel && (r.path.split('/').length <= 2 || r.name === 'report-list'))
    .filter((r) => auth.hasAnyRole(r.meta.roles))
    .map((r) => ({ path: r.path, label: r.meta.navLabel ?? '', order: r.meta.navOrder ?? 999 }))
    .filter((item, index, arr) => arr.findIndex((i) => i.path === item.path) === index)
    .sort((a, b) => a.order - b.order)
})

function isActive(path: string): boolean {
  if (path === '/documents') {
    return route.path === '/documents' || route.path.startsWith('/documents/')
  }
  if (path === '/reports') {
    return route.path.startsWith('/reports')
  }
  return route.path === path || route.path.startsWith(`${path}/`)
}

async function handleLogout(): Promise<void> {
  await auth.logout()
  app.push('info', '已退出登录')
  void router.push({ path: '/login' })
}
</script>

<template>
  <header class="nav">
    <RouterLink
      to="/"
      class="nav-brand"
    >
      财务风险审核
    </RouterLink>
    <nav
      class="nav-items"
      aria-label="主导航"
    >
      <RouterLink
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
    <div class="nav-user">
      <span class="nav-user-name">{{ auth.displayName }}</span>
      <button
        type="button"
        class="btn-link nav-logout"
        @click="handleLogout"
      >
        退出
      </button>
    </div>
  </header>
</template>

<style scoped>
.nav {
  height: var(--nav-height);
  background: var(--color-card);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 0 var(--page-padding);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-brand-deep);
  text-decoration: none;
  line-height: 27px;
}

.nav-items {
  display: flex;
  align-items: center;
  gap: 28px;
  flex: 1;
  overflow-x: auto;
}

.nav-item {
  font-size: 14px;
  line-height: 19px;
  color: #6b7280;
  text-decoration: none;
  white-space: nowrap;
  padding: 4px 2px;
  border-bottom: 2px solid transparent;
}

.nav-item:hover {
  color: var(--color-primary);
  text-decoration: none;
}

.nav-item.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.nav-user-name {
  font-size: 13px;
  color: var(--color-text-title);
}

.nav-logout {
  font-size: 13px;
}
</style>
