import {
  createRouter,
  createWebHistory,
  type RouterHistory,
} from 'vue-router'
import AdminLayout from '@/components/AdminLayout.vue'
import CapturesPage from '@/pages/CapturesPage.vue'
import ChannelDetailPage from '@/pages/ChannelDetailPage.vue'
import ChannelsPage from '@/pages/ChannelsPage.vue'
import FlightMessagesPage from '@/pages/FlightMessagesPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import NotFoundPage from '@/pages/NotFoundPage.vue'
import OverviewPage from '@/pages/OverviewPage.vue'
import { useAuthSession, type AuthSession } from '@/auth/session'
import { onSessionExpired } from '@/api/http'

export function safeReturnPath(value: unknown): string | null {
  if (
    typeof value !== 'string' ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\')
  ) {
    return null
  }

  try {
    const target = new URL(value, 'https://flightlink-console.invalid')
    if (target.origin !== 'https://flightlink-console.invalid') return null
    return `${target.pathname}${target.search}${target.hash}`
  } catch {
    return null
  }
}

export interface AppRouterOptions {
  history?: RouterHistory
  session?: AuthSession
}

export function createAppRouter(options: AppRouterOptions = {}) {
  const session = options.session ?? useAuthSession()
  const router = createRouter({
    history: options.history ?? createWebHistory(),
    routes: [
      {
        path: '/login',
        name: 'login',
        component: LoginPage,
        meta: { title: '登录', requiresAuth: false },
      },
      {
        path: '/',
        component: AdminLayout,
        meta: { requiresAuth: true },
        children: [
          {
            path: '',
            name: 'overview',
            component: OverviewPage,
            meta: { title: '总览', requiresAuth: true },
          },
          {
            path: 'channels',
            name: 'channels',
            component: ChannelsPage,
            meta: { title: '端口组', requiresAuth: true },
          },
          {
            path: 'channels/:id',
            name: 'channel-detail',
            component: ChannelDetailPage,
            meta: { title: '端口组详情', requiresAuth: true },
          },
          {
            path: 'messages',
            name: 'messages',
            component: FlightMessagesPage,
            meta: { title: '飞控消息', requiresAuth: true },
          },
          {
            path: 'captures',
            name: 'captures',
            component: CapturesPage,
            meta: { title: '抓包文件', requiresAuth: true },
          },
          {
            path: ':pathMatch(.*)*',
            name: 'not-found',
            component: NotFoundPage,
            meta: { title: '页面不存在', requiresAuth: true },
          },
        ],
      },
    ],
  })

  router.beforeEach(async (to) => {
    if (to.meta.requiresAuth) {
      if (!session.isAuthenticated.value) {
        try {
          await session.restore()
        } catch {
          return {
            name: 'login',
            query: { redirect: safeReturnPath(to.fullPath) ?? '/' },
          }
        }
      }
      if (!session.isAuthenticated.value) {
        return {
          name: 'login',
          query: { redirect: safeReturnPath(to.fullPath) ?? '/' },
        }
      }
    } else if (to.name === 'login' && session.isAuthenticated.value) {
      return { name: 'overview' }
    }
  })

  router.afterEach((to) => {
    if (typeof document !== 'undefined' && typeof to.meta.title === 'string') {
      document.title = `${to.meta.title} · FlightLink-Console`
    }
  })

  const unsubscribe = onSessionExpired(() => {
    session.clear('登录状态已过期，请重新登录。')
    if (router.currentRoute.value.meta.requiresAuth) {
      const redirect = safeReturnPath(router.currentRoute.value.fullPath) ?? '/'
      void router.replace({ name: 'login', query: { redirect } })
    }
  })

  return { router, dispose: unsubscribe }
}

const appRouter = createAppRouter()
export const router = appRouter.router

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
  }
}
