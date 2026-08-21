import 'vue-router'
import type { RoleCode } from '@/types/domain'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（document.title） */
    title: string
    /** 公开页面（无布局、免登录） */
    public?: boolean
    /** 允许访问的角色；为空表示登录即可 */
    roles?: RoleCode[]
    /** 顶部导航显示名 */
    navLabel?: string
    /** 导航排序权重 */
    navOrder?: number
  }
}
