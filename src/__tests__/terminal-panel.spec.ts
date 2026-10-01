// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TerminalPanel from '@/components/TerminalPanel.vue'

describe('terminal panel', () => {
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
