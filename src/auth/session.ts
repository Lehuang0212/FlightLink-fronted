import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { getCurrentAdmin, loginAdmin, logoutAdmin } from '@/api/auth'
import { toChineseError } from '@/api/error-message'
import { ApiError, onSessionExpired } from '@/api/http'
import { advanceSessionEpoch, currentSessionEpoch } from '@/auth/session-epoch'
import type { AdminPublic, LoginRequest } from '@/api/types'

export interface AuthSession {
  admin: Ref<AdminPublic | null>
  isAuthenticated: ComputedRef<boolean>
  restoreError: Ref<string | null>
  restore(): Promise<AdminPublic | null>
  login(input: LoginRequest): Promise<AdminPublic>
  logout(): Promise<void>
  clear(message?: string | null): void
}

const admin = ref<AdminPublic | null>(null)
const isAuthenticated = computed(() => admin.value !== null)
const restoreError = ref<string | null>(null)
let restoreAttempted = false
let restorePromise: Promise<AdminPublic | null> | null = null
let logoutPromise: Promise<void> | null = null

function clear(message: string | null = null): void {
  advanceSessionEpoch()
  admin.value = null
  restoreAttempted = true
  restoreError.value = message
}

onSessionExpired(() => clear('登录状态已过期，请重新登录。'))

async function restore(): Promise<AdminPublic | null> {
  if (admin.value) return admin.value
  if (restoreAttempted) return null
  if (restorePromise) return restorePromise

  const requestEpoch = currentSessionEpoch()
  restorePromise = getCurrentAdmin()
    .then((currentAdmin) => {
      if (requestEpoch !== currentSessionEpoch()) return admin.value
      admin.value = currentAdmin
      restoreAttempted = true
      restoreError.value = null
      return currentAdmin
    })
    .catch((error: unknown) => {
      if (requestEpoch !== currentSessionEpoch()) return admin.value
      restoreAttempted = true
      if (error instanceof ApiError && error.status === 401) {
        admin.value = null
        return null
      }
      restoreError.value = toChineseError(error, '无法恢复登录状态，请重新登录。')
      throw error
    })
    .finally(() => {
      restorePromise = null
    })

  return restorePromise
}

async function login(input: LoginRequest): Promise<AdminPublic> {
  if (logoutPromise) await logoutPromise.catch(() => undefined)
  const authenticatedAdmin = await loginAdmin(input)
  advanceSessionEpoch()
  admin.value = authenticatedAdmin
  restoreAttempted = true
  restoreError.value = null
  return authenticatedAdmin
}

function logout(): Promise<void> {
  if (logoutPromise) return logoutPromise

  const requestEpoch = currentSessionEpoch()
  logoutPromise = logoutAdmin()
    .then(() => {
      if (requestEpoch === currentSessionEpoch()) clear()
    })
    .catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        if (requestEpoch === currentSessionEpoch()) clear()
        return
      }
      throw error
    })
    .finally(() => {
      logoutPromise = null
    })

  return logoutPromise
}

const session: AuthSession = {
  admin,
  isAuthenticated,
  restoreError,
  restore,
  login,
  logout,
  clear,
}

export function useAuthSession(): AuthSession {
  return session
}
