// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RouterLogPanel from '@/components/RouterLogPanel.vue'

function stats(name: string, value: number) {
  return [`UDP Endpoint [4]${name} {`, '\tReceived messages {', '\t\tCRC error: 0 0% 0KB',
    '\t\tSequence lost: 0 0%', `\t\tHandled: ${value} 15KB`, `\t\tTotal: ${value}`,
    '\t}', '\tTransmitted messages {', '\t\tTotal: 389 7KB', '\t}', '}']
}

describe('Router statistics terminal', () => {
  it('keeps the first statistics block in view when initial logs arrive', async () => {
    const wrapper = mount(RouterLogPanel, { props: { lines: [] } })
    const output = wrapper.get('.terminal-panel__output').element as HTMLDivElement
    Object.defineProperty(output, 'scrollHeight', { configurable: true, value: 700 })
    await wrapper.setProps({ lines: ['Router started', ...stats('B100Cm', 20)] })
    await flushPromises()
    expect(output.scrollTop).toBe(0)
    wrapper.unmount()
  })
  it('keeps the latest complete block per endpoint and preserves unchanged DOM rows', async () => {
    const wrapper = mount(RouterLogPanel, { props: {
      lines: ['Router started', ...stats('B100Cm', 10), ...stats('B100Cm', 20), ...stats('monitor', 5)],
    } })
    expect(wrapper.text()).not.toContain('Handled: 10')
    expect(wrapper.text()).toContain('Handled: 20')
    expect(wrapper.text()).toContain('Router started')
    const endpoint = wrapper.findAll('[data-endpoint]')[0]!.element
    const unchangedRow = wrapper.findAll('[data-endpoint]')[0]!.findAll('.terminal-panel__line')[2]!.element
    const output = wrapper.get('.terminal-panel__output').element as HTMLDivElement
    output.scrollTop = 24
    await wrapper.setProps({ lines: ['Router started', ...stats('B100Cm', 21), ...stats('monitor', 5)] })
    await flushPromises()
    expect(wrapper.findAll('[data-endpoint]')[0]!.element).toBe(endpoint)
    expect(wrapper.findAll('[data-endpoint]')[0]!.findAll('.terminal-panel__line')[2]!.element).toBe(unchangedRow)
    expect(output.scrollTop).toBe(24)
    expect(wrapper.text()).toContain('Handled: 21')
    await wrapper.setProps({ lines: [...stats('B100Cm', 21), ...stats('B100Cm', 22).slice(0, 5)] })
    expect(wrapper.text()).toContain('Handled: 21')
    expect(wrapper.text()).not.toContain('Handled: 22')
    wrapper.unmount()
  })

  it('keeps duplicate events and handles braces inside ordinary event messages safely', () => {
    const wrapper = mount(RouterLogPanel, { props: { lines: ['retry {port}', 'retry {port}', ...stats('B100Cm', 0)] } })
    expect(wrapper.findAll('.router-log-events .terminal-panel__line')).toHaveLength(2)
    expect(wrapper.text()).toContain('Handled: 0')
    wrapper.unmount()
  })
})
