/**
 * 统一 API 客户端。
 * - 注入 Authorization: Bearer、X-Request-ID、Idempotency-Key（写操作）
 * - 解析后端统一错误体 { error: { code, message }, request_id }，兼容 FastAPI 原生 { detail }
 * - handleApiError 统一 401/403/404/409/422/503/500 交互（SPEC 20 §7）
 */

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId?: string
  readonly details?: unknown

  constructor(status: number, code: string, message: string, requestId?: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

export type ApiErrorHandler = (error: ApiError) => void

let tokenGetter: () => string | null = () => null
let errorHandler: ApiErrorHandler | null = null

export function setTokenGetter(getter: () => string | null): void {
  tokenGetter = getter
}

export function setApiErrorHandler(handler: ApiErrorHandler | null): void {
  errorHandler = handler
}

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || '/api/v1'
export const MOCK_ENABLED: boolean = import.meta.env.VITE_ENABLE_MOCK === 'true'

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** 查询参数：扁平对象，值为空/null/undefined 时跳过 */
  query?: object
  /** 写操作幂等键；显式传入或自动生成 */
  idempotencyKey?: string
  signal?: AbortSignal
}

function buildUrl(path: string, query?: object): string {
  const url = `${API_BASE_URL}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  const requestId = response.headers.get('X-Request-ID') ?? undefined
  let code = 'unknown_error'
  let message = `请求失败（HTTP ${response.status}）`
  let details: unknown
  try {
    const data: unknown = await response.json()
    if (data && typeof data === 'object') {
      const obj = data as Record<string, unknown>
      if (obj.error && typeof obj.error === 'object') {
        const err = obj.error as Record<string, unknown>
        code = typeof err.code === 'string' ? err.code : code
        message = typeof err.message === 'string' ? err.message : message
        details = err.details
      } else if (typeof obj.detail === 'string') {
        // FastAPI HTTPException 原生格式（如 401/422）
        message = obj.detail
        code = response.status === 401 ? 'unauthorized' : code
        if (Array.isArray(obj.detail)) {
          details = obj.detail
          message = '请求参数校验失败'
        }
      }
    }
  } catch {
    // 响应体非 JSON，保留默认文案
  }
  return new ApiError(response.status, code, message, requestId, details)
}

export function handleApiError(error: unknown): void {
  if (error instanceof ApiError) {
    errorHandler?.(error)
  } else {
    console.error('[api] 未识别的请求异常')
  }
}

/** 将未知异常转为对用户安全的消息（不泄露路径/SQL/模型内部信息） */
export function safeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 500) {
      return error.requestId
        ? `服务器内部错误，请联系管理员并提供请求编号 ${error.requestId}`
        : '服务器内部错误，请联系管理员'
    }
    return error.message
  }
  if (error instanceof TypeError) return '网络连接失败，请检查网络后重试'
  return '操作失败，请稍后重试'
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, idempotencyKey, signal } = options

  if (MOCK_ENABLED) {
    const { mockRequest } = await import('@/mocks/handlers')
    const mocked = await mockRequest<T>(method, path, body, query)
    if (mocked.handled) return mocked.data as T
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Request-ID': crypto.randomUUID(),
  }
  const token = tokenGetter()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'network_error', '网络连接失败，请检查网络后重试')
  }

  if (!response.ok) {
    throw await parseErrorBody(response)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** 下载文件（blob），同样注入认证头 */
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  if (MOCK_ENABLED) {
    const { mockRequest } = await import('@/mocks/handlers')
    const mocked = await mockRequest<void>('GET', path, undefined, undefined)
    if (mocked.handled) {
      triggerBrowserDownload(new Blob([JSON.stringify(mocked.data ?? {}, null, 2)], { type: 'application/json' }), `${fallbackName}.json`)
      return
    }
  }
  const headers: Record<string, string> = { 'X-Request-ID': crypto.randomUUID() }
  const token = tokenGetter()
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(buildUrl(path), { headers })
  if (!response.ok) throw await parseErrorBody(response)
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition)
  triggerBrowserDownload(blob, match ? decodeURIComponent(match[1]!) : fallbackName)
}

/** 上传文件（multipart），注入认证头与追踪头 */
export async function apiUpload<T>(path: string, file: File, extra?: Record<string, string>): Promise<T> {
  if (MOCK_ENABLED) {
    const { mockUpload } = await import('@/mocks/handlers')
    const mocked = await mockUpload<T>(path, file, extra)
    if (mocked.handled) return mocked.data as T
  }
  const form = new FormData()
  form.append('file', file)
  for (const [key, value] of Object.entries(extra ?? {})) form.append(key, value)
  const headers: Record<string, string> = { 'X-Request-ID': crypto.randomUUID() }
  const token = tokenGetter()
  if (token) headers.Authorization = `Bearer ${token}`
  let response: Response
  try {
    response = await fetch(buildUrl(path), { method: 'POST', headers, body: form })
  } catch {
    throw new ApiError(0, 'network_error', '网络连接失败，请检查网络后重试')
  }
  if (!response.ok) throw await parseErrorBody(response)
  return (await response.json()) as T
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
