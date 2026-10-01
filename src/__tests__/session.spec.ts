import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('administrator session', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('restores the administrator from the HttpOnly cookie once', async () => {
    const admin = { id: 7, username: 'operator' }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(admin), { status: 200 }),
    )
    const { useAuthSession } = await import('@/auth/session')
    const session = useAuthSession()

    await expect(session.restore()).resolves.toEqual(admin)
    await expect(session.restore()).resolves.toEqual(admin)
    expect(session.isAuthenticated.value).toBe(true)
    expect(fetch).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/me',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('sets administrator state after a successful login', async () => {
    const admin = { id: 7, username: 'operator' }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(admin), { status: 200 }),
    )
    const { useAuthSession } = await import('@/auth/session')
    const session = useAuthSession()

    await session.login({ username: 'operator', password: 'secret' })

    expect(session.admin.value).toEqual(admin)
    expect(session.isAuthenticated.value).toBe(true)
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ username: 'operator', password: 'secret' }),
      }),
    )
  })

  it('clears local administrator state after logout', async () => {
    const admin = { id: 7, username: 'operator' }
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(admin), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    const { useAuthSession } = await import('@/auth/session')
    const session = useAuthSession()
    await session.login({ username: 'operator', password: 'secret' })

    await session.logout()

    expect(session.admin.value).toBeNull()
    expect(session.isAuthenticated.value).toBe(false)
    expect(fetch).toHaveBeenLastCalledWith(
      '/api/v1/auth/logout',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })

  it('keeps the administrator session when the logout request fails', async () => {
    const admin = { id: 7, username: 'operator' }
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(admin), { status: 200 }))
      .mockRejectedValueOnce(new TypeError('Network unavailable'))
    const { useAuthSession } = await import('@/auth/session')
    const session = useAuthSession()
    await session.login({ username: 'operator', password: 'secret' })

    await expect(session.logout()).rejects.toThrow('Network unavailable')

    expect(session.admin.value).toEqual(admin)
    expect(session.isAuthenticated.value).toBe(true)
  })

  it('clears session state when a protected request reports 401', async () => {
    const admin = { id: 7, username: 'operator' }
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(admin), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
      )
    const { useAuthSession } = await import('@/auth/session')
    const { apiRequest } = await import('@/api/http')
    const session = useAuthSession()
    await session.login({ username: 'operator', password: 'secret' })

    await expect(apiRequest('/channels')).rejects.toMatchObject({ status: 401 })

    expect(session.admin.value).toBeNull()
    expect(session.isAuthenticated.value).toBe(false)
  })

  it('does not let a delayed 401 from an older session clear a new login', async () => {
    const admin = { id: 7, username: 'operator' }
    let releaseOldRequest: (response: Response) => void = () => undefined
    const oldRequestResponse = new Promise<Response>((resolve) => {
      releaseOldRequest = resolve
    })
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input)
      if (url.endsWith('/channels')) return oldRequestResponse
      if (url.endsWith('/auth/login')) {
        return Promise.resolve(new Response(JSON.stringify(admin), { status: 200 }))
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    const { useAuthSession } = await import('@/auth/session')
    const { apiRequest } = await import('@/api/http')
    const session = useAuthSession()
    const oldRequest = apiRequest('/channels')
    await session.login({ username: 'operator', password: 'secret' })

    releaseOldRequest(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    )
    await expect(oldRequest).rejects.toMatchObject({ status: 401 })

    expect(session.admin.value).toEqual(admin)
    expect(session.isAuthenticated.value).toBe(true)
  })

  it('runs one logout and waits for its response before establishing a new session', async () => {
    const admin = { id: 7, username: 'operator' }
    let releaseLogout: (response: Response) => void = () => undefined
    const logoutResponse = new Promise<Response>((resolve) => {
      releaseLogout = resolve
    })
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input)
      if (url.endsWith('/auth/login')) {
        return Promise.resolve(new Response(JSON.stringify(admin), { status: 200 }))
      }
      if (url.endsWith('/auth/logout')) return logoutResponse
      throw new Error(`Unexpected request: ${url}`)
    })
    const { useAuthSession } = await import('@/auth/session')
    const session = useAuthSession()
    await session.login({ username: 'operator', password: 'secret' })

    const firstLogout = session.logout()
    const duplicateLogout = session.logout()
    const nextLogin = session.login({ username: 'operator', password: 'secret' })
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/auth/login'))).toHaveLength(1)

    releaseLogout(new Response(null, { status: 204 }))
    await Promise.all([firstLogout, duplicateLogout])
    await nextLogin

    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/auth/logout'))).toHaveLength(1)
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/auth/login'))).toHaveLength(2)
    expect(session.admin.value).toEqual(admin)
    expect(session.isAuthenticated.value).toBe(true)
  })
})
