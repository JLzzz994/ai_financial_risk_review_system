import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'
import { MOCK_ENABLED } from '@/api/client'
import type { Principal, RoleCode } from '@/types/domain'

const TOKEN_KEY = 'fr.access_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(sessionStorage.getItem(TOKEN_KEY))
  const principal = ref<Principal | null>(null)
  const booted = ref(false)

  const isAuthenticated = computed(() => token.value !== null && principal.value !== null)
  const roles = computed<RoleCode[]>(() => principal.value?.roles ?? [])
  const displayName = computed(() => {
    if (!principal.value) return ''
    const name = principal.value.display_name ?? principal.value.username
    return principal.value.department ? `${name} · ${principal.value.department}` : name
  })

  function hasAnyRole(required?: RoleCode[]): boolean {
    if (!required || required.length === 0) return true
    return required.some((role) => roles.value.includes(role))
  }

  async function login(username: string, password: string): Promise<void> {
    const authToken = await authApi.login(username, password)
    token.value = authToken.access_token
    sessionStorage.setItem(TOKEN_KEY, authToken.access_token)
    if (MOCK_ENABLED) {
      const { mockAuth } = await import('@/mocks/mock-auth')
      mockAuth.token = authToken.access_token
    }
    await refreshPrincipal()
  }

  async function refreshPrincipal(): Promise<void> {
    if (!token.value) return
    if (MOCK_ENABLED) {
      const { mockAuth } = await import('@/mocks/mock-auth')
      mockAuth.token = token.value
    }
    try {
      principal.value = await authApi.fetchMe()
    } catch (error) {
      clearSession()
      throw error
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } catch {
      // 退出登录忽略后端异常，本地状态必须清理
    }
    clearSession()
  }

  function clearSession(): void {
    token.value = null
    principal.value = null
    sessionStorage.removeItem(TOKEN_KEY)
    if (MOCK_ENABLED) {
      void import('@/mocks/mock-auth').then(({ mockAuth }) => {
        mockAuth.token = ''
      })
    }
  }

  return {
    token,
    principal,
    booted,
    isAuthenticated,
    roles,
    displayName,
    hasAnyRole,
    login,
    refreshPrincipal,
    logout,
    clearSession,
  }
})
