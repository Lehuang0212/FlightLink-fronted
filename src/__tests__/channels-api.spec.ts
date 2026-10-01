import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createChannel,
  downloadCapture,
  getChannelLogs,
  getFlightMessages,
  listCaptures,
} from '@/api/channels'

describe('channel API adapters', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the exact port-group write payload', async () => {
    const channel = { id: 'channel-1' }
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(channel), { status: 201 }),
    )

    await createChannel({
      uav_udp_port: 5760,
      ground_station_port: 14552,
      ground_station_protocol: 'tcp',
      enabled: true,
    })

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/channels',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          uav_udp_port: 5760,
          ground_station_port: 14552,
          ground_station_protocol: 'tcp',
          enabled: true,
        }),
      }),
    )
  })

  it('unwraps the lines field returned by the logs endpoint', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ channel_id: 'c1', lines: ['router started'] }), {
        status: 200,
      }),
    )

    await expect(getChannelLogs('c1')).resolves.toEqual(['router started'])
    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/channels/c1/logs?limit=100',
      expect.anything(),
    )
  })

  it('unwraps flight messages and capture files from the backend envelopes', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ channel_id: 'c1', messages: [{ text: 'Battery low' }] }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ channel_id: 'c1', captures: [{ file_name: 'closed.pcap' }] }),
          { status: 200 },
        ),
      )

    await expect(getFlightMessages('c1')).resolves.toEqual([{ text: 'Battery low' }])
    await expect(listCaptures('c1')).resolves.toEqual([{ file_name: 'closed.pcap' }])
  })

  it('encodes capture names in the authenticated download request', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(new Blob(['pcap']), { status: 200 }),
    )

    await downloadCapture('c1', 'flight segment #1.pcap')

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/channels/c1/captures/flight%20segment%20%231.pcap',
      expect.objectContaining({ credentials: 'include' }),
    )
  })
})
