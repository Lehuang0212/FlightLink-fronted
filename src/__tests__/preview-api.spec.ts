import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import type { ViteDevServer } from 'vite'
import { afterEach, describe, expect, it } from 'vitest'
import { previewApiPlugin } from '../../dev/preview-api.ts'

type PreviewMiddleware = (
  request: IncomingMessage,
  response: ServerResponse,
  next: (error?: Error) => void,
) => void

const servers: Server[] = []

async function startPreviewApi() {
  let middleware: PreviewMiddleware | undefined
  const plugin = previewApiPlugin({ username: 'preview-admin', password: 'preview-only' })
  const configureServer = plugin.configureServer
  if (typeof configureServer !== 'function') {
    throw new Error('Preview API plugin did not provide configureServer.')
  }
  configureServer.call(plugin, {
    middlewares: {
      use: (handler: PreviewMiddleware) => {
        middleware = handler
      },
    },
  } as unknown as ViteDevServer)

  const server = createServer((request, response) => {
    if (!middleware) {
      response.writeHead(500).end()
      return
    }
    middleware(request, response, () => response.writeHead(404).end())
  })
  servers.push(server)
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const address = server.address()
  if (!address || typeof address === 'string') {
    throw new Error('Preview API test server has no TCP address.')
  }
  const baseUrl = `http://127.0.0.1:${address.port}`
  const login = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'preview-admin', password: 'preview-only' }),
  })
  const setCookie = login.headers.get('set-cookie')
  if (!setCookie) throw new Error('Preview login did not return a session cookie.')
  return { baseUrl, cookie: setCookie.split(';', 1)[0] }
}

async function previewRequest(
  baseUrl: string,
  cookie: string,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Cookie', cookie)
  return fetch(`${baseUrl}${path}`, { ...init, headers })
}

afterEach(async () => {
  await Promise.all(
    servers.splice(0).map(
      (server) => new Promise<void>((resolve, reject) => {
        server.close((error) => error ? reject(error) : resolve())
      }),
    ),
  )
})

describe('local preview API', () => {
  it('can create a port group after every sample group has been deleted', async () => {
    const { baseUrl, cookie } = await startPreviewApi()
    const initial = await previewRequest(baseUrl, cookie, '/api/v1/channels')
    const channels = await initial.json() as { id: string }[]
    for (const channel of channels) {
      const deleted = await previewRequest(
        baseUrl,
        cookie,
        `/api/v1/channels/${channel.id}`,
        { method: 'DELETE' },
      )
      expect(deleted.status).toBe(204)
    }

    const created = await previewRequest(baseUrl, cookie, '/api/v1/channels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uav_udp_port: 5762,
        ground_station_port: 14554,
        ground_station_protocol: 'tcp',
        enabled: true,
      }),
    })

    expect(created.status).toBe(201)
    expect(await created.json()).toMatchObject({
      uav_udp_port: 5762,
      ground_station_port: 14554,
      ground_station_protocol: 'tcp',
    })
  })

  it('treats TCP and UDP listeners with the same number as separate ports', async () => {
    const { baseUrl, cookie } = await startPreviewApi()
    const created = await previewRequest(baseUrl, cookie, '/api/v1/channels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uav_udp_port: 5762,
        ground_station_port: 5762,
        ground_station_protocol: 'tcp',
        enabled: true,
      }),
    })

    expect(created.status).toBe(201)
  })

  it('rejects the same UDP listener number for both endpoints', async () => {
    const { baseUrl, cookie } = await startPreviewApi()
    const created = await previewRequest(baseUrl, cookie, '/api/v1/channels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uav_udp_port: 5762,
        ground_station_port: 5762,
        ground_station_protocol: 'udp',
        enabled: true,
      }),
    })

    expect(created.status).toBe(409)
  })

  it('lists current and closed capture segments in local preview', async () => {
    const { baseUrl, cookie } = await startPreviewApi()
    const channelResponse = await previewRequest(baseUrl, cookie, '/api/v1/channels')
    const channels = await channelResponse.json() as { id: string }[]
    const channelId = channels[0]?.id
    if (!channelId) throw new Error('Preview did not provide a sample channel.')

    const response = await previewRequest(
      baseUrl,
      cookie,
      `/api/v1/channels/${channelId}/captures`,
    )
    const payload = await response.json() as {
      captures: { file_name: string; is_current: boolean }[]
    }

    expect(response.headers.get('x-flightlink-preview')).toBe('local')
    expect(response.status).toBe(200)
    expect(payload.captures).toHaveLength(2)
    expect(payload.captures.filter((capture) => capture.is_current)).toHaveLength(1)
  })

  it('only downloads a closed local preview capture segment', async () => {
    const { baseUrl, cookie } = await startPreviewApi()
    const channelResponse = await previewRequest(baseUrl, cookie, '/api/v1/channels')
    const channels = await channelResponse.json() as { id: string }[]
    const channelId = channels[0]?.id
    if (!channelId) throw new Error('Preview did not provide a sample channel.')

    const listResponse = await previewRequest(
      baseUrl,
      cookie,
      `/api/v1/channels/${channelId}/captures`,
    )
    const payload = await listResponse.json() as {
      captures: { file_name: string; is_current: boolean; size_bytes: number }[]
    }
    const currentFile = payload.captures.find((capture) => capture.is_current)
    const closedFile = payload.captures.find((capture) => !capture.is_current)
    if (!currentFile || !closedFile) throw new Error('Preview capture samples are incomplete.')

    const currentDownload = await previewRequest(
      baseUrl,
      cookie,
      `/api/v1/channels/${channelId}/captures/${currentFile.file_name}`,
    )
    const closedDownload = await previewRequest(
      baseUrl,
      cookie,
      `/api/v1/channels/${channelId}/captures/${closedFile.file_name}`,
    )

    expect(currentDownload.status).toBe(409)
    expect(closedDownload.status).toBe(200)
    expect(closedDownload.headers.get('content-type')).toContain('application/vnd.tcpdump.pcap')
    expect(closedDownload.headers.get('x-flightlink-preview')).toBe('local')
    expect((await closedDownload.arrayBuffer()).byteLength).toBe(closedFile.size_bytes)
  })
})
