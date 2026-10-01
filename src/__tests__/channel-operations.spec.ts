// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/http'
import type { ChannelPublic } from '@/api/types'
import { createChannel, listChannels } from '@/api/channels'
import ChannelsPage from '@/pages/ChannelsPage.vue'
import { makeChannel } from './fixtures/channel'

vi.mock('@/api/channels', () => ({
  listChannels: vi.fn(),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  deleteChannel: vi.fn(),
  restartChannel: vi.fn(),
  getChannel: vi.fn(),
  getChannelLogs: vi.fn(),
  getFlightMessages: vi.fn(),
  getPacketSummaries: vi.fn(),
}))

function mountChannels() {
  return mount(ChannelsPage, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

describe('port-group operations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listChannels).mockResolvedValue([])
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('creates a TCP port pair and refreshes the list', async () => {
    const created = makeChannel()
    vi.mocked(listChannels)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([created])
    vi.mocked(createChannel).mockResolvedValue(created)
    const wrapper = mountChannels()
    await flushPromises()
    await wrapper.get('button.create-channel').trigger('click')
    await wrapper.get('#uav-udp-port').setValue('5760')
    await wrapper.get('#ground-station-port').setValue('14552')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createChannel).toHaveBeenCalledWith({
      uav_udp_port: 5760,
      ground_station_port: 14552,
      ground_station_protocol: 'tcp',
      enabled: true,
    })
    expect(wrapper.text()).toContain('端口组已创建')
    expect(wrapper.text()).toContain('5760')
    wrapper.unmount()
  })

  it('reports an Aliyun security-group failure returned by a successful create', async () => {
    const created = makeChannel({
      security_group: { state: 'error', error: 'rule sync failed' },
    })
    vi.mocked(listChannels)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([created])
    vi.mocked(createChannel).mockResolvedValue(created)
    const wrapper = mountChannels()
    await flushPromises()
    await wrapper.get('button.create-channel').trigger('click')
    await wrapper.get('#uav-udp-port').setValue('5760')
    await wrapper.get('#ground-station-port').setValue('14552')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('安全组规则同步失败')
    expect(wrapper.text()).toContain('安全组')
    expect(wrapper.text()).toContain('异常')
    wrapper.unmount()
  })

  it('allows a TCP ground-station listener to reuse the UDP port number', async () => {
    const created = makeChannel({ ground_station_port: 5760 })
    vi.mocked(createChannel).mockResolvedValue(created)
    const wrapper = mountChannels()
    await flushPromises()
    await wrapper.get('button.create-channel').trigger('click')
    await wrapper.get('#uav-udp-port').setValue('5760')
    await wrapper.get('#ground-station-port').setValue('5760')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createChannel).toHaveBeenCalledWith({
      uav_udp_port: 5760,
      ground_station_port: 5760,
      ground_station_protocol: 'tcp',
      enabled: true,
    })
    wrapper.unmount()
  })

  it('rejects the same port number when both endpoints use UDP', async () => {
    const wrapper = mountChannels()
    await flushPromises()
    await wrapper.get('button.create-channel').trigger('click')
    await wrapper.get('#uav-udp-port').setValue('5760')
    await wrapper.get('#ground-station-protocol').setValue('udp')
    await wrapper.get('#ground-station-port').setValue('5760')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[role="alert"]').text()).toContain('同为 UDP 时')
    expect(createChannel).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it.each([
    [409, '端口冲突'],
    [503, '服务暂不可用'],
  ] as const)('keeps entered ports and shows a Chinese message for HTTP %s', async (status, message) => {
    vi.mocked(createChannel).mockRejectedValue(
      new ApiError(status, 'English backend detail', 'English backend detail'),
    )
    const wrapper = mountChannels()
    await flushPromises()
    await wrapper.get('button.create-channel').trigger('click')
    await wrapper.get('#uav-udp-port').setValue('5762')
    await wrapper.get('#ground-station-port').setValue('14554')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(message)
    expect((wrapper.get('#uav-udp-port').element as HTMLInputElement).value).toBe('5762')
    expect((wrapper.get('#ground-station-port').element as HTMLInputElement).value).toBe('14554')
    expect(wrapper.text()).not.toContain('English backend detail')
    wrapper.unmount()
  })

  it('disables the create action when the five-group limit is reached', async () => {
    const channels: ChannelPublic[] = Array.from({ length: 5 }, (_, index) =>
      makeChannel({
        id: `00000000-0000-4000-8000-00000000576${index}`,
        uav_udp_port: 5760 + index,
        ground_station_port: 14552 + index,
      }),
    )
    vi.mocked(listChannels).mockResolvedValue(channels)
    const wrapper = mountChannels()
    await flushPromises()

    expect(wrapper.get('button.create-channel').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('最多配置 5 组')
    wrapper.unmount()
  })
})
