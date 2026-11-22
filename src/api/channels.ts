import { apiDownload, apiRequest } from './http'
import type {
  CaptureFilePublic,
  ChannelPublic,
  ChannelWrite,
  FlightMessagePublic,
  PacketSummaryPublic,
} from './types'

export interface HistoryWindow<T> { id?: string; cursor?: string | null; items?: T[] }
interface CursorPage { cursor?: string | null; reset?: boolean }
function after<T>(window: HistoryWindow<T> | undefined, id: string) {
  return window?.id === id && window.cursor ? `&after=${encodeURIComponent(window.cursor)}` : ''
}
function merge<T>(window: HistoryWindow<T> | undefined, page: CursorPage, id: string, items: T[], limit: number) {
  if (!window) return items
  const result = window.id === id && page.reset === false ? [...(window.items ?? []), ...items].slice(-limit) : items
  Object.assign(window, { id, cursor: page.cursor, items: result })
  return result
}

interface LogsResponse extends CursorPage {
  lines: string[]
}

interface FlightMessagesResponse extends CursorPage {
  messages: FlightMessagePublic[]
}

interface PacketSummariesResponse extends CursorPage {
  packets: PacketSummaryPublic[]
}

interface CaptureFilesResponse {
  captures: CaptureFilePublic[]
}

export function listChannels(): Promise<ChannelPublic[]> {
  return apiRequest<ChannelPublic[]>('/channels')
}

export function getChannel(id: string): Promise<ChannelPublic> {
  return apiRequest<ChannelPublic>(`/channels/${encodeURIComponent(id)}`)
}

export function createChannel(input: ChannelWrite): Promise<ChannelPublic> {
  return apiRequest<ChannelPublic>('/channels', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateChannel(
  id: string,
  input: ChannelWrite,
): Promise<ChannelPublic> {
  return apiRequest<ChannelPublic>(`/channels/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function deleteChannel(id: string): Promise<void> {
  return apiRequest<void>(`/channels/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function restartChannel(id: string): Promise<ChannelPublic> {
  return apiRequest<ChannelPublic>(
    `/channels/${encodeURIComponent(id)}/restart`,
    { method: 'POST' },
  )
}

export async function getChannelLogs(
  id: string,
  limit = 100,
  window?: HistoryWindow<string>,
): Promise<string[]> {
  const result = await apiRequest<LogsResponse>(
    `/channels/${encodeURIComponent(id)}/logs?limit=${limit}${after(window, id)}`,
  )
  return merge(window, result, id, result.lines, limit)
}

export async function getFlightMessages(
  id: string,
  limit = 100,
  window?: HistoryWindow<FlightMessagePublic>,
): Promise<FlightMessagePublic[]> {
  const result = await apiRequest<FlightMessagesResponse>(
    `/channels/${encodeURIComponent(id)}/messages?limit=${limit}${after(window, id)}`,
  )
  return merge(window, result, id, result.messages, limit)
}

export async function getPacketSummaries(
  id: string,
  limit = 100,
  window?: HistoryWindow<PacketSummaryPublic>,
): Promise<PacketSummaryPublic[]> {
  const result = await apiRequest<PacketSummariesResponse>(
    `/channels/${encodeURIComponent(id)}/packets?limit=${limit}${after(window, id)}`,
  )
  return merge(window, result, id, result.packets, limit)
}

export async function listCaptures(id: string): Promise<CaptureFilePublic[]> {
  const result = await apiRequest<CaptureFilesResponse>(
    `/channels/${encodeURIComponent(id)}/captures`,
  )
  return result.captures
}

export function downloadCapture(id: string, fileName: string): Promise<Blob> {
  return apiDownload(
    `/channels/${encodeURIComponent(id)}/captures/${encodeURIComponent(fileName)}`,
  )
}
