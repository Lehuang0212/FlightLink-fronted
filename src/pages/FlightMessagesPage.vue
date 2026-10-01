<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getFlightMessages, listChannels } from '@/api/channels'
import { toChineseError } from '@/api/error-message'
import TerminalPanel from '@/components/TerminalPanel.vue'
import { usePolling } from '@/composables/usePolling'

const channelPolling = usePolling(listChannels, 15_000)
const channels = computed(() => channelPolling.data.value ?? [])
const selectedChannelId = ref('')
const hasChannels = computed(() => channels.value.length > 0)
const messagesEnabled = computed(() => selectedChannelId.value.length > 0)
const messagesPolling = usePolling(
  () => getFlightMessages(selectedChannelId.value, 100),
  2_000,
  messagesEnabled,
  selectedChannelId,
)
const severityFilter = ref('')
const autoScroll = ref(true)
const severityLabels: Record<string, string> = {
  EMERGENCY: '紧急',
  ALERT: '警报',
  CRITICAL: '严重',
  ERROR: '错误',
  WARNING: '警告',
  NOTICE: '通知',
  INFO: '信息',
  DEBUG: '调试',
  UNKNOWN: '未知级别',
}

watch(
  channels,
  (items) => {
    if (!items.length) {
      selectedChannelId.value = ''
      return
    }
    if (!items.some((channel) => channel.id === selectedChannelId.value)) {
      selectedChannelId.value = items[0]?.id ?? ''
    }
  },
  { immediate: true },
)

const messages = computed(() => messagesPolling.data.value ?? [])
const filteredMessages = computed(() =>
  severityFilter.value
    ? messages.value.filter((message) => message.severity_name.toUpperCase() === severityFilter.value)
    : messages.value,
)
const messageLines = computed(() =>
  filteredMessages.value.map((message) => {
    const date = new Date(message.received_at)
    const time = Number.isNaN(date.getTime())
      ? '未知时间'
      : date.toLocaleTimeString('zh-CN', { hour12: false })
    const severity = severityLabels[message.severity_name.toUpperCase()] ?? '未知级别'
    return `[${time}] [${severity}] ${message.text}`
  }),
)
const messageTones = computed(() =>
  filteredMessages.value.map((message) => {
    const severity = message.severity_name.toUpperCase()
    if (['EMERGENCY', 'ALERT', 'CRITICAL', 'ERROR'].includes(severity)) return 'critical' as const
    if (severity === 'WARNING') return 'warning' as const
    if (['NOTICE', 'INFO'].includes(severity)) return 'info' as const
    return 'muted' as const
  }),
)
const channelError = computed(() =>
  channelPolling.error.value
    ? toChineseError(channelPolling.error.value, '无法读取端口组，请检查后端服务后重试。')
    : null,
)
const messageError = computed(() =>
  messagesPolling.error.value
    ? toChineseError(messagesPolling.error.value, '暂时无法读取飞控消息，请稍后重试。')
    : null,
)

async function refresh(): Promise<void> {
  await Promise.all([
    channelPolling.refresh(),
    ...(selectedChannelId.value ? [messagesPolling.refresh()] : []),
  ])
}
</script>

<template>
  <section class="messages-page page-stack">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">
          飞控状态
        </p>
        <h1>飞控消息</h1>
        <p class="page-heading__description">
          查看飞控通过 MAVLink 发送的 STATUSTEXT 消息，并按级别筛选。
        </p>
      </div>
      <button
        class="quiet-button"
        type="button"
        aria-label="刷新飞控消息"
        :disabled="messagesPolling.loading.value || channelPolling.loading.value"
        @click="refresh"
      >
        <span aria-hidden="true">↻</span>
        {{ messagesPolling.loading.value ? '正在更新…' : '刷新' }}
      </button>
    </header>

    <p
      v-if="channelError"
      class="page-alert"
      role="alert"
    >
      {{ channelError }}
      <button
        type="button"
        @click="refresh"
      >
        重试
      </button>
    </p>

    <template v-if="hasChannels">
      <section
        class="messages-toolbar"
        aria-label="消息筛选"
      >
        <label class="messages-field">
          <span>端口组</span>
          <select
            v-model="selectedChannelId"
            aria-label="端口组"
          >
            <option
              v-for="channel in channels"
              :key="channel.id"
              :value="channel.id"
            >
              UDP {{ channel.uav_udp_port }} / {{ channel.ground_station_protocol.toUpperCase() }} {{ channel.ground_station_port }}
            </option>
          </select>
        </label>
        <label class="messages-field">
          <span>消息级别</span>
          <select
            v-model="severityFilter"
            aria-label="消息级别"
          >
            <option value="">全部级别</option>
            <option value="EMERGENCY">紧急</option>
            <option value="ALERT">警报</option>
            <option value="CRITICAL">严重</option>
            <option value="ERROR">错误</option>
            <option value="WARNING">警告</option>
            <option value="NOTICE">通知</option>
            <option value="INFO">信息</option>
            <option value="DEBUG">调试</option>
            <option value="UNKNOWN">未知级别</option>
          </select>
        </label>
        <p class="messages-count">
          显示 {{ filteredMessages.length }} / {{ messages.length }} 条 · 每 2 秒更新
        </p>
      </section>

      <TerminalPanel
        title="飞控消息 · STATUSTEXT"
        :lines="messageLines"
        :line-tones="messageTones"
        :loading="messagesPolling.loading.value"
        :error="messageError"
        :auto-scroll="autoScroll"
        @update:auto-scroll="autoScroll = $event"
      />
    </template>

    <div
      v-else-if="!channelError && (channelPolling.loading.value || channelPolling.data.value === undefined)"
      class="messages-empty"
      role="status"
    >
      正在读取端口组…
    </div>
    <div
      v-else-if="!channelError"
      class="messages-empty"
      role="status"
    >
      <strong>尚未配置端口组</strong>
      <span>创建端口组并收到飞控消息后，内容会显示在这里。</span>
    </div>
  </section>
</template>

<style scoped>
.messages-page {
  display: grid;
  width: 100%;
  gap: 1.1rem;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}

.page-heading__eyebrow {
  margin: 0 0 0.42rem;
  color: var(--color-primary);
  font-size: 0.65rem;
  font-weight: 750;
  letter-spacing: 0.13em;
}

.page-heading h1 {
  margin: 0;
  color: #1d3044;
  font-size: clamp(1.7rem, 3vw, 2.15rem);
  letter-spacing: -0.055em;
}

.page-heading__description {
  margin: 0.45rem 0 0;
  color: var(--color-muted);
  font-size: 0.85rem;
  line-height: 1.5;
}

.quiet-button {
  display: inline-flex;
  min-height: 2.45rem;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #dbe4ec;
  border-radius: var(--radius-sm);
  color: #4b6075;
  background: #fff;
  cursor: pointer;
  font-size: 0.76rem;
  font-weight: 650;
}

.quiet-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.messages-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 0.85rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.messages-field {
  display: grid;
  min-width: min(100%, 14rem);
  gap: 0.35rem;
  color: #566a7e;
  font-size: 0.69rem;
  font-weight: 650;
}

.messages-field select {
  min-height: 2.4rem;
  padding: 0.4rem 2rem 0.4rem 0.65rem;
  border: 1px solid #d8e1e9;
  border-radius: 0.5rem;
  color: #32485d;
  background: #fff;
  font-size: 0.75rem;
}

.messages-count {
  margin: 0 0 0.55rem auto;
  color: #8090a0;
  font-size: 0.7rem;
}

.messages-empty {
  display: grid;
  min-height: 10rem;
  align-content: center;
  justify-items: center;
  gap: 0.55rem;
  padding: 1.5rem;
  border: 1px dashed #dce5ec;
  border-radius: var(--radius-md);
  color: #748396;
  background: #fbfcfd;
  font-size: 0.8rem;
  text-align: center;
}

.messages-empty strong {
  color: #506277;
  font-size: 0.85rem;
}

.messages-empty span {
  line-height: 1.5;
}

.page-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin: 0;
  padding: 0.7rem 0.9rem;
  border: 1px solid #efd7ae;
  border-radius: var(--radius-sm);
  color: #805915;
  background: #fff9ec;
  font-size: 0.76rem;
}

.page-alert button {
  padding: 0.25rem 0.45rem;
  border: 0;
  color: inherit;
  background: transparent;
  cursor: pointer;
  font-weight: 700;
}

@media (max-width: 620px) {
  .page-heading {
    align-items: flex-start;
  }

  .messages-toolbar {
    align-items: stretch;
  }

  .messages-field {
    width: 100%;
  }

  .messages-count {
    margin: 0;
  }
}
</style>
