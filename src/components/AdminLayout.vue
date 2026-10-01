<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthSession } from '@/auth/session'
import { toChineseError } from '@/api/error-message'
import StatusBadge from '@/components/StatusBadge.vue'
import { useHealthStatus } from '@/composables/useHealthStatus'
import { isPreviewMode } from '@/preview'

const route = useRoute()
const router = useRouter()
const session = useAuthSession()
const health = useHealthStatus()
const mobileMenuOpen = ref(false)
const logoutInProgress = ref(false)
const logoutError = ref<string | null>(null)
const navigation = [
  { name: 'overview', label: '总览', marker: '总' },
  { name: 'channels', label: '端口组', marker: '组' },
  { name: 'messages', label: '飞控消息', marker: '消息' },
  { name: 'captures', label: '抓包文件', marker: 'PCAP' },
]

function isCurrentSection(name: string): boolean {
  if (name === 'channels') return route.path.startsWith('/channels')
  return route.name === name
}

async function signOut(): Promise<void> {
  if (logoutInProgress.value) return
  logoutInProgress.value = true
  logoutError.value = null
  try {
    await session.logout()
    await router.replace({ name: 'login' })
  } catch (error: unknown) {
    logoutError.value = toChineseError(error, '退出登录失败，请检查网络后重试。')
  } finally {
    logoutInProgress.value = false
  }
}
</script>

<template>
  <div class="console-shell">
    <button
      class="mobile-menu-button"
      type="button"
      :aria-expanded="mobileMenuOpen"
      aria-controls="console-navigation"
      @click="mobileMenuOpen = !mobileMenuOpen"
    >
      <span aria-hidden="true">☰</span>
      <span class="visually-hidden">切换导航菜单</span>
    </button>

    <aside
      id="console-navigation"
      class="console-sidebar"
      :class="{ 'console-sidebar--open': mobileMenuOpen }"
    >
      <RouterLink
        class="console-brand"
        :to="{ name: 'overview' }"
      >
        <span
          class="console-brand__mark"
          aria-hidden="true"
        >FL</span>
        <span class="console-brand__name">
          <strong>FlightLink</strong>
          <small>控制台</small>
        </span>
      </RouterLink>

      <p class="console-nav__caption">
        运行管理
      </p>
      <nav
        class="console-nav"
        aria-label="主导航"
      >
        <RouterLink
          v-for="item in navigation"
          :key="item.name"
          :to="{ name: item.name }"
          class="console-nav__link"
          :class="{ 'console-nav__link--active': isCurrentSection(item.name) }"
          @click="mobileMenuOpen = false"
        >
          <span
            class="console-nav__marker"
            aria-hidden="true"
          >{{ item.marker }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="console-sidebar__footer">
        <span
          class="console-sidebar__footer-dot"
          aria-hidden="true"
        />
        <span>FlightLink-Console</span>
        <small>v0.1</small>
      </div>
    </aside>

    <div class="console-main">
      <header class="console-topbar">
        <div
          class="console-topbar__health"
          aria-label="服务状态"
        >
          <StatusBadge
            :state="health.apiState.value"
            label="后端服务"
          />
          <StatusBadge
            :state="health.databaseState.value"
            label="数据库"
          />
          <span
            v-if="health.error.value"
            class="console-topbar__health-error"
          >
            {{ health.error.value }}
          </span>
        </div>
        <div class="console-account">
          <span
            class="console-account__avatar"
            aria-hidden="true"
          >
            {{ session.admin.value?.username.slice(0, 1).toUpperCase() ?? 'A' }}
          </span>
          <span class="console-account__name">{{ session.admin.value?.username }}</span>
          <button
            class="console-account__logout"
            type="button"
            :disabled="logoutInProgress"
            :aria-busy="logoutInProgress"
            @click="signOut"
          >
            退出登录
          </button>
        </div>
      </header>

      <div
        v-if="logoutError"
        class="console-logout-error"
        role="alert"
      >
        {{ logoutError }} 点击“退出登录”可重试。
      </div>

      <div
        v-if="isPreviewMode"
        class="console-preview-banner"
        role="status"
      >
        <span class="console-preview-banner__tag">本地预览</span>
        <span>当前为示例遥测数据，预览请求仅由前端本地处理。</span>
      </div>

      <main class="console-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>
