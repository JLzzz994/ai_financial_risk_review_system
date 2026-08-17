/**
 * 字符串十进制工具 —— 金额禁止 float（R-06）。
 * 输入输出均为字符串，内部按“分”使用 BigInt 计算。
 */

function toCents(value: string): bigint {
  const s = String(value ?? '').trim()
  if (!/^-?\d+(\.\d+)?$/.test(s)) return 0n
  const negative = s.startsWith('-')
  const [intPart = '0', decPart = ''] = s.replace('-', '').split('.')
  const dec = (decPart + '00').slice(0, 2)
  const cents = BigInt(intPart || '0') * 100n + BigInt(dec || '0')
  return negative ? -cents : cents
}

function fromCents(cents: bigint): string {
  const negative = cents < 0n
  const abs = negative ? -cents : cents
  const intPart = abs / 100n
  const decPart = abs % 100n
  const text = `${intPart}.${decPart.toString().padStart(2, '0')}`
  return negative ? `-${text}` : text
}

/** 多个金额字符串相加 */
export function addAmounts(...values: string[]): string {
  return fromCents(values.reduce((acc, v) => acc + toCents(v), 0n))
}

/** 两个金额相减（a - b） */
export function subtractAmount(a: string, b: string): string {
  return fromCents(toCents(a) - toCents(b))
}

/** 是否等于 0 */
export function isZeroAmount(value: string): boolean {
  return toCents(value) === 0n
}

/** 比较金额：返回 -1/0/1 */
export function compareAmount(a: string, b: string): number {
  const x = toCents(a)
  const y = toCents(b)
  return x < y ? -1 : x > y ? 1 : 0
}

/** 校验金额字符串：非负、最多两位小数 */
export function isValidAmountInput(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value.trim())
}

/** 展示金额：两位小数 + 千分位 */
export function formatMoney(value: string | number | null | undefined, currency = 'CNY'): string {
  if (value === null || value === undefined || value === '') return '—'
  const fixed = fromCents(toCents(String(value)))
  const negative = fixed.startsWith('-')
  const [intPart, decPart] = (negative ? fixed.slice(1) : fixed).split('.')
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const symbol = currency === 'CNY' ? '¥' : `${currency} `
  return `${negative ? '-' : ''}${symbol}${grouped}.${decPart}`
}

/** 文件大小展示 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** ISO 时间 → YYYY-MM-DD HH:mm */
export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** ISO 时间 → YYYY-MM-DD */
export function formatDate(iso?: string | null): string {
  if (!iso) return '—'
  return formatDateTime(iso).slice(0, 10)
}

/** 置信度 0-1 → 百分比 */
export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`
}
