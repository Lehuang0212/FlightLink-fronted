// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TerminalPanel from '@/components/TerminalPanel.vue'

describe('terminal panel', () => {
  it('keeps unchanged event rows when the rolling window advances and does not scroll identical content', async () => {
    const wrapper = mount(TerminalPanel, { props: { title: '日志', lines: ['one', 'two', 'three'] } })
    const row = wrapper.findAll('.terminal-panel__line')[1]!.element
    await wrapper.setProps({ lines: ['two', 'three', 'four'] })
    await flushPromises()
    expect(wrapper.findAll('.terminal-panel__line')[0]!.element).toBe(row)
    const output = wrapper.get('.terminal-panel__output').element as HTMLDivElement
    output.scrollTop = 15
    await wrapper.setProps({ lines: ['two', 'three', 'four'] })
    await flushPromises()
    expect(output.scrollTop).toBe(15)
    wrapper.unmount()
  })
  it('auto-scrolls when a full 100-line window changes without changing length', async () => {
    const lines = Array.from({ length: 100 }, (_, index) => `line ${index + 1}`)
    const wrapper = mount(TerminalPanel, {
      props: { title: '运行日志', lines, autoScroll: true },
    })
    const output = wrapper.get('.terminal-panel__output').element as HTMLDivElement
    Object.defineProperty(output, 'scrollHeight', { configurable: true, value: 720 })

    await wrapper.setProps({ lines: [...lines.slice(1), 'latest line'] })
    await flushPromises()

    expect(output.scrollTop).toBe(720)
    wrapper.unmount()
  })
})
