// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FlightMessagePublic } from '@/api/types'
import FlightMessagesPage from '@/pages/FlightMessagesPage.vue'
import { getFlightMessages, listChannels } from '@/api/channels'
import { makeChannel } from './fixtures/channel'

vi.mock('@/api/channels', () => ({
  getFlightMessages: vi.fn(),
  listChannels: vi.fn(),
}))

const firstChannel = makeChannel()
const secondChannel = makeChannel({
  id: '00000000-0000-4000-8000-000000005761',
  uav_udp_port: 5761,
  ground_station_port: 14553,
})
const sampleMessages: FlightMessagePublic[] = [
  {
    received_at: '2026-09-30T12:00:00Z',
    severity: 4,
    severity_name: 'WARNING',
    text: 'Battery failsafe',
  },
  {
    received_at: '2026-09-30T12:00:01Z',
    severity: 6,
    severity_name: 'INFO',
    text: 'EKF3 IMU0 is using GPS',
  },
]

describe('flight messages page', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    vi.mocked(listChannels).mockResolvedValue([firstChannel, secondChannel])
    vi.mocked(getFlightMessages).mockResolvedValue(sampleMessages)
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('filters messages by severity and switches the selected port group', async () => {
    const wrapper = mount(FlightMessagesPage)
    await flushPromises()

    expect(getFlightMessages).toHaveBeenCalledWith(firstChannel.id, 100)
    expect(wrapper.text()).toContain('Battery failsafe')
    expect(wrapper.text()).toContain('EKF3 IMU0 is using GPS')

    await wrapper.get('select[aria-label="消息级别"]').setValue('WARNING')
    expect(wrapper.text()).toContain('Battery failsafe')
    expect(wrapper.text()).toContain('警告')
    expect(wrapper.text()).not.toContain('EKF3 IMU0 is using GPS')

    await wrapper.get('select[aria-label="端口组"]').setValue(secondChannel.id)
    await flushPromises()
    expect(getFlightMessages).toHaveBeenLastCalledWith(secondChannel.id, 100)
    wrapper.unmount()
  })

  it('colors terminal lines by MAVLink message severity', async () => {
    const wrapper = mount(FlightMessagesPage)
    await flushPromises()

    expect(wrapper.get('.terminal-panel__line--warning').text()).toContain('Battery failsafe')
    expect(wrapper.get('.terminal-panel__line--info').text()).toContain('EKF3 IMU0 is using GPS')
    wrapper.unmount()
  })

  it('polls every two seconds and supports manual refresh', async () => {
    const wrapper = mount(FlightMessagesPage)
    await flushPromises()
    expect(getFlightMessages).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1_999)
    expect(getFlightMessages).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(getFlightMessages).toHaveBeenCalledTimes(2)

    await wrapper.get('button[aria-label="刷新飞控消息"]').trigger('click')
    await flushPromises()
    expect(getFlightMessages).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('shows an empty state without requesting messages when there are no port groups', async () => {
    vi.mocked(listChannels).mockResolvedValue([])
    const wrapper = mount(FlightMessagesPage)
    await flushPromises()

    expect(wrapper.text()).toContain('尚未配置端口组')
    expect(getFlightMessages).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
