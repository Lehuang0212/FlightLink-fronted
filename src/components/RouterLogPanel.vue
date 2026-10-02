<script setup lang="ts">
import { computed } from 'vue'
import TerminalPanel from './TerminalPanel.vue'
import { splitRouterLogs, statisticsTone } from './routerLogs'

const props = withDefaults(defineProps<{
  lines: readonly string[]
  loading?: boolean
  error?: string | null
  autoScroll?: boolean
}>(), { loading: false, error: null, autoScroll: true })
const emit = defineEmits<{ 'update:autoScroll': [value: boolean] }>()
const display = computed(() => splitRouterLogs(props.lines))
const eventRows = computed(() => {
  const occurrences = new Map<string, number>()
  return display.value.events.map((text) => {
    const occurrence = occurrences.get(text) ?? 0
    occurrences.set(text, occurrence + 1)
    return { text, key: `${text}:${occurrence}` }
  })
})
</script>

<template>
  <TerminalPanel
    title="mavlink-router 运行日志"
    :lines="display.events"
    :loading="loading"
    :error="error"
    :auto-scroll="autoScroll"
    :scroll-on-first-load="false"
    @update:auto-scroll="emit('update:autoScroll', $event)"
  >
    <pre
      v-for="endpoint in display.endpoints"
      :key="endpoint.id"
      :data-endpoint="endpoint.id"
      class="terminal-panel__lines router-log-statistics"
    ><span
      v-for="(line, index) in endpoint.lines"
      :key="index"
      class="terminal-panel__line"
      :class="`terminal-panel__line--${statisticsTone(line)}`"
    >{{ line }}</span></pre>
    <div
      v-if="display.events.length"
      class="router-log-events"
    >
      <p
        v-if="display.endpoints.length"
        class="router-log-label"
      >
        运行事件
      </p>
      <pre class="terminal-panel__lines"><span
        v-for="row in eventRows"
        :key="row.key"
        class="terminal-panel__line"
      >{{ row.text }}</span></pre>
    </div>
    <p
      v-if="!display.endpoints.length && !display.events.length && !error"
      class="terminal-panel__empty"
    >
      {{ loading ? '正在读取数据…' : '暂无日志，等待 Router 输出' }}
    </p>
  </TerminalPanel>
</template>

<style scoped>
.router-log-statistics + .router-log-statistics { margin-top: 0.8rem; }
.router-log-label {
  margin: 0.8rem 0 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid #263948;
  color: #91a5b6;
  font-size: 0.7rem;
}
</style>
