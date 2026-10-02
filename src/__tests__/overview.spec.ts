// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChannelPublic } from '@/api/types'
import OverviewPage from '@/pages/OverviewPage.vue'
import ChannelsPage from '@/pages/ChannelsPage.vue'
import { listChannels } from '@/api/channels'

vi.mock('@/api/channels', () => ({
  listChannels: vi.fn(),
}))

function channel(overrides: Partial<ChannelPublic> = {}): ChannelPublic {
  return {
    id: '00000000-0000-4000-8000-000000000001',
    uav_udp_port: 5760,
    ground_station_port: 14552,
    ground_station_protocol: 'tcp',
    enabled: true,
    monitor_udp_port: 15760,
    config_file_name: 'channel-5760-14552.conf',
    created_at: '2026-09-30T00:00:00Z',
    updated_at: '2026-09-30T00:00:00Z',
    security_group: { state: 'synced', error: null },
    runtime: {
      state: 'active', substate: 'running', pid: 100, active_since: null,
      result: null, error: null,
    },
    capture_runtime: {
      state: 'active', substate: 'running', pid: 101, active_since: null,
      result: null, error: null,
    },
    telemetry: {
      monitor_state: 'listening', monitor_error: null, uav_online: true,
      uav_peer: '203.0.113.8:38211', system_id: 1, component_id: 1,
      vehicle_type: 'QUADROTOR', autopilot: 'ArduPilot', flight_mode: 'AUTO',
      armed: true, battery_remaining_percent: 82, battery_voltage_v: 15.8,
      gps_fix_type: 3, gps_satellites: 21, altitude_m: 78,
      relative_altitude_m: 32, ground_speed_m_s: 11.2,
      link_quality_percent: 93, packets_received_window: 980,
      packets_lost_window: 2, last_packet_at: '2026-09-30T00:00:00Z',
      last_packet_age_seconds: 0.12, uav_rx_bytes_per_second: 4_800,
      gcs_tx_bytes_per_second: 1_200, ground_station_connected: true,
      ground_station_peer: '192.0.2.15:59231',
      ground_station_last_packet_at: '2026-09-30T00:00:00Z', radio_status: null,
    },
    ...overrides,
  }
}

describe('overview and port-group cards', () => {
  beforeEach(() => {
    vi.mocked(listChannels).mockResolvedValue([channel()])
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('summarizes online aircraft and ground stations without an aggregate link score', async () => {
    vi.mocked(listChannels).mockResolvedValue([
      channel(),
      channel({
        id: '00000000-0000-4000-8000-000000000002',
        uav_udp_port: 5761,
        ground_station_port: 14553,
        telemetry: {
          ...channel().telemetry,
          uav_online: false,
          ground_station_connected: false,
          system_id: null,
          link_quality_percent: null,
        },
      }),
    ])
    const wrapper = mount(OverviewPage, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('1 / 2')
    expect(wrapper.text()).toContain('5760')
    expect(wrapper.text()).toContain('14552')
    expect(wrapper.text()).toContain('93.00%')
    expect(wrapper.text()).not.toContain('Fleet MAVLink quality')
    expect(wrapper.text()).toContain('本次访问尚未观察到状态变化')

    wrapper.unmount()
  })

  it('shows an empty state when no port groups exist', async () => {
    vi.mocked(listChannels).mockResolvedValue([])
    const wrapper = mount(OverviewPage, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('尚未配置端口组')
    expect(wrapper.text()).toContain('0')
    wrapper.unmount()
  })

  it('records a connection change only after observing it during this session', async () => {
    vi.useFakeTimers()
    vi.mocked(listChannels)
      .mockResolvedValueOnce([channel()])
      .mockResolvedValueOnce([
        channel({
          telemetry: { ...channel().telemetry, uav_online: false },
        }),
      ])
    const wrapper = mount(OverviewPage, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('本次访问尚未观察到状态变化')

    await vi.advanceTimersByTimeAsync(1_000)
    await flushPromises()
    expect(wrapper.text()).toContain('飞控已断开 · 5760 / 14552')
    expect(wrapper.text()).not.toContain('本次访问尚未观察到状态变化')

    wrapper.unmount()
  })

  it('renders a per-channel quality indicator and unknown values as dashes', async () => {
    vi.mocked(listChannels).mockResolvedValue([
      channel({
        telemetry: {
          ...channel().telemetry,
          uav_online: false,
          ground_station_connected: false,
          system_id: null,
          flight_mode: null,
          battery_remaining_percent: null,
          gps_satellites: null,
          altitude_m: null,
          ground_speed_m_s: null,
          link_quality_percent: null,
        },
      }),
    ])
    const wrapper = mount(ChannelsPage, {
      global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('MAVLink 链路质量')
    expect(wrapper.text()).toContain('—')
    expect(wrapper.text()).toContain('5760')
    expect(wrapper.text()).toContain('14552')
    wrapper.unmount()
  })
})
