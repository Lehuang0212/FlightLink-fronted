import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getHealth } from '@/api/health'
import { toChineseError } from '@/api/error-message'
import type { HealthPublic } from '@/api/types'

export type HealthIndicatorState =
  | 'checking'
  | 'available'
  | 'degraded'
  | 'unavailable'

export function useHealthStatus(
  loader: () => Promise<HealthPublic> = getHealth,
  intervalMs = 15_000,
) {
  const health = ref<HealthPublic | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  const apiState = computed<HealthIndicatorState>(() => {
    if (error.value) return 'unavailable'
    if (!health.value) return 'checking'
    return health.value.status === 'ok' ? 'available' : 'degraded'
  })
  const databaseState = computed<HealthIndicatorState>(() => {
    if (error.value) return 'unavailable'
    if (!health.value) return 'checking'
    return health.value.database === 'ok' ? 'available' : 'degraded'
  })

  let timer: ReturnType<typeof setInterval> | undefined
  let inFlight: Promise<void> | null = null
  let mounted = false

  function isVisible(): boolean {
    return typeof document === 'undefined' || document.visibilityState !== 'hidden'
  }

  function clearTimer(): void {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  }

  function startTimer(): void {
    clearTimer()
    if (mounted && isVisible()) {
      timer = setInterval(() => void refresh(), intervalMs)
    }
  }

  function onVisibilityChange(): void {
    if (!isVisible()) {
      clearTimer()
      return
    }
    startTimer()
    void refresh()
  }

  async function refresh(): Promise<void> {
    if (inFlight) return inFlight
    loading.value = true
    inFlight = loader()
      .then((result) => {
        health.value = result
        error.value = null
      })
      .catch((reason: unknown) => {
        error.value = toChineseError(reason, '健康检查失败，请检查后端服务。')
      })
      .finally(() => {
        loading.value = false
        inFlight = null
      })
    return inFlight
  }

  onMounted(() => {
    mounted = true
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange)
    }
    if (isVisible()) {
      startTimer()
      void refresh()
    }
  })

  onUnmounted(() => {
    mounted = false
    clearTimer()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  })

  return { health, loading, error, apiState, databaseState, refresh }
}
