<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { downloadCapture, getPacketSummaries, listCaptures, listChannels } from '@/api/channels'
import { toChineseError } from '@/api/error-message'
import type { CaptureFilePublic } from '@/api/types'
import CaptureFileList from '@/components/CaptureFileList.vue'
import TerminalPanel from '@/components/TerminalPanel.vue'
import { usePolling } from '@/composables/usePolling'

const channelPolling = usePolling(listChannels, 15_000)
const channels = computed(() => channelPolling.data.value ?? [])
const selectedChannelId = ref('')
const selectedChannel = computed(() =>
  channels.value.find((channel) => channel.id === selectedChannelId.value) ?? null,
)
const capturesEnabled = computed(() => selectedChannelId.value.length > 0)
const packetPolling = usePolling(
  () => getPacketSummaries(selectedChannelId.value, 100),
  1_000,
  capturesEnabled,
  selectedChannelId,
)
const capturePolling = usePolling(
  () => listCaptures(selectedChannelId.value),
  15_000,
  capturesEnabled,
  selectedChannelId,
)
const autoScroll = ref(true)
const downloadingFileName = ref<string | null>(null)
const downloadError = ref<string | null>(null)
const downloadMessage = ref<string | null>(null)

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

watch(selectedChannelId, () => {
  downloadError.value = null
  downloadMessage.value = null
})

const captures = computed(() => capturePolling.data.value ?? [])
const packetLines = computed(() =>
  (packetPolling.data.value ?? []).map((packet) => {
    const date = new Date(packet.captured_at)
    const time = Number.isNaN(date.getTime())
      ? '未知时间'
      : date.toLocaleTimeString('zh-CN', { hour12: false })
    const peer = `${packet.source ?? '未知来源'} → ${packet.destination ?? '未知目标'}`
    const protocol = packet.protocol ?? '未知协议'
    const length = packet.length_bytes === null ? '未知长度' : `${packet.length_bytes} 字节`
    return `[${time}] ${protocol} ${peer} · ${length} · ${packet.summary}`
  }),
)
const channelError = computed(() =>
  channelPolling.error.value
    ? toChineseError(channelPolling.error.value, '无法读取端口组，请检查后端服务后重试。')
    : null,
)
const packetError = computed(() =>
  packetPolling.error.value
    ? toChineseError(packetPolling.error.value, '暂时无法读取实时报文，请稍后重试。')
    : null,
)
const capturesError = computed(() => {
  if (!capturePolling.error.value) return null
  const message = toChineseError(capturePolling.error.value, 'PCAP 文件更新失败，请稍后重试。')
  return capturePolling.data.value === undefined
    ? `${message} 当前没有可用的 PCAP 列表。`
    : `${message} 正在保留上次成功读取的 PCAP 列表。`
})

async function refresh(): Promise<void> {
  if (!selectedChannelId.value) {
    await channelPolling.refresh()
    return
  }
  await Promise.all([
    channelPolling.refresh(),
    packetPolling.refresh(),
    capturePolling.refresh(),
  ])
}

function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  anchor.hidden = true
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

async function downloadFile(capture: CaptureFilePublic): Promise<void> {
  const targetId = selectedChannelId.value
  if (!targetId || capture.is_current || downloadingFileName.value) return
  downloadingFileName.value = capture.file_name
  downloadError.value = null
  downloadMessage.value = null
  try {
    const blob = await downloadCapture(targetId, capture.file_name)
    saveBlob(blob, capture.file_name)
    if (selectedChannelId.value === targetId) {
      downloadMessage.value = 'PCAP 文件下载已开始。'
    }
  } catch (error: unknown) {
    if (selectedChannelId.value === targetId) {
      downloadError.value = toChineseError(error, 'PCAP 文件下载失败，请稍后重试。')
    }
  } finally {
    downloadingFileName.value = null
  }
}
</script>

<template>
  <section class="captures-page page-stack">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">
          网络记录
        </p>
        <h1>抓包文件</h1>
        <p class="page-heading__description">
          查看实时 MAVLink 报文摘要，并下载已完成写入的 PCAP 文件。
        </p>
      </div>
      <button
        class="quiet-button"
        type="button"
        aria-label="刷新抓包数据"
        :disabled="packetPolling.loading.value || capturePolling.loading.value || channelPolling.loading.value"
        @click="refresh"
      >
        <span aria-hidden="true">↻</span>
        {{ packetPolling.loading.value || capturePolling.loading.value ? '正在更新…' : '刷新' }}
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

    <template v-if="selectedChannel">
      <section
        class="captures-toolbar"
        aria-label="抓包筛选"
      >
        <label class="captures-field">
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
        <p class="captures-toolbar__meta">
          飞控 UDP {{ selectedChannel.uav_udp_port }}
          <span>·</span>
          {{ selectedChannel.ground_station_protocol.toUpperCase() }} {{ selectedChannel.ground_station_port }}
        </p>
      </section>

      <TerminalPanel
        title="实时 MAVLink 报文摘要"
        :lines="packetLines"
        :loading="packetPolling.initialLoading.value"
        :error="packetError"
        :auto-scroll="autoScroll"
        @update:auto-scroll="autoScroll = $event"
      />

      <section class="capture-files-panel">
        <header class="capture-files-panel__heading">
          <div>
            <p class="capture-files-panel__eyebrow">
              本地抓包轮转文件
            </p>
            <h2>PCAP 文件</h2>
            <span class="capture-files-panel__interval">每 10 分钟轮转 · 列表每 15 秒更新</span>
          </div>
          <button
            class="quiet-button quiet-button--small"
            type="button"
            aria-label="刷新 PCAP 文件列表"
            :disabled="capturePolling.loading.value"
            @click="capturePolling.refresh"
          >
            <span aria-hidden="true">↻</span>
            刷新文件
          </button>
        </header>

        <p
          v-if="downloadMessage"
          class="download-notice download-notice--success"
          role="status"
        >
          {{ downloadMessage }}
        </p>
        <p
          v-if="downloadError"
          class="download-notice download-notice--error"
          role="alert"
        >
          {{ downloadError }}
        </p>

        <CaptureFileList
          :captures="captures"
          :loading="capturePolling.initialLoading.value"
          :error="capturesError"
          :downloading-file-name="downloadingFileName"
          @download="downloadFile"
        />
      </section>
    </template>

    <div
      v-else-if="!channelError && (channelPolling.initialLoading.value || channelPolling.data.value === undefined)"
      class="captures-empty"
      role="status"
    >
      正在读取端口组…
    </div>
    <div
      v-else-if="!channelError"
      class="captures-empty"
      role="status"
    >
      <strong>尚未配置端口组</strong>
      <span>创建端口组并启用抓包后，报文摘要和 PCAP 文件会显示在这里。</span>
    </div>
  </section>
</template>

<style scoped>
.captures-page {
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

.quiet-button:hover:not(:disabled) {
  border-color: #b9d0e4;
  color: #1f67a7;
}

.quiet-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.quiet-button--small {
  min-height: 2.1rem;
  padding: 0.35rem 0.6rem;
  font-size: 0.68rem;
}

.captures-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 0.9rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.captures-field {
  display: grid;
  min-width: min(100%, 17rem);
  gap: 0.35rem;
  color: #566a7e;
  font-size: 0.69rem;
  font-weight: 650;
}

.captures-field select {
  min-height: 2.4rem;
  padding: 0.4rem 2rem 0.4rem 0.65rem;
  border: 1px solid #d8e1e9;
  border-radius: 0.5rem;
  color: #32485d;
  background: #fff;
  font-size: 0.75rem;
}

.captures-toolbar__meta {
  margin: 0 0 0.58rem auto;
  color: #74879a;
  font-family: var(--font-mono);
  font-size: 0.69rem;
}

.captures-toolbar__meta span {
  margin: 0 0.35rem;
  color: #a5b0bb;
}

.capture-files-panel {
  display: grid;
  gap: 0.9rem;
  padding: 1rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.capture-files-panel__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.capture-files-panel__eyebrow {
  margin: 0 0 0.25rem;
  color: #8997a7;
  font-size: 0.59rem;
  font-weight: 750;
  letter-spacing: 0.12em;
}

.capture-files-panel__heading h2 {
  margin: 0;
  color: #263a4f;
  font-size: 1.02rem;
}

.capture-files-panel__interval {
  display: block;
  margin-top: 0.3rem;
  color: #8492a0;
  font-size: 0.63rem;
}

.download-notice {
  margin: 0;
  padding: 0.65rem 0.8rem;
  border: 1px solid;
  border-radius: 0.5rem;
  font-size: 0.73rem;
  line-height: 1.5;
}

.download-notice--success {
  border-color: #c7e8da;
  color: #217354;
  background: #f0fbf6;
}

.download-notice--error {
  border-color: #f0d1d4;
  color: #9b3541;
  background: #fff5f5;
}

.captures-empty {
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

.captures-empty strong {
  color: #506277;
  font-size: 0.85rem;
}

.captures-empty span {
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

  .captures-toolbar {
    align-items: stretch;
  }

  .captures-field {
    width: 100%;
  }

  .captures-toolbar__meta {
    margin: 0;
  }
}
</style>
