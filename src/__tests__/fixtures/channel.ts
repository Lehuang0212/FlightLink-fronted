import type { ChannelPublic, ChannelTelemetryPublic } from '@/api/types'

export const previewChannelId = '00000000-0000-4000-8000-000000005760'

export function makeChannel(
  overrides: Partial<ChannelPublic> = {},
): ChannelPublic {
  const telemetry: ChannelTelemetryPublic = {
    monitor_state: 'listening',
    monitor_error: null,
    uav_online: true,
    uav_peer: '198.51.100.24:38211',
    system_id: 1,
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
    ground_station_connected: true,
    ground_station_peer: '192.0.2.45:59231',
    ground_station_last_packet_at: '2026-09-30T12:00:00Z',
    radio_status: null,
  }
  const runtime = {
    state: 'active' as const,
    substate: 'running',
    pid: 4812,
    active_since: '2026-09-28T01:00:00Z',
    result: null,
    error: null,
  }

  return {
    id: previewChannelId,
    uav_udp_port: 5760,
    ground_station_port: 14552,
    ground_station_protocol: 'tcp',
    enabled: true,
    monitor_udp_port: 15760,
    config_file_name: 'channel-5760-14552.conf',
    created_at: '2026-09-28T01:00:00Z',
    updated_at: '2026-09-30T12:00:00Z',
    security_group: { state: 'synced', error: null },
    runtime,
    capture_runtime: { ...runtime, pid: 4820 },
    ...overrides,
    telemetry: { ...telemetry, ...overrides.telemetry },
    runtime: { ...runtime, ...overrides.runtime },
    capture_runtime: { ...runtime, pid: 4820, ...overrides.capture_runtime },
    security_group: {
      state: 'synced',
      error: null,
      ...overrides.security_group,
    },
  }
}
