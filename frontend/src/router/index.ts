import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import BasicLayout from '@/layouts/BasicLayout.vue'
import UserLayout from '@/layouts/UserLayout.vue'

const HomeView = () => import('@/views/HomeView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const RegisterView = () => import('@/views/RegisterView.vue')
const PersonaView = () => import('@/views/PersonaView.vue')
const ForumDetailView = () => import('@/views/ForumDetailView.vue')
const AssistantView = () => import('@/views/AssistantView.vue')
const SkillRepositoryView = () => import('@/views/SkillRepositoryView.vue')
const TimeGateView = () => import('@/views/TimeGateView.vue')
const TeamListView = () => import('@/views/team/TeamListView.vue')
const TeamChatView = () => import('@/views/team/TeamChatView.vue')
const DecisionPanelView = () => import('@/views/DecisionPanelView.vue')
// 渡心功能暂隐藏：后续恢复时取消下方注释
// const DuxinView = () => import('@/views/DuxinView.vue')
const AdminOverviewView = () => import('@/views/admin/AdminOverviewView.vue')
const AdminUsersView = () => import('@/views/admin/AdminUsersView.vue')
const AdminConfigView = () => import('@/views/admin/AdminConfigView.vue')
const AdminPersonasView = () => import('@/views/admin/AdminPersonasView.vue')
const AdminSkillsView = () => import('@/views/admin/AdminSkillsView.vue')
const AdminAuditView = () => import('@/views/admin/AdminAuditView.vue')

const ADMIN_ROLES = ['admin', 'god']

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/auth',
      component: UserLayout,
      redirect: '/auth/login',
      children: [
        {
          path: 'login',
          name: 'login',
          component: LoginView
        },
        {
          path: 'register',
          name: 'register',
          component: RegisterView
        }
      ]
    },
    {
      path: '/',
      component: BasicLayout,
      redirect: '/dashboard',
      meta: { requiresAuth: true },
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: HomeView
        },
        {
          path: 'personas',
          name: 'personas',
          component: PersonaView
        },
        {
          path: 'forums/:id',
          name: 'forum-detail',
          component: ForumDetailView
        },
        {
          path: 'assistants',
          name: 'assistants',
          component: AssistantView
        },
        {
          path: 'assistants/skills',
          name: 'assistant-skills',
          component: SkillRepositoryView
        },
        {
          path: 'time-gate',
          name: 'time-gate',
          component: TimeGateView
        },
        {
          path: 'teams',
          name: 'team-list',
          component: TeamListView
        },
        {
          path: 'teams/:id',
          name: 'team-chat',
          component: TeamChatView
        },
        {
          path: 'decision',
          name: 'decision-panel',
          component: DecisionPanelView
        },
        // 渡心功能暂隐藏：后续恢复时取消下方注释
        // {
        //   path: 'duxin',
        //   name: 'duxin',
        //   component: DuxinView
        // },
        {
          path: 'admin',
          redirect: '/admin/overview',
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/overview',
          name: 'admin-overview',
          component: AdminOverviewView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/users',
          name: 'admin-users',
          component: AdminUsersView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/config',
          name: 'admin-config',
          component: AdminConfigView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/personas',
          name: 'admin-personas',
          component: AdminPersonasView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/skills',
          name: 'admin-skills',
          component: AdminSkillsView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
        {
          path: 'admin/audit',
          name: 'admin-audit',
          component: AdminAuditView,
          meta: { requiresAuth: true, requiresAdmin: true }
        },
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard'
    }
  ]
})

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  
  if (to.path.startsWith('/auth') && authStore.token) {
    next('/dashboard')
    return
  }
  
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!authStore.token) {
      next('/auth/login')
      return
    }
  }

  if (to.matched.some(record => record.meta.requiresAdmin)) {
    const role = authStore.user?.role
    if (!ADMIN_ROLES.includes(role || '')) {
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
