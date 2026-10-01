export interface AdminPublic {
  id: number
  username: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface HealthPublic {
  status: string
  database: string
}

export type GroundStationProtocol = 'tcp' | 'udp'

export type RuntimeState =
  | 'active'
  | 'inactive'
  | 'failed'
  | 'starting'
  | 'stopping'
  | 'unknown'

export interface RouterRuntimePublic {
  state: RuntimeState
  substate: string | null
  pid: number | null
  active_since: string | null
  result: string | null
  error: string | null
}

export interface SecurityGroupChannelPublic {
  state: 'disabled' | 'pending' | 'synced' | 'cleanup_pending' | 'error'
  error: string | null
}

export interface RadioStatusPublic {
  rssi: number | null
  remote_rssi: number | null
  noise: number | null
  remote_noise: number | null
  tx_buffer_percent: number | null
  receive_errors: number | null
}

export interface ChannelTelemetryPublic {
  monitor_state: 'listening' | 'unavailable'
  monitor_error: string | null
  uav_online: boolean
  uav_peer: string | null
  system_id: number | null
  component_id: number | null
  vehicle_type: string | null
  autopilot: string | null
  flight_mode: string | null
  armed: boolean | null
  battery_remaining_percent: number | null
  battery_voltage_v: number | null
  gps_fix_type: number | null
  gps_satellites: number | null
  altitude_m: number | null
  relative_altitude_m: number | null
  ground_speed_m_s: number | null
  link_quality_percent: number | null
  packets_received_window: number
  packets_lost_window: number
  last_packet_at: string | null
  last_packet_age_seconds: number | null
  uav_rx_bytes_per_second: number
  gcs_tx_bytes_per_second: number
  ground_station_connected: boolean
  ground_station_peer: string | null
  ground_station_last_packet_at: string | null
  radio_status: RadioStatusPublic | null
}

export interface ChannelWrite {
  uav_udp_port: number
  ground_station_port: number
  ground_station_protocol: GroundStationProtocol
  enabled: boolean
}

export interface ChannelPublic extends ChannelWrite {
  id: string
  monitor_udp_port: number
  config_file_name: string
  created_at: string
  updated_at: string
  security_group: SecurityGroupChannelPublic
  runtime: RouterRuntimePublic
  capture_runtime: RouterRuntimePublic
  telemetry: ChannelTelemetryPublic
}

export interface FlightMessagePublic {
  received_at: string
  severity: number | null
  severity_name: string
  text: string
}

export interface PacketSummaryPublic {
  captured_at: string
  protocol: string | null
  source: string | null
  destination: string | null
  length_bytes: number | null
  summary: string
}

export interface CaptureFilePublic {
  file_name: string
  started_at: string | null
  size_bytes: number
  is_current: boolean
}
