// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChannelPublic } from '@/api/types'
import ChannelDetailPage from '@/pages/ChannelDetailPage.vue'
import {
  getChannel,
  getChannelLogs,
  getFlightMessages,
  getPacketSummaries,
  updateChannel,
  restartChannel,
  deleteChannel,
} from '@/api/channels'
import { makeChannel, previewChannelId } from './fixtures/channel'

vi.mock('@/api/channels', () => ({
  getChannel: vi.fn(),
  getChannelLogs: vi.fn(),
  getFlightMessages: vi.fn(),
  getPacketSummaries: vi.fn(),
  updateChannel: vi.fn(),
  deleteChannel: vi.fn(),
  restartChannel: vi.fn(),
}))

async function mountDetail(channel: ChannelPublic, otherChannel?: ChannelPublic) {
  vi.mocked(getChannel).mockImplementation((id) =>
    Promise.resolve(id === otherChannel?.id ? otherChannel : channel),
  )
  vi.mocked(getChannelLogs).mockResolvedValue(['router started'])
  vi.mocked(getFlightMessages).mockResolvedValue([
    {
      received_at: '2026-09-30T12:00:00Z',
      severity: 4,
      severity_name: 'WARNING',
      text: 'Battery failsafe',
    },
  ])
  vi.mocked(getPacketSummaries).mockResolvedValue([
    {
      captured_at: '2026-09-30T12:00:00Z',
      protocol: 'MAVLink 2',
      source: '198.51.100.24:38211',
      destination: '127.0.0.1:14552',
      length_bytes: 42,
      summary: 'HEARTBEAT',
    },
  ])
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/channels/:id', name: 'channel-detail', component: ChannelDetailPage },
      { path: '/channels', name: 'channels', component: { template: '<div>端口组</div>' } },
    ],
  })
  await router.push(`/channels/${channel.id}`)
  await router.isReady()
  const wrapper = mount(ChannelDetailPage, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('port-group detail', () => {
  it('polls telemetry, messages and packets every second, and Router logs every two seconds', async () => {
    vi.useFakeTimers()
    const { wrapper } = await mountDetail(makeChannel())
    expect(getChannel).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(999)
    expect(getChannel).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(getChannel).toHaveBeenCalledTimes(2)
    expect(getFlightMessages).toHaveBeenCalledTimes(2)
    expect(getPacketSummaries).toHaveBeenCalledTimes(2)
    expect(getChannelLogs).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1_000)
    expect(getChannelLogs).toHaveBeenCalledTimes(2)
    expect(getChannelLogs).toHaveBeenLastCalledWith(previewChannelId, 500)
    wrapper.unmount()
  })
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps monitor, router, capture, and security-group states independent', async () => {
    const channel = makeChannel({
      enabled: false,
      security_group: { state: 'error', error: 'provider unavailable' },
      runtime: { state: 'failed', substate: 'failed', pid: null, active_since: null, result: 'exit-code', error: 'router stopped' },
      capture_runtime: { state: 'failed', substate: 'failed', pid: null, active_since: null, result: 'exit-code', error: 'capture stopped' },
      telemetry: {
        monitor_state: 'unavailable',
        monitor_error: 'UDP monitor failed',
        uav_online: false,
        link_quality_percent: null,
        last_packet_at: '2026-09-30T11:58:00Z',
        last_packet_age_seconds: 120,
      },
    })
    const { wrapper } = await mountDetail(channel)

    expect(wrapper.text()).toContain('监测服务不可用')
    expect(wrapper.text()).toContain('飞控最近断开')
    expect(wrapper.text()).toContain('链路质量未知')
    expect(wrapper.text()).toContain('Router 服务')
    expect(wrapper.text()).toContain('抓包服务')
    expect(wrapper.text()).toContain('安全组规则')
    expect(wrapper.text()).toContain('失败')

    wrapper.unmount()
  })

  it('distinguishes a never-seen UAV from a recently disconnected UAV', async () => {
    const channel = makeChannel({
      telemetry: {
        uav_online: false,
        last_packet_at: null,
        last_packet_age_seconds: null,
      },
    })
    const { wrapper } = await mountDetail(channel)

    expect(wrapper.text()).toContain('尚未收到飞控数据')
    expect(wrapper.text()).not.toContain('飞控最近断开')
    wrapper.unmount()
  })

  it('shows the current port pair, flight telemetry, per-group quality, and terminal output', async () => {
    const { wrapper } = await mountDetail(makeChannel())

    expect(wrapper.text()).toContain('UDP 5760')
    expect(wrapper.text()).toContain('TCP 14552')
    expect(wrapper.text()).toContain('SYSID 1')
    expect(wrapper.text()).toContain('AUTO')
    expect(wrapper.text()).toContain('82%')
    expect(wrapper.text()).toContain('21')
    expect(wrapper.text()).toContain('78.00 m')
    expect(wrapper.text()).toContain('11.20 m/s')
    expect(wrapper.text()).toContain('93.00%')
    expect(wrapper.text()).toContain('Battery failsafe')
    expect(wrapper.text()).toContain('HEARTBEAT')
    expect(wrapper.text()).toContain('router started')

    wrapper.unmount()
  })

  it('updates a port group and refreshes its detail', async () => {
    const current = makeChannel()
    const updated = makeChannel({ ground_station_port: 14560 })
    vi.mocked(updateChannel).mockResolvedValue(updated)
    const { wrapper } = await mountDetail(current)

    await wrapper.get('button.detail-action--primary').trigger('click')
    await wrapper.get('#ground-station-port').setValue('14560')
    await wrapper.get('.channel-form').trigger('submit')
    await flushPromises()

    expect(updateChannel).toHaveBeenCalledWith(previewChannelId, {
      uav_udp_port: 5760,
      ground_station_port: 14560,
      ground_station_protocol: 'tcp',
      enabled: true,
    })
    expect(wrapper.text()).toContain('端口组配置已保存')
    wrapper.unmount()
  })

  it('keeps entered ports when the backend returns the previous configuration after a failed update', async () => {
    const current = makeChannel()
    const rolledBack = makeChannel({
      security_group: { state: 'error', error: 'Unable to synchronize security-group rules.' },
    })
    vi.mocked(updateChannel).mockResolvedValue(rolledBack)
    const { wrapper } = await mountDetail(current)

    await wrapper.get('button.detail-action--primary').trigger('click')
    await wrapper.get('#ground-station-port').setValue('14560')
    await wrapper.get('.channel-form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect((wrapper.get('#ground-station-port').element as HTMLInputElement).value).toBe('14560')
    expect(wrapper.get('.channel-dialog [role="alert"]').text()).toContain('未应用')
    expect(wrapper.text()).not.toContain('端口组配置已保存')
    wrapper.unmount()
  })

  it('warns when a successful update response applies ports but reports a security-group error', async () => {
    const current = makeChannel()
    const applied = makeChannel({
      ground_station_port: 14560,
      security_group: { state: 'error', error: 'Unable to synchronize security-group rules.' },
    })
    vi.mocked(updateChannel).mockResolvedValue(applied)
    const { wrapper } = await mountDetail(current)
    vi.mocked(getChannel).mockResolvedValue(applied)

    await wrapper.get('button.detail-action--primary').trigger('click')
    await wrapper.get('#ground-station-port').setValue('14560')
    await wrapper.get('.channel-form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('配置已保存，但阿里云安全组同步或运行服务状态异常')
    wrapper.unmount()
  })

  it('does not let an older save close the edit dialog after switching port groups', async () => {
    const current = makeChannel()
    const next = makeChannel({
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
    })
    vi.mocked(updateChannel).mockResolvedValue(makeChannel({ ground_station_port: 14560 }))
    const { wrapper, router } = await mountDetail(current, next)
    let resolveRefreshLogs!: (logs: string[]) => void
    vi.mocked(getChannelLogs).mockImplementationOnce(
      () => new Promise((resolve) => { resolveRefreshLogs = resolve }),
    )

    await wrapper.get('button.detail-action--primary').trigger('click')
    await wrapper.get('#ground-station-port').setValue('14560')
    await wrapper.get('.channel-form').trigger('submit')
    await flushPromises()
    expect(resolveRefreshLogs).toBeDefined()

    await router.push(`/channels/${next.id}`)
    await flushPromises()
    expect(wrapper.text()).toContain('UDP 5761')
    await wrapper.get('button.detail-action--primary').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)

    resolveRefreshLogs(['old channel refresh'])
    await flushPromises()

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('端口组配置已保存')
    wrapper.unmount()
  })

  it('confirms and sends a Router restart request', async () => {
    vi.mocked(restartChannel).mockResolvedValue(makeChannel())
    const { wrapper } = await mountDetail(makeChannel())

    await wrapper.get('button.detail-action:not(.detail-action--primary):not(.detail-action--danger):not(.detail-action--icon)').trigger('click')
    await wrapper.get('[aria-labelledby="restart-title"] button.detail-action--primary').trigger('click')
    await flushPromises()

    expect(restartChannel).toHaveBeenCalledWith(previewChannelId)
    expect(wrapper.text()).toContain('Router 重启请求已完成')
    wrapper.unmount()
  })

  it('confirms deletion and returns to the port-group list', async () => {
    vi.mocked(deleteChannel).mockResolvedValue()
    const { wrapper, router } = await mountDetail(makeChannel())

    await wrapper.get('button.detail-action--danger').trigger('click')
    await wrapper.get('[aria-labelledby="delete-title"] button.detail-action--danger').trigger('click')
    await flushPromises()

    expect(deleteChannel).toHaveBeenCalledWith(previewChannelId)
    expect(router.currentRoute.value.name).toBe('channels')
    wrapper.unmount()
  })

  it('does not display an older group response after switching to another group', async () => {
    const first = makeChannel()
    const second = makeChannel({
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
    })
    let resolveFirst!: (value: ChannelPublic) => void
    let resolveSecond!: (value: ChannelPublic) => void
    vi.mocked(getChannel)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))
    vi.mocked(getChannelLogs).mockResolvedValue([])
    vi.mocked(getFlightMessages).mockResolvedValue([])
    vi.mocked(getPacketSummaries).mockResolvedValue([])

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/channels/:id', name: 'channel-detail', component: ChannelDetailPage },
        { path: '/channels', name: 'channels', component: { template: '<div>端口组</div>' } },
      ],
    })
    await router.push(`/channels/${first.id}`)
    await router.isReady()
    const wrapper = mount(ChannelDetailPage, { global: { plugins: [router] } })
    await flushPromises()

    await router.push(`/channels/${second.id}`)
    await flushPromises()
    resolveFirst(first)
    await flushPromises()

    expect(wrapper.text()).not.toContain('UDP 5760')
    expect(wrapper.text()).not.toContain('TCP 14552')

    resolveSecond(second)
    await flushPromises()
    expect(wrapper.text()).toContain('UDP 5761')
    expect(wrapper.text()).toContain('TCP 14553')
    wrapper.unmount()
  })

  it('does not apply a save response to the next port group', async () => {
    const first = makeChannel()
    const second = makeChannel({
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
    })
    let resolveUpdate!: (value: ChannelPublic) => void
    vi.mocked(updateChannel).mockImplementationOnce(
      () => new Promise((resolve) => { resolveUpdate = resolve }),
    )
    const { wrapper, router } = await mountDetail(first, second)

    await wrapper.get('button.detail-action--primary').trigger('click')
    await wrapper.get('#ground-station-port').setValue('14560')
    await wrapper.get('.channel-form').trigger('submit')
    await router.push(`/channels/${second.id}`)
    await flushPromises()
    resolveUpdate(makeChannel({ ground_station_port: 14560 }))
    await flushPromises()

    expect(wrapper.text()).toContain('UDP 5761')
    expect(wrapper.text()).not.toContain('TCP 14560')
    expect(wrapper.text()).not.toContain('端口组配置已保存')
    wrapper.unmount()
  })

  it('does not apply a restart response to the next port group', async () => {
    const first = makeChannel()
    const second = makeChannel({
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
    })
    let resolveRestart!: (value: ChannelPublic) => void
    vi.mocked(restartChannel).mockImplementationOnce(
      () => new Promise((resolve) => { resolveRestart = resolve }),
    )
    const { wrapper, router } = await mountDetail(first, second)

    await wrapper.get('button.detail-action:not(.detail-action--primary):not(.detail-action--danger):not(.detail-action--icon)').trigger('click')
    await wrapper.get('[aria-labelledby="restart-title"] button.detail-action--primary').trigger('click')
    await router.push(`/channels/${second.id}`)
    await flushPromises()
    resolveRestart(first)
    await flushPromises()

    expect(wrapper.text()).toContain('UDP 5761')
    expect(wrapper.text()).not.toContain('Router 重启请求已完成')
    wrapper.unmount()
  })

  it('does not leave the new detail page after a prior group is deleted', async () => {
    const first = makeChannel()
    const second = makeChannel({
      id: '00000000-0000-4000-8000-000000005761',
      uav_udp_port: 5761,
      ground_station_port: 14553,
    })
    let resolveDelete!: () => void
    vi.mocked(deleteChannel).mockImplementationOnce(
      () => new Promise((resolve) => { resolveDelete = resolve }),
    )
    const { wrapper, router } = await mountDetail(first, second)

    await wrapper.get('button.detail-action--danger').trigger('click')
    await wrapper.get('[aria-labelledby="delete-title"] button.detail-action--danger').trigger('click')
    await router.push(`/channels/${second.id}`)
    await flushPromises()
    resolveDelete()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('channel-detail')
    expect(router.currentRoute.value.params.id).toBe(second.id)
    expect(wrapper.text()).toContain('UDP 5761')
    wrapper.unmount()
  })
})
