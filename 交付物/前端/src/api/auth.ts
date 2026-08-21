import type { AuthToken, Principal } from '@/types/domain'
import { apiFetch } from './client'

export function login(username: string, password: string): Promise<AuthToken> {
  return apiFetch<AuthToken>('/auth/login', {
    method: 'POST',
    body: { username, password },
  })
}

export function fetchMe(): Promise<Principal> {
  return apiFetch<Principal>('/auth/me')
}

export function logout(): Promise<void> {
  return apiFetch<void>('/auth/logout', { method: 'POST' })
}
