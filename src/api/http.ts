import { currentSessionEpoch } from '@/auth/session-epoch'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type SessionExpiredListener = () => void
const sessionExpiredListeners = new Set<SessionExpiredListener>()

export function onSessionExpired(listener: SessionExpiredListener): () => void {
  sessionExpiredListeners.add(listener)
  return () => sessionExpiredListeners.delete(listener)
}

function notifySessionExpired(): void {
  for (const listener of sessionExpiredListeners) listener()
}

function normalizedPath(path: string): string {
  const withLeadingSlash = path.startsWith('/') ? path : `/${path}`
  return withLeadingSlash.split('?')[0] ?? withLeadingSlash
}

function apiUrl(path: string): string {
  return `/api/v1${path.startsWith('/') ? path : `/${path}`}`
}

async function readError(response: Response): Promise<ApiError> {
  let detail: unknown

  try {
    const payload: unknown = await response.clone().json()
    if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
      detail = payload.detail
    } else {
      detail = payload
    }
  } catch {
    detail = await response.clone().text().catch(() => null)
  }

  const message =
    typeof detail === 'string'
      ? detail
      : `Request failed with status ${response.status}`
  return new ApiError(response.status, message, detail)
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const requestEpoch = currentSessionEpoch()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    const error = await readError(response)
    if (
      response.status === 401 &&
      normalizedPath(path) !== '/auth/login' &&
      requestEpoch === currentSessionEpoch()
    ) {
      notifySessionExpired()
    }
    throw error
  }

  return response
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await request(path, init)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function apiDownload(path: string): Promise<Blob> {
  const response = await request(path, {
    headers: { Accept: 'application/octet-stream' },
  })
  return response.blob()
}
