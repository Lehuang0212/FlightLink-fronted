import { apiDownload, apiRequest } from './http'
import type {
  CaptureFilePublic,
  ChannelPublic,
  ChannelWrite,
  FlightMessagePublic,
  PacketSummaryPublic,
} from './types'

interface LogsResponse {
  lines: string[]
}

interface FlightMessagesResponse {
  messages: FlightMessagePublic[]
}

interface PacketSummariesResponse {
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
): Promise<string[]> {
  const result = await apiRequest<LogsResponse>(
    `/channels/${encodeURIComponent(id)}/logs?limit=${limit}`,
  )
  return result.lines
}

export async function getFlightMessages(
  id: string,
  limit = 100,
): Promise<FlightMessagePublic[]> {
  const result = await apiRequest<FlightMessagesResponse>(
    `/channels/${encodeURIComponent(id)}/messages?limit=${limit}`,
  )
  return result.messages
}

export async function getPacketSummaries(
  id: string,
  limit = 100,
): Promise<PacketSummaryPublic[]> {
  const result = await apiRequest<PacketSummariesResponse>(
    `/channels/${encodeURIComponent(id)}/packets?limit=${limit}`,
  )
  return result.packets
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
