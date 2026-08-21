import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      redirect: () => {
        const auth = useAuthStore()
        if (auth.roles.includes('applicant') && !auth.roles.some((r) => r === 'approver' || r === 'finance')) {
          return { path: '/documents' }
        }
        if (auth.roles.includes('admin') && auth.roles.length === 1) {
          return { path: '/workflow-config' }
        }
        return { path: '/workbench' }
      },
    },
    {
      path: '/workbench',
      name: 'workbench',
      component: () => import('@/views/WorkbenchView.vue'),
      meta: { title: '审核工作台', roles: ['approver', 'finance'], navLabel: '工作台', navOrder: 10 },
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('@/views/MyDocumentsView.vue'),
      meta: { title: '我的单据', roles: ['applicant', 'finance'], navLabel: '我的单据', navOrder: 20 },
    },
    {
      path: '/documents/:id/edit',
      name: 'document-edit',
      component: () => import('@/views/DocumentEditView.vue'),
      meta: { title: '单据编辑', roles: ['applicant'] },
    },
    {
      path: '/documents/:id',
      name: 'document-detail',
      component: () => import('@/views/DocumentDetailView.vue'),
      meta: { title: '单据详情', roles: ['applicant', 'approver', 'finance'] },
    },
    {
      path: '/documents/:id/risk-analysis',
      name: 'risk-analysis',
      component: () => import('@/views/RiskAnalysisView.vue'),
      meta: { title: '风险分析', roles: ['applicant', 'approver', 'finance'] },
    },
    {
      path: '/documents/:id/amount-comparison',
      name: 'amount-comparison',
      component: () => import('@/views/AmountCheckView.vue'),
      meta: { title: '金额核对', roles: ['approver', 'finance'] },
    },
    {
      path: '/review-sessions/:id',
      name: 'review-session',
      component: () => import('@/views/ReviewSessionView.vue'),
      meta: { title: '审核会话', roles: ['applicant', 'approver', 'finance'] },
    },
    {
      path: '/suppliers/:id/risks',
      name: 'supplier-risks',
      component: () => import('@/views/SupplierRiskView.vue'),
      meta: { title: '供应商风险', roles: ['approver', 'finance'] },
    },
    {
      path: '/approval-tasks',
      name: 'approval-tasks',
      component: () => import('@/views/ApprovalTasksView.vue'),
      meta: { title: '审批任务', roles: ['approver'], navLabel: '审批任务', navOrder: 30 },
    },
    {
      path: '/rule-center',
      name: 'rule-center',
      component: () => import('@/views/RuleCenterView.vue'),
      meta: { title: '规则中心', roles: ['finance', 'admin'], navLabel: '规则中心', navOrder: 40 },
    },
    {
      path: '/workflow-config',
      name: 'workflow-config',
      component: () => import('@/views/WorkflowConfigView.vue'),
      meta: { title: '流程配置', roles: ['admin'], navLabel: '流程配置', navOrder: 50 },
    },
    {
      path: '/reports',
      name: 'report-list',
      component: () => import('@/views/ReportCenterView.vue'),
      meta: { title: '报告中心', roles: ['applicant', 'approver', 'finance'], navLabel: '报告中心', navOrder: 60 },
    },
    {
      path: '/reports/:documentVersionId',
      name: 'report-detail',
      component: () => import('@/views/ReportCenterView.vue'),
      meta: { title: '报告中心', roles: ['applicant', 'approver', 'finance'], navLabel: '报告中心', navOrder: 60 },
    },
    {
      path: '/audit-logs',
      name: 'audit-logs',
      component: () => import('@/views/AuditLogView.vue'),
      meta: { title: '审计日志', roles: ['admin'], navLabel: '审计日志', navOrder: 70 },
    },
    {
      path: '/403',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { title: '无权访问', public: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { title: '页面不存在', public: true },
    },
  ],
})

export default router
