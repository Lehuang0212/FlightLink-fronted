// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/http'
import type { CaptureFilePublic, PacketSummaryPublic } from '@/api/types'
import CapturesPage from '@/pages/CapturesPage.vue'
import { downloadCapture, getPacketSummaries, listCaptures, listChannels } from '@/api/channels'
import { makeChannel } from './fixtures/channel'

vi.mock('@/api/channels', () => ({
  downloadCapture: vi.fn(),
  getPacketSummaries: vi.fn(),
  listCaptures: vi.fn(),
  listChannels: vi.fn(),
}))

const channel = makeChannel()
const currentFile: CaptureFilePublic = {
  file_name: 'channel-00000000-0000-4000-8000-000000005760-a1b2c3d4-20260930-120000-1790769600.pcap',
  started_at: '2026-09-30T12:00:00Z',
  size_bytes: 4096,
  is_current: true,
}
const closedFile: CaptureFilePublic = {
  file_name: 'channel-00000000-0000-4000-8000-000000005760-a1b2c3d4-20260930-110000-1790766000.pcap',
  started_at: '2026-09-30T11:00:00Z',
  size_bytes: 1_572_864,
  is_current: false,
}
const packets: PacketSummaryPublic[] = [
  {
    captured_at: '2026-09-30T12:00:00Z',
    protocol: 'MAVLink 2',
    source: '198.51.100.24:38211',
    destination: '127.0.0.1:5760',
    length_bytes: 42,
    summary: 'HEARTBEAT sysid=1 compid=1',
  },
]

describe('capture page', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    vi.mocked(listChannels).mockResolvedValue([channel])
    vi.mocked(getPacketSummaries).mockResolvedValue(packets)
    vi.mocked(listCaptures).mockResolvedValue([currentFile, closedFile])
    vi.mocked(downloadCapture).mockResolvedValue(new Blob(['pcap-data']))
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:flightlink-capture'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('shows current and closed capture segments and disables current-file download', async () => {
    const wrapper = mount(CapturesPage)
    await flushPromises()

    expect(wrapper.text()).toContain('HEARTBEAT sysid=1 compid=1')
    expect(wrapper.text()).toContain('每 10 分钟轮转')
    expect(wrapper.text()).toContain('写入中')
    expect(wrapper.text()).toContain('1.50 MiB')
    const currentDownload = wrapper.get(`button[aria-label="下载 ${currentFile.file_name}"]`)
    expect(currentDownload.attributes('disabled')).toBeDefined()
    await currentDownload.trigger('click')
    expect(downloadCapture).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps the last successful capture list visible when a refresh fails', async () => {
    vi.mocked(listCaptures)
      .mockResolvedValueOnce([currentFile, closedFile])
      .mockRejectedValueOnce(new Error('Capture service unavailable'))
    const wrapper = mount(CapturesPage)
    await flushPromises()

    expect(wrapper.get('.capture-file-list').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(15_000)
    await flushPromises()

    expect(wrapper.text()).toContain('PCAP 文件更新失败')
    expect(wrapper.get('.capture-file-list').exists()).toBe(true)
    expect(wrapper.findAll('.capture-file')).toHaveLength(2)
    wrapper.unmount()
  })

  it('downloads only a closed PCAP file through the authenticated API and saves it', async () => {
    const clickedNames: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clickedNames.push(this.download)
    })
    const wrapper = mount(CapturesPage)
    await flushPromises()

    await wrapper.get(`button[aria-label="下载 ${closedFile.file_name}"]`).trigger('click')
    await flushPromises()

    expect(downloadCapture).toHaveBeenCalledWith(channel.id, closedFile.file_name)
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    expect(clickedNames).toEqual([closedFile.file_name])
    expect(wrapper.text()).toContain('PCAP 文件下载已开始')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:flightlink-capture')
    wrapper.unmount()
  })

  it('shows specific messages when a capture is still writing or no longer exists', async () => {
    const wrapper = mount(CapturesPage)
    await flushPromises()

    vi.mocked(downloadCapture).mockRejectedValueOnce(
      new ApiError(409, 'The newest capture segment is still being written', 'The newest capture segment is still being written'),
    )
    await wrapper.get(`button[aria-label="下载 ${closedFile.file_name}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('抓包片段仍在写入，暂时无法下载。')

    vi.mocked(downloadCapture).mockRejectedValueOnce(
      new ApiError(404, 'Capture file not found', 'Capture file not found'),
    )
    await wrapper.get(`button[aria-label="下载 ${closedFile.file_name}"]`).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('抓包文件已不可用或已清理。')
    wrapper.unmount()
  })

  it('polls packet summaries every second and files every fifteen seconds', async () => {
    const wrapper = mount(CapturesPage)
    await flushPromises()
    expect(getPacketSummaries).toHaveBeenCalledTimes(1)
    expect(listCaptures).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(1_000)
    await flushPromises()
    expect(getPacketSummaries).toHaveBeenCalledTimes(2)
    expect(listCaptures).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(14_000)
    await flushPromises()
    expect(getPacketSummaries).toHaveBeenCalledTimes(16)
    expect(listCaptures).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
