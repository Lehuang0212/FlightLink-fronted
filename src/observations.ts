import type { ChannelPublic } from '@/api/types'

export function uavState({ telemetry: t }: ChannelPublic) {
  if (t.monitor_state !== 'listening') return 'unknown'
  return t.uav_online ? 'online' : t.last_packet_at ? 'expired' : 'waiting'
}

export function groundState({ telemetry: t, ground_station_protocol: protocol }: ChannelPublic) {
  if (t.monitor_state !== 'listening' || t.ground_station_observable === false) return 'unknown'
  if (protocol === 'tcp') return t.ground_station_connected ? 'tcpSession' : 'noSession'
  return t.ground_station_connected ? 'udpActivity' : t.ground_station_last_packet_at ? 'quiet' : 'waiting'
}
