import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { ApiError, setApiErrorHandler, setTokenGetter } from './api/client'
import router from './router'
import { installRouterGuards, setAuthBoot } from './router/guards'
import { useAppStore } from './stores/app'
import { useAuthStore } from './stores/auth'
import './styles/base.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const auth = useAuthStore()
setTokenGetter(() => auth.token)

setApiErrorHandler((error: ApiError) => {
  const toast = useAppStore()
  if (error.status === 401) {
    auth.clearSession()
    toast.push('error', '登录已过期，请重新登录')
    void router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
    return
  }
  if (error.status === 403) {
    toast.push('error', '当前账号无权执行该操作')
    return
  }
  if (error.status === 404) {
    toast.push('error', '资源不存在或已被删除')
    return
  }
  if (error.status === 409) {
    toast.push('warning', '数据已被其他人处理，请刷新后查看最新状态')
    return
  }
  if (error.status === 422) {
    toast.push('warning', '提交内容校验失败，请检查填写项')
    return
  }
  if (error.status === 503 || error.status === 0) {
    toast.push('warning', '服务暂不可用，请稍后重试')
    return
  }
  if (error.status === 500) {
    toast.push(
      'error',
      error.requestId
        ? `服务器内部错误，请联系管理员（请求编号 ${error.requestId}）`
        : '服务器内部错误，请联系管理员',
    )
    return
  }
  toast.push('error', error.message)
})

// 1. 先注册守卫（等待会话恢复），再安装路由触发首次导航
installRouterGuards(router)
app.use(router)

// 2. 会话恢复任务：存在 token 时调用 /auth/me；失败则清理本地状态
const bootTask = (async (): Promise<void> => {
  if (auth.token) {
    try {
      await auth.refreshPrincipal()
    } catch {
      // refreshPrincipal 内部已清理本地状态
    }
  }
  auth.booted = true
})()
setAuthBoot(bootTask)

// 3. 恢复完成后再挂载，避免闪现未登录视图
void bootTask.then(() => {
  app.mount('#app')
})
