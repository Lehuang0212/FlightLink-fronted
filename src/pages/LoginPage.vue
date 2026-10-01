<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthSession } from '@/auth/session'
import { toChineseError } from '@/api/error-message'
import { isPreviewMode } from '@/preview'
import { safeReturnPath } from '@/router'

const route = useRoute()
const router = useRouter()
const session = useAuthSession()
const username = ref('')
const password = ref('')
const submitting = ref(false)
const errorMessage = ref(session.restoreError.value)

watch(
  () => session.restoreError.value,
  (message) => {
    if (message) errorMessage.value = message
  },
)

async function submitLogin(): Promise<void> {
  if (submitting.value) return
  submitting.value = true
  errorMessage.value = null

  try {
    await session.login({ username: username.value.trim(), password: password.value })
    await router.replace(safeReturnPath(route.query.redirect) ?? '/')
  } catch (error: unknown) {
    errorMessage.value = toChineseError(error, '登录失败，请检查连接后重试。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-screen">
    <section
      class="login-brand"
      aria-label="FlightLink-Console"
    >
      <div
        class="login-brand__mark"
        aria-hidden="true"
      >
        FL
      </div>
      <p class="login-brand__eyebrow">
        FLIGHTLINK · 飞行运行管理
      </p>
      <h1>FlightLink-Console</h1>
      <p class="login-brand__description">
        安全管理 MAVLink 端口组与链路服务。
      </p>
      <div class="login-brand__footer">
        仅限管理员访问
      </div>
    </section>

    <section
      class="login-panel"
      aria-labelledby="login-title"
    >
      <div class="login-panel__heading">
        <p class="login-panel__eyebrow">
          管理员
        </p>
        <h2 id="login-title">
          登录
        </h2>
        <p>请使用服务器管理员创建的账号登录。</p>
      </div>

      <form
        class="login-form"
        @submit.prevent="submitLogin"
      >
        <label for="username">用户名</label>
        <input
          id="username"
          v-model="username"
          name="username"
          type="text"
          autocomplete="username"
          required
          maxlength="64"
          :disabled="submitting"
        >

        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          name="password"
          type="password"
          autocomplete="current-password"
          required
          maxlength="1024"
          :disabled="submitting"
        >

        <p
          v-if="errorMessage"
          class="login-error"
          role="alert"
        >
          {{ errorMessage }}
        </p>

        <button
          class="login-submit"
          type="submit"
          :disabled="submitting"
        >
          {{ submitting ? '正在登录…' : '登录' }}
        </button>
      </form>

      <p
        v-if="isPreviewMode"
        class="login-preview-note"
      >
        当前为本地预览模式，显示示例遥测数据。
      </p>

      <p class="login-panel__note">
        管理员账号由服务器端命令行创建，不支持自助注册。
      </p>
    </section>
  </main>
</template>
