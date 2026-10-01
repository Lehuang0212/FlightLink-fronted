<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

type TerminalLineTone = 'critical' | 'warning' | 'info' | 'muted' | 'default'

const props = withDefaults(
  defineProps<{
    title: string
    lines: readonly string[]
    loading?: boolean
    error?: string | null
    autoScroll?: boolean
    lineTones?: readonly TerminalLineTone[]
  }>(),
  { loading: false, error: null, autoScroll: true, lineTones: () => [] },
)

const emit = defineEmits<{
  'update:autoScroll': [value: boolean]
}>()

const output = ref<HTMLDivElement | null>(null)

watch(
  () => `${props.lines.join('\n')}\u0000${props.lineTones?.join(',') ?? ''}`,
  async () => {
    if (!props.autoScroll) return
    await nextTick()
    if (output.value) output.value.scrollTop = output.value.scrollHeight
  },
)
</script>

<template>
  <section
    class="terminal-panel"
    :aria-label="title"
  >
    <header class="terminal-panel__header">
      <div class="terminal-panel__title">
        <span
          class="terminal-panel__light"
          aria-hidden="true"
        />
        <h3>{{ title }}</h3>
      </div>
      <label class="terminal-panel__scroll-toggle">
        <input
          type="checkbox"
          :checked="autoScroll"
          @change="emit('update:autoScroll', ($event.target as HTMLInputElement).checked)"
        >
        自动滚动
      </label>
    </header>

    <div
      ref="output"
      class="terminal-panel__output"
      aria-live="off"
    >
      <p
        v-if="error"
        class="terminal-panel__notice"
      >
        {{ error }}
      </p>
      <p
        v-if="loading && lines.length === 0"
        class="terminal-panel__empty"
      >
        正在读取数据…
      </p>
      <pre
        v-else-if="lines.length"
        class="terminal-panel__lines"
      ><span
        v-for="(line, index) in lines"
        :key="index"
        class="terminal-panel__line"
        :class="`terminal-panel__line--${lineTones?.[index] ?? 'default'}`"
      >{{ line }}</span></pre>
      <p
        v-else-if="!error"
        class="terminal-panel__empty"
      >
        暂无数据
      </p>
    </div>
  </section>
</template>

<style scoped>
.terminal-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #253747;
  border-radius: var(--radius-md);
  color: var(--color-terminal-ink);
  background: var(--color-terminal);
  box-shadow: 0 12px 28px rgb(12 25 37 / 12%);
}

.terminal-panel__header {
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.8rem;
  border-bottom: 1px solid #263948;
  background: #142331;
}

.terminal-panel__title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.55rem;
}

.terminal-panel__title h3 {
  overflow: hidden;
  margin: 0;
  color: #dce8f2;
  font-size: 0.75rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.terminal-panel__light {
  width: 0.48rem;
  height: 0.48rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #38b78c;
  box-shadow: 0 0 0 3px rgb(56 183 140 / 12%);
}

.terminal-panel__scroll-toggle {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.35rem;
  color: #9eb0c0;
  font-size: 0.65rem;
  cursor: pointer;
}

.terminal-panel__scroll-toggle input {
  accent-color: #43a9e0;
}

.terminal-panel__output {
  max-height: 17rem;
  min-height: 7.5rem;
  overflow: auto;
  padding: 0.75rem 0.85rem;
  scrollbar-color: #43586a #101923;
}

.terminal-panel__lines {
  margin: 0;
  color: #c6d6e3;
  font-family: var(--font-mono);
  font-size: 0.69rem;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.terminal-panel__line {
  display: block;
}

.terminal-panel__line--critical {
  color: #ff8585;
}

.terminal-panel__line--warning {
  color: #ffd27a;
}

.terminal-panel__line--info {
  color: #8ed7b5;
}

.terminal-panel__line--muted {
  color: #91a5b6;
}

.terminal-panel__empty,
.terminal-panel__notice {
  margin: 0;
  color: #91a5b6;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  line-height: 1.6;
}

.terminal-panel__notice {
  margin-bottom: 0.55rem;
  color: #ffc679;
}
</style>
