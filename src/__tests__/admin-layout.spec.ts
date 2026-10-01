// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  logout: vi.fn<() => Promise<void>>(),
  replace: vi.fn<() => Promise<void>>(),
}))

vi.mock('@/auth/session', () => ({
  useAuthSession: () => ({ admin: { value: { username: 'operator' } }, logout: mocks.logout }),
}))

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  RouterView: { template: '<div />' },
  useRoute: () => ({ path: '/overview', name: 'overview' }),
  useRouter: () => ({ replace: mocks.replace }),
}))

vi.mock('@/composables/useHealthStatus', () => ({
  useHealthStatus: () => ({
    apiState: { value: 'online' },
    databaseState: { value: 'online' },
    error: { value: null },
  }),
}))

vi.mock('@/preview', () => ({ isPreviewMode: false }))

describe('administrator console layout', () => {
  beforeEach(() => {
    vi.resetModules()
    mocks.logout.mockReset()
    mocks.replace.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows logout failure and allows retry without navigating away', async () => {
    mocks.logout
      .mockRejectedValueOnce(new TypeError('Network unavailable'))
      .mockResolvedValueOnce(undefined)
    const { default: AdminLayout } = await import('@/components/AdminLayout.vue')
    const wrapper = mount(AdminLayout, {
      global: {
        stubs: {
          StatusBadge: true,
        },
      },
    })

    await wrapper.find('.console-account__logout').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('无法连接后端服务')
    expect(mocks.replace).not.toHaveBeenCalled()

    await wrapper.find('.console-account__logout').trigger('click')
    await flushPromises()

    expect(mocks.replace).toHaveBeenCalledWith({ name: 'login' })
  })

  it('disables repeated logout clicks while the request is in progress', async () => {
    let releaseLogout: () => void = () => undefined
    mocks.logout.mockReturnValue(
      new Promise<void>((resolve) => {
        releaseLogout = resolve
      }),
    )
    const { default: AdminLayout } = await import('@/components/AdminLayout.vue')
    const wrapper = mount(AdminLayout, {
      global: {
        stubs: {
          StatusBadge: true,
        },
      },
    })
    const button = wrapper.find('.console-account__logout')
    const firstClick = button.trigger('click')
    await flushPromises()

    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    await button.trigger('click')
    expect(mocks.logout).toHaveBeenCalledOnce()

    releaseLogout()
    await firstClick
    await flushPromises()
    expect(mocks.replace).toHaveBeenCalledOnce()
  })
})
