import { randomBytes, timingSafeEqual } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import type { CaptureFilePublic, ChannelPublic, ChannelWrite } from '../src/api/types.ts'

interface PreviewCredentials {
  username: string
  password: string
}

interface PreviewSession {
  username: string
  expiresAt: number
}

const sessionCookie = 'flightlink_preview_session'
const sessionLifetimeSeconds = 8 * 60 * 60
const sessions = new Map<string, PreviewSession>()

function writeJson(
  response: ServerResponse,
  status: number,
  payload: unknown,
  additionalHeaders: Record<string, string> = {},
): void {
  response.writeHead(status, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
    'X-FlightLink-Preview': 'local',
    ...additionalHeaders,
  })
  response.end(JSON.stringify(payload))
}

function writeNoContent(
  response: ServerResponse,
  additionalHeaders: Record<string, string> = {},
): void {
  response.writeHead(204, {
    'Cache-Control': 'no-store',
    'X-FlightLink-Preview': 'local',
    ...additionalHeaders,
  })
  response.end()
}

function safeEqual(actual: string, expected: string): boolean {
  const actualBytes = Buffer.from(actual)
  const expectedBytes = Buffer.from(expected)
  return (
    actualBytes.length === expectedBytes.length &&
    timingSafeEqual(actualBytes, expectedBytes)
  )
}

function readRequestBody(request: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = ''
    request.setEncoding('utf8')
    request.on('data', (chunk: string) => {
      body += chunk
      if (body.length > 8_192) {
        reject(new Error('Request body too large'))
        request.destroy()
      }
    })
    request.on('end', () => resolve(body))
    request.on('error', reject)
  })
}

function cookieValue(request: IncomingMessage, name: string): string | null {
  const cookies = request.headers.cookie?.split(';') ?? []
  const entry = cookies.find((cookie) => cookie.trim().startsWith(`${name}=`))
  if (!entry) return null
  return decodeURIComponent(entry.trim().slice(name.length + 1))
}

function previewChannels(): ChannelPublic[] {
  const sharedTelemetry = {
    monitor_state: 'listening',
    monitor_error: null,
    uav_peer: '198.51.100.24:38211',
    component_id: 1,
    vehicle_type: 'QUADROTOR',
    autopilot: 'ArduPilot',
    flight_mode: 'AUTO',
    armed: true,
    battery_remaining_percent: 82,
    battery_voltage_v: 15.8,
    gps_fix_type: 3,
    gps_satellites: 21,
    altitude_m: 78,
    relative_altitude_m: 32,
    ground_speed_m_s: 11.2,
    link_quality_percent: 93,
    packets_received_window: 980,
    packets_lost_window: 2,
    last_packet_at: '2026-09-30T12:00:00Z',
    last_packet_age_seconds: 0.12,
    uav_rx_bytes_per_second: 4_800,
    gcs_tx_bytes_per_second: 1_200,
    ground_station_peer: '192.0.2.45:59231',
    ground_station_last_packet_at: '2026-09-30T12:00:00Z',
    radio_status: null,
  }
  const runtime = {
    state: 'active',
    substate: 'running',
    pid: 4812,
    active_since: '2026-09-28T01:00:00Z',
    result: null,
    error: null,
  }
  const captureRuntime = {
    state: 'active',
    substate: 'running',
    pid: 4820,
    active_since: '2026-09-28T01:00:00Z',
    result: null,
    error: null,
  }
  const base = {
    ground_station_protocol: 'tcp',
    enabled: true,
    config_file_name: 'preview.conf',
    created_at: '2026-09-28T01:00:00Z',
    updated_at: '2026-09-30T12:00:00Z',
    security_group: { state: 'synced', error: null },
    runtime,
    capture_runtime: captureRuntime,
  }

  return [
    {
      ...base,
      id: '00000000-0000-4000-8000-000000005760',
      uav_udp_port: 5760,
      ground_station_port: 14552,
      monitor_udp_port: 15760,
      config_file_name: 'preview-5760-14552.conf',
      telemetry: {
        ...sharedTelemetry,
        uav_online: true,
        system_id: 1,
        ground_station_connected: true,
      },
    },
    {
      ...base,
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
      monitor_udp_port: 15761,
      config_file_name: 'preview-5761-14553.conf',
      telemetry: {
        ...sharedTelemetry,
        uav_online: false,
        system_id: null,
        flight_mode: null,
        armed: null,
        battery_remaining_percent: null,
        battery_voltage_v: null,
        gps_fix_type: null,
        gps_satellites: null,
        altitude_m: null,
        relative_altitude_m: null,
        ground_speed_m_s: null,
        link_quality_percent: null,
        packets_received_window: 0,
        packets_lost_window: 0,
        last_packet_at: null,
        last_packet_age_seconds: null,
        uav_rx_bytes_per_second: 0,
        gcs_tx_bytes_per_second: 0,
        ground_station_connected: false,
        ground_station_peer: null,
        ground_station_last_packet_at: null,
      },
    },
  ] as unknown as ChannelPublic[]
}

const previewDefaults = previewChannels()

function listenerKeys(channel: ChannelWrite): string[] {
  return [
    `udp:${channel.uav_udp_port}`,
    `${channel.ground_station_protocol}:${channel.ground_station_port}`,
  ]
}

function hasListenerConflict(
  candidate: ChannelWrite,
  existing: ChannelPublic[],
): boolean {
  const candidateKeys = listenerKeys(candidate)
  if (new Set(candidateKeys).size !== candidateKeys.length) return true
  const candidateKeySet = new Set(candidateKeys)
  return existing.some((channel) =>
    listenerKeys(channel).some((key) => candidateKeySet.has(key)),
  )
}

function sampleLogs(): string[] {
  return [
    'Sep 30 12:00:00 mavlink-router[4812]: Router started',
    'Sep 30 12:00:01 mavlink-router[4812]: UDP endpoint 0.0.0.0:5760 listening',
    'Sep 30 12:00:02 mavlink-router[4812]: TCP server listening on 0.0.0.0:14552',
  ]
}

function sampleMessages(): { received_at: string; severity: number; severity_name: string; text: string }[] {
  return [
    {
      received_at: new Date().toISOString(),
      severity: 6,
      severity_name: 'INFO',
      text: 'EKF3 IMU0 is using GPS',
    },
    {
      received_at: new Date(Date.now() - 5_000).toISOString(),
      severity: 4,
      severity_name: 'WARNING',
      text: 'Battery failsafe',
    },
  ]
}

function samplePackets(port: number): { captured_at: string; protocol: string; source: string; destination: string; length_bytes: number; summary: string }[] {
  return [
    {
      captured_at: new Date().toISOString(),
      protocol: 'MAVLink 2',
      source: '198.51.100.24:38211',
      destination: `127.0.0.1:${port}`,
      length_bytes: 42,
      summary: 'HEARTBEAT sysid=1 compid=1',
    },
    {
      captured_at: new Date(Date.now() - 250).toISOString(),
      protocol: 'MAVLink 2',
      source: `127.0.0.1:${port}`,
      destination: '198.51.100.24:38211',
      length_bytes: 28,
      summary: 'ATTITUDE sysid=1 compid=1',
    },
  ]
}

function sampleCaptureFiles(channel: ChannelPublic): CaptureFilePublic[] {
  const newestIsCurrent = channel.capture_runtime.state === 'active'
  return [
    {
      file_name: `channel-${channel.id}-a1b2c3d4-20260930-120000-1790769600.pcap`,
      started_at: '2026-09-30T12:00:00Z',
      size_bytes: 456_789,
      is_current: newestIsCurrent,
    },
    {
      file_name: `channel-${channel.id}-a1b2c3d4-20260930-110000-1790766000.pcap`,
      started_at: '2026-09-30T11:00:00Z',
      size_bytes: samplePcapHeader().byteLength,
      is_current: false,
    },
  ]
}

function samplePcapHeader(): Buffer {
  const header = Buffer.alloc(24)
  header.writeUInt32LE(0xa1b2c3d4, 0)
  header.writeUInt16LE(2, 4)
  header.writeUInt16LE(4, 6)
  header.writeInt32LE(0, 8)
  header.writeUInt32LE(0, 12)
  header.writeUInt32LE(65_535, 16)
  header.writeUInt32LE(1, 20)
  return header
}

function writePreviewPcap(response: ServerResponse, fileName: string): void {
  const contents = samplePcapHeader()
  response.writeHead(200, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/vnd.tcpdump.pcap',
    'Content-Length': String(contents.byteLength),
    'Content-Disposition': `attachment; filename="${fileName}"`,
    'X-FlightLink-Preview': 'local',
  })
  response.end(contents)
}

async function handleRequest(
  request: IncomingMessage,
  response: ServerResponse,
  url: URL,
  credentials: PreviewCredentials,
  channels: ChannelPublic[],
): Promise<void> {
  const path = url.pathname
  const method = request.method ?? 'GET'

  if (method === 'OPTIONS') {
    writeNoContent(response)
    return
  }

  if (path === '/api/v1/health' && method === 'GET') {
    writeJson(response, 200, { status: 'ok', database: 'ok' })
    return
  }

  if (path === '/api/v1/auth/login' && method === 'POST') {
    if (!credentials.username || !credentials.password) {
      writeJson(response, 503, {
        detail: 'Local preview credentials are not configured.',
      })
      return
    }

    let input: unknown
    try {
      input = JSON.parse(await readRequestBody(request))
    } catch {
      writeJson(response, 400, { detail: 'Invalid login request.' })
      return
    }
    const login =
      typeof input === 'object' && input !== null
        ? (input as { username?: unknown; password?: unknown })
        : {}
    if (
      typeof login.username !== 'string' ||
      typeof login.password !== 'string' ||
      !safeEqual(login.username, credentials.username) ||
      !safeEqual(login.password, credentials.password)
    ) {
      writeJson(response, 401, { detail: 'Invalid username or password.' })
      return
    }

    const token = randomBytes(32).toString('base64url')
    sessions.set(token, {
      username: credentials.username,
      expiresAt: Date.now() + sessionLifetimeSeconds * 1_000,
    })
    writeJson(
      response,
      200,
      { id: 1, username: credentials.username },
      {
        'Set-Cookie': `${sessionCookie}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${sessionLifetimeSeconds}`,
      },
    )
    return
  }

  const token = cookieValue(request, sessionCookie)
  const session = token ? sessions.get(token) : undefined
  if (!session || session.expiresAt <= Date.now()) {
    if (token) sessions.delete(token)
    writeJson(response, 401, { detail: 'Not authenticated.' })
    return
  }

  if (path === '/api/v1/auth/me' && method === 'GET') {
    writeJson(response, 200, { id: 1, username: session.username })
    return
  }

  if (path === '/api/v1/auth/logout' && method === 'POST') {
    if (token) sessions.delete(token)
    writeNoContent(response, {
      'Set-Cookie': `${sessionCookie}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`,
    })
    return
  }

  if (path === '/api/v1/channels' && method === 'GET') {
    writeJson(response, 200, channels)
    return
  }

  if (path === '/api/v1/channels' && method === 'POST') {
    let input: ChannelWrite
    try {
      input = JSON.parse(await readRequestBody(request)) as ChannelWrite
    } catch {
      writeJson(response, 400, { detail: 'Invalid channel request.' })
      return
    }
    if (channels.length >= 5) {
      writeJson(response, 409, { detail: 'The preview supports up to five channels.' })
      return
    }
    if (hasListenerConflict(input, channels)) {
      writeJson(response, 409, { detail: 'A port conflict was found.' })
      return
    }
    const template = previewDefaults[0]
    if (!template) throw new Error('The preview channel template is missing.')
    const telemetry = previewDefaults[1]?.telemetry ?? template.telemetry
    const now = new Date().toISOString()
    const created: ChannelPublic = {
      ...template,
      ...input,
      id: `00000000-0000-4000-8000-${String(input.uav_udp_port).padStart(12, '0')}`,
      monitor_udp_port: input.uav_udp_port + 10_000,
      config_file_name: `preview-${input.uav_udp_port}-${input.ground_station_port}.conf`,
      created_at: now,
      updated_at: now,
      telemetry: { ...telemetry },
    }
    channels.push(created)
    writeJson(response, 201, created)
    return
  }

  const captureListMatch = path.match(/^\/api\/v1\/channels\/([^/]+)\/captures$/)
  if (captureListMatch && method === 'GET') {
    const id = decodeURIComponent(captureListMatch[1] ?? '')
    const channel = channels.find((item) => item.id === id)
    if (!channel) {
      writeJson(response, 404, { detail: 'Port group not found.' })
      return
    }
    writeJson(response, 200, {
      channel_id: id,
      captures: sampleCaptureFiles(channel),
    })
    return
  }

  const captureDownloadMatch = path.match(/^\/api\/v1\/channels\/([^/]+)\/captures\/([^/]+)$/)
  if (captureDownloadMatch && method === 'GET') {
    let id: string
    let fileName: string
    try {
      id = decodeURIComponent(captureDownloadMatch[1] ?? '')
      fileName = decodeURIComponent(captureDownloadMatch[2] ?? '')
    } catch {
      writeJson(response, 404, { detail: 'Capture file not found.' })
      return
    }
    const channel = channels.find((item) => item.id === id)
    if (!channel) {
      writeJson(response, 404, { detail: 'Port group not found.' })
      return
    }
    const capture = sampleCaptureFiles(channel).find((item) => item.file_name === fileName)
    if (!capture) {
      writeJson(response, 404, { detail: 'Capture file not found.' })
      return
    }
    if (capture.is_current) {
      writeJson(response, 409, {
        detail: 'The newest capture segment is still being written',
      })
      return
    }
    writePreviewPcap(response, capture.file_name)
    return
  }

  const channelMatch = path.match(/^\/api\/v1\/channels\/([^/]+)(?:\/(logs|messages|packets|restart))?$/)
  if (channelMatch) {
    const id = decodeURIComponent(channelMatch[1])
    const channelIndex = channels.findIndex((channel) => channel.id === id)
    if (channelIndex < 0) {
      writeJson(response, 404, { detail: 'Port group not found.' })
      return
    }
    const channel = channels[channelIndex]
    const resource = channelMatch[2]
    if (method === 'GET' && !resource) {
      writeJson(response, 200, channel)
      return
    }
    if (method === 'GET' && resource === 'logs') {
      writeJson(response, 200, { lines: sampleLogs() })
      return
    }
    if (method === 'GET' && resource === 'messages') {
      writeJson(response, 200, { messages: sampleMessages() })
      return
    }
    if (method === 'GET' && resource === 'packets') {
      writeJson(response, 200, { packets: samplePackets(channel.ground_station_port) })
      return
    }
    if (method === 'PUT' && !resource) {
      let input: ChannelWrite
      try {
        input = JSON.parse(await readRequestBody(request)) as ChannelWrite
      } catch {
        writeJson(response, 400, { detail: 'Invalid channel request.' })
        return
      }
      if (hasListenerConflict(
        input,
        channels.filter((_, index) => index !== channelIndex),
      )) {
        writeJson(response, 409, { detail: 'A port conflict was found.' })
        return
      }
      const updated: ChannelPublic = {
        ...channel,
        ...input,
        monitor_udp_port: input.uav_udp_port + 10_000,
        config_file_name: `preview-${input.uav_udp_port}-${input.ground_station_port}.conf`,
        updated_at: new Date().toISOString(),
      }
      channels[channelIndex] = updated
      writeJson(response, 200, updated)
      return
    }
    if (method === 'POST' && resource === 'restart') {
      const restarted = {
        ...channel,
        runtime: { ...channel.runtime, state: 'active' as const, substate: 'running', active_since: new Date().toISOString() },
      }
      channels[channelIndex] = restarted
      writeJson(response, 200, restarted)
      return
    }
    if (method === 'DELETE' && !resource) {
      channels.splice(channelIndex, 1)
      writeNoContent(response)
      return
    }
  }

  writeJson(response, 501, {
    detail: 'This endpoint is not implemented in local preview mode. No backend request was sent.',
  })
}

export function previewApiPlugin(credentials: PreviewCredentials): Plugin {
  const previewChannelsState = [...previewDefaults]
  return {
    name: 'flightlink-local-preview-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const requestUrl = request.url ?? '/'
        if (!requestUrl.startsWith('/api/')) {
          next()
          return
        }

        const url = new URL(requestUrl, 'http://127.0.0.1')
        void handleRequest(request, response, url, credentials, previewChannelsState).catch((error: unknown) => {
          console.error('[FlightLink 本地预览] API 请求失败', error)
          if (!response.headersSent) {
            writeJson(response, 500, { detail: 'Local preview request failed.' })
          } else {
            response.end()
          }
        })
      })
    },
  }
}
