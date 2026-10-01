// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('console router and login', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects unauthenticated users to login and remembers the internal path', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    )
    const [{ useAuthSession }, { createAppRouter }, { createMemoryHistory }] =
      await Promise.all([
        import('@/auth/session'),
        import('@/router'),
        import('vue-router'),
      ])
    const { router, dispose } = createAppRouter({
      session: useAuthSession(),
      history: createMemoryHistory(),
    })
    await router.push('/channels')

    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/channels')
    dispose()
  })

  it('sends an authenticated user away from login to the overview', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 7, username: 'operator' }), { status: 200 }),
    )
    const [{ useAuthSession }, { createAppRouter }, { createMemoryHistory }] =
      await Promise.all([
        import('@/auth/session'),
        import('@/router'),
        import('vue-router'),
      ])
    const session = useAuthSession()
    const { router, dispose } = createAppRouter({
      session,
      history: createMemoryHistory(),
    })
    await session.login({ username: 'operator', password: 'secret' })
    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('overview')
    dispose()
  })

  it('renders the shared console navigation and service health in a protected route', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 7, username: 'operator' }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: 'ok', database: 'ok' }), { status: 200 }),
      )
    const [
      { useAuthSession },
      { createAppRouter },
      { createMemoryHistory },
      { default: App },
    ] = await Promise.all([
      import('@/auth/session'),
      import('@/router'),
      import('vue-router'),
      import('@/App.vue'),
    ])
    const session = useAuthSession()
    const { router, dispose } = createAppRouter({
      session,
      history: createMemoryHistory(),
    })
    await session.login({ username: 'operator', password: 'secret' })
    await router.push('/messages')
    const wrapper = mount(App, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('端口组')
    expect(wrapper.text()).toContain('飞控消息')
    expect(wrapper.text()).toContain('operator')
    expect(wrapper.text()).toContain('后端服务')
    expect(wrapper.text()).toContain('数据库')
    wrapper.unmount()
    dispose()
  })

  it('accepts only same-app return paths', async () => {
    const { safeReturnPath } = await import('@/router')

    expect(safeReturnPath('/channels/abc?tab=runtime')).toBe(
      '/channels/abc?tab=runtime',
    )
    expect(safeReturnPath('//outside.example')).toBeNull()
    expect(safeReturnPath('https://outside.example')).toBeNull()
    expect(safeReturnPath('/\\\\outside.example')).toBeNull()
  })

  it('shows invalid credentials on login and keeps the user on that page', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid username or password' }), {
        status: 401,
      }),
    )
    const [{ useAuthSession }, { createAppRouter }, { createMemoryHistory }] =
      await Promise.all([
        import('@/auth/session'),
        import('@/router'),
        import('vue-router'),
      ])
    const { default: LoginPage } = await import('@/pages/LoginPage.vue')
    const { router, dispose } = createAppRouter({
      session: useAuthSession(),
      history: createMemoryHistory(),
    })
    await router.push('/login?redirect=%2Fchannels')
    const wrapper = mount(LoginPage, { global: { plugins: [router] } })
    await wrapper.get('#username').setValue('operator')
    await wrapper.get('#password').setValue('wrong')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('用户名或密码错误')
    expect(router.currentRoute.value.path).toBe('/login')
    wrapper.unmount()
    dispose()
  })

  it('redirects to login when a protected request expires the session', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 7, username: 'operator' }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
      )
    const [{ useAuthSession }, { apiRequest }, { createAppRouter }, { createMemoryHistory }] =
      await Promise.all([
        import('@/auth/session'),
        import('@/api/http'),
        import('@/router'),
        import('vue-router'),
      ])
    const session = useAuthSession()
    const { router, dispose } = createAppRouter({
      session,
      history: createMemoryHistory(),
    })
    await session.login({ username: 'operator', password: 'secret' })
    await router.push('/channels')

    await expect(apiRequest('/channels')).rejects.toMatchObject({ status: 401 })
    await flushPromises()

    expect(session.isAuthenticated.value).toBe(false)
    expect(router.currentRoute.value.path).toBe('/login')
    dispose()
  })
})
