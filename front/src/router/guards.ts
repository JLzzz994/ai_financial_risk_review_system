import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * 路由守卫只负责体验：未登录跳登录页、无权限显示 403；
 * 后端 API 仍会强制校验权限（SPEC 20 §2）。
 */
let authBootTask: Promise<void> | null = null

/** 注册应用启动时的会话恢复任务，守卫在首次导航前等待其完成（避免整页刷新被误判为未登录） */
export function setAuthBoot(task: Promise<void>): void {
  authBootTask = task
}

export function installRouterGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const auth = useAuthStore()

    if (authBootTask && !auth.booted) {
      await authBootTask
    }

    if (to.meta.public) {
      if (to.name === 'login' && auth.isAuthenticated) {
        return { path: '/', replace: true }
      }
      return true
    }

    if (!auth.isAuthenticated) {
      return { path: '/login', query: { redirect: to.fullPath }, replace: true }
    }

    if (!auth.hasAnyRole(to.meta.roles)) {
      return { path: '/403', replace: true }
    }

    return true
  })

  router.afterEach((to) => {
    document.title = to.meta.title ? `${to.meta.title} · 财务风险审核` : '财务风险审核'
  })
}
