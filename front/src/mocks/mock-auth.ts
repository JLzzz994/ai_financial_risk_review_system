/**
 * mock 模式下的轻量登录态桥接：auth store 写入，handlers 读取（仅开发模式使用）。
 * token 键名与 stores/auth.ts 的 TOKEN_KEY 保持一致；
 * 从 sessionStorage 初始化，保证整页刷新后 mock 会话仍可用。
 */
const TOKEN_KEY = 'fr.access_token'

function readToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export const mockAuth = {
  token: readToken(),
}
