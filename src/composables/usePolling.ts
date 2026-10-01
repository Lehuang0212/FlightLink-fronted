import {
  computed,
  onMounted,
  onUnmounted,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from 'vue'

export function usePolling<T>(
  loader: () => Promise<T>,
  intervalMs: number,
  enabled: MaybeRefOrGetter<boolean> = true,
  key?: MaybeRefOrGetter<unknown>,
) {
  const data = shallowRef<T>()
  const error = shallowRef<unknown>(null)
  const loading = shallowRef(false)
  const enabledValue = computed(() => toValue(enabled))
  const keyValue = computed(() => (key === undefined ? undefined : toValue(key)))
  let timer: ReturnType<typeof setInterval> | undefined
  let inFlight: Promise<void> | null = null
  let refreshQueued = false
  let mounted = false
  let requestGeneration = 0

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
    if (mounted && enabledValue.value && isVisible()) {
      timer = setInterval(() => void refresh(), intervalMs)
    }
  }

  function onVisibilityChange(): void {
    if (!isVisible()) {
      clearTimer()
      return
    }
    if (!enabledValue.value) return
    startTimer()
    void refresh()
  }

  async function refresh(): Promise<void> {
    if (inFlight) {
      refreshQueued = true
      return inFlight
    }

    loading.value = true
    const generation = requestGeneration
    const request = Promise.resolve()
      .then(loader)
      .then((result) => {
        if (!mounted || generation !== requestGeneration) return
        data.value = result
        error.value = null
      })
      .catch((reason: unknown) => {
        if (mounted && generation === requestGeneration) error.value = reason
      })
      .finally(() => {
        if (!mounted) return
        loading.value = false
        inFlight = null
        if (refreshQueued && enabledValue.value && isVisible()) {
          refreshQueued = false
          void refresh()
        } else {
          refreshQueued = false
        }
      })
    inFlight = request
    return request
  }

  watch([enabledValue, keyValue], ([isEnabled, currentKey], [wasEnabled, previousKey]) => {
    if (!mounted) return
    const keyChanged = !Object.is(currentKey, previousKey)
    if (isEnabled !== wasEnabled || keyChanged) requestGeneration += 1
    if (keyChanged) {
      data.value = undefined
      error.value = null
    }
    if (!isEnabled) {
      clearTimer()
      refreshQueued = false
      return
    }
    startTimer()
    if (isVisible()) void refresh()
  })

  onMounted(() => {
    mounted = true
    document.addEventListener('visibilitychange', onVisibilityChange)
    if (enabledValue.value && isVisible()) {
      startTimer()
      void refresh()
    }
  })

  onUnmounted(() => {
    mounted = false
    clearTimer()
    refreshQueued = false
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return { data, error, loading, refresh }
}
