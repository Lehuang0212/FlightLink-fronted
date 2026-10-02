// @vitest-environment jsdom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import LinkQuality from '@/components/LinkQuality.vue'

describe('integer link quality display', () => {
  it.each([[98.7654321, '99%'], [78.1234567, '78%'], [0, '0%'], [100.1, '100%'], [-1, '0%']])(
    'formats %s as %s consistently for text and accessibility', (value, expected) => {
      const wrapper = mount(LinkQuality, { props: { value } })
      expect(wrapper.get('.link-quality__value').text()).toBe(expected)
      expect(wrapper.get('[role="img"]').attributes('aria-label')).toBe(`MAVLink 链路质量：${expected}`)
      wrapper.unmount()
    },
  )
  it('keeps unavailable quality unknown', () => {
    const wrapper = mount(LinkQuality, { props: { value: null } })
    expect(wrapper.get('.link-quality__value').text()).toBe('未知')
    wrapper.unmount()
  })
})
