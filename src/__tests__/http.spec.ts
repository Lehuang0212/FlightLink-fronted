import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiDownload, apiRequest, onSessionExpired } from '@/api/http'

describe('API HTTP client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the same-origin API prefix and includes the session cookie', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200 }),
    )

    await expect(apiRequest('/channels')).resolves.toEqual([])
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/channels',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('does not try to parse a 204 response as JSON', async () => {
    const response = new Response(null, { status: 204 })
    const jsonSpy = vi.spyOn(response, 'json')
    vi.mocked(fetch).mockResolvedValueOnce(response)

    await expect(apiRequest('/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
    expect(jsonSpy).not.toHaveBeenCalled()
  })

  it('maps FastAPI detail responses to readable API errors', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Ground station port is already in use' }), {
        status: 409,
      }),
    )

    await expect(apiRequest('/channels', { method: 'POST' })).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      message: 'Ground station port is already in use',
    })
  })

  it('notifies listeners when a protected request returns 401', async () => {
    const listener = vi.fn()
    const unsubscribe = onSessionExpired(listener)
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    )

    await expect(apiRequest('/channels')).rejects.toBeInstanceOf(ApiError)
    expect(listener).toHaveBeenCalledOnce()
    unsubscribe()
  })

  it('keeps login credential errors local to the login form', async () => {
    const listener = vi.fn()
    const unsubscribe = onSessionExpired(listener)
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Invalid username or password' }), {
        status: 401,
      }),
    )

    await expect(
      apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: 'operator', password: 'wrong' }),
      }),
    ).rejects.toMatchObject({ message: 'Invalid username or password' })
    expect(listener).not.toHaveBeenCalled()
    unsubscribe()
  })

  it('downloads a binary response with the session cookie', async () => {
    const file = new Blob(['pcap-data'], { type: 'application/vnd.tcpdump.pcap' })
    vi.mocked(fetch).mockResolvedValueOnce(new Response(file, { status: 200 }))

    const result = await apiDownload('/channels/a/captures/flight.pcap')

    expect(result.type).toBe('application/vnd.tcpdump.pcap')
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/channels/a/captures/flight.pcap',
      expect.objectContaining({ credentials: 'include' }),
    )
  })
})
