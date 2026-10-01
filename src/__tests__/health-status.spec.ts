// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useHealthStatus } from '@/composables/useHealthStatus'
import type { HealthPublic } from '@/api/types'

let configuredLoader: () => Promise<HealthPublic> = async () => ({ status: 'ok', database: 'ok' })
let healthStatus!: ReturnType<typeof useHealthStatus>

const HealthStatusHost = defineComponent({
  setup() {
    healthStatus = useHealthStatus(configuredLoader, 15_000)
    return () => h('div')
  },
})

describe('health status polling', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('distinguishes API failure, database failure, and recovery', async () => {
    const fetchHealth = vi
      .fn<() => Promise<HealthPublic>>()
      .mockResolvedValueOnce({ status: 'ok', database: 'ok' })
      .mockRejectedValueOnce(new Error('Backend unavailable'))
      .mockResolvedValueOnce({ status: 'ok', database: 'error' })
    configuredLoader = fetchHealth
    const wrapper = mount(HealthStatusHost)
    await flushPromises()

    expect(healthStatus.apiState.value).toBe('available')
    expect(healthStatus.databaseState.value).toBe('available')

    await healthStatus.refresh()
    expect(healthStatus.apiState.value).toBe('unavailable')
    expect(healthStatus.databaseState.value).toBe('unavailable')

    await healthStatus.refresh()
    expect(healthStatus.apiState.value).toBe('available')
    expect(healthStatus.databaseState.value).toBe('degraded')

    wrapper.unmount()
  })

  it('pauses while the document is hidden and refreshes when it becomes visible', async () => {
    vi.useFakeTimers()
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'hidden',
    })
    const fetchHealth = vi.fn<() => Promise<HealthPublic>>()
      .mockResolvedValue({ status: 'ok', database: 'ok' })
    configuredLoader = fetchHealth
    const wrapper = mount(HealthStatusHost)
    await flushPromises()

    expect(fetchHealth).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(30_000)
    expect(fetchHealth).not.toHaveBeenCalled()

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(fetchHealth).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(15_000)
    await flushPromises()
    expect(fetchHealth).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
