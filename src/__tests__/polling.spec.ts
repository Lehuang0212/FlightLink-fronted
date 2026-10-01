// @vitest-environment jsdom
/* eslint vue/one-component-per-file: off */
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePolling } from '@/composables/usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads immediately and polls every three seconds', async () => {
    const loader = vi.fn().mockResolvedValue('fresh')
    let polling!: ReturnType<typeof usePolling<string>>
    const Host = defineComponent({
      setup() {
        polling = usePolling(loader, 3_000)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)
    await flushPromises()

    expect(loader).toHaveBeenCalledTimes(1)
    expect(polling.data.value).toBe('fresh')
    await vi.advanceTimersByTimeAsync(2_999)
    expect(loader).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(loader).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('pauses while hidden and refreshes when the page becomes visible', async () => {
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'hidden',
    })
    const loader = vi.fn().mockResolvedValue('fresh')
    const Host = defineComponent({
      setup() {
        usePolling(loader, 3_000)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)
    await vi.advanceTimersByTimeAsync(6_000)
    expect(loader).not.toHaveBeenCalled()

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(loader).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('does not overlap requests and performs one queued refresh', async () => {
    let resolveFirst!: (value: string) => void
    const loader = vi
      .fn<() => Promise<string>>()
      .mockImplementationOnce(
        () => new Promise((resolve) => { resolveFirst = resolve }),
      )
      .mockResolvedValue('second')
    let polling!: ReturnType<typeof usePolling<string>>
    const Host = defineComponent({
      setup() {
        polling = usePolling(loader, 3_000)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)

    const firstRefresh = polling.refresh()
    await Promise.resolve()
    expect(loader).toHaveBeenCalledTimes(1)
    const queuedRefresh = polling.refresh()
    expect(loader).toHaveBeenCalledTimes(1)

    resolveFirst('first')
    await Promise.all([firstRefresh, queuedRefresh])
    await flushPromises()

    expect(loader).toHaveBeenCalledTimes(2)
    expect(polling.data.value).toBe('second')
    wrapper.unmount()
  })

  it('reacts to an enabled ref and preserves data after a failed refresh', async () => {
    const enabled = ref(false)
    const loader = vi
      .fn<() => Promise<string>>()
      .mockResolvedValueOnce('cached')
      .mockRejectedValueOnce(new Error('offline'))
    let polling!: ReturnType<typeof usePolling<string>>
    const Host = defineComponent({
      setup() {
        polling = usePolling(loader, 3_000, enabled)
        return () => h('div')
      },
    })
    const wrapper = mount(Host)
    expect(loader).not.toHaveBeenCalled()

    enabled.value = true
    await flushPromises()
    expect(loader).toHaveBeenCalledTimes(1)
    await polling.refresh()
    expect(polling.data.value).toBe('cached')
    expect(polling.error.value).toEqual(new Error('offline'))

    wrapper.unmount()
  })
})
