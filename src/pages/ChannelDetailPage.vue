<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { deleteChannel, getChannel, getChannelLogs, getFlightMessages, getPacketSummaries, restartChannel, updateChannel } from '@/api/channels'
import { toChineseError } from '@/api/error-message'
import type { ChannelWrite } from '@/api/types'
import ChannelFormDialog from '@/components/ChannelFormDialog.vue'
import ChannelRuntime from '@/components/ChannelRuntime.vue'
import LinkQuality from '@/components/LinkQuality.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TerminalPanel from '@/components/TerminalPanel.vue'
import RouterLogPanel from '@/components/RouterLogPanel.vue'
import { usePolling } from '@/composables/usePolling'

const route = useRoute()
const router = useRouter()
const channelId = computed(() => String(route.params.id ?? ''))
const enabled = computed(() => channelId.value.length > 0)
const channelPolling = usePolling(() => getChannel(channelId.value), 1_000, enabled, channelId)
const logsPolling = usePolling(() => getChannelLogs(channelId.value, 500), 2_000, enabled, channelId)
const messagesPolling = usePolling(() => getFlightMessages(channelId.value, 100), 1_000, enabled, channelId)
const packetsPolling = usePolling(() => getPacketSummaries(channelId.value, 100), 1_000, enabled, channelId)

const channel = computed(() => channelPolling.data.value)
const logLines = computed(() => logsPolling.data.value ?? [])
const messageLines = computed(() =>
  (messagesPolling.data.value ?? []).map((message) =>
    `[${formatClock(message.received_at)}] [${message.severity_name}] ${message.text}`,
  ),
)
const packetLines = computed(() =>
  (packetsPolling.data.value ?? []).map((packet) => {
    const peer = `${packet.source ?? '未知来源'} → ${packet.destination ?? '未知目标'}`
    const protocol = packet.protocol ?? '未知协议'
    const length = packet.length_bytes === null ? '未知长度' : `${packet.length_bytes} 字节`
    return `[${formatClock(packet.captured_at)}] ${protocol} ${peer} · ${length} · ${packet.summary}`
  }),
)
const channelError = computed(() =>
  channelPolling.error.value
    ? toChineseError(channelPolling.error.value, '读取端口组状态失败。')
    : null,
)
const isLoading = computed(() => !channel.value && channelPolling.loading.value)
const monitorStateText = computed(() => {
  if (!channel.value) return ''
  if (channel.value.telemetry.monitor_state === 'unavailable') return '监测服务不可用'
  if (channel.value.telemetry.uav_online) return '飞控在线'
  return channel.value.telemetry.last_packet_at
    ? '飞控最近断开'
    : '尚未收到飞控数据'
})

const actionError = ref<string | null>(null)
const actionMessage = ref<string | null>(null)
const formError = ref<string | null>(null)
const formOpen = ref(false)
const formSubmitting = ref(false)
const restartConfirmOpen = ref(false)
const deleteConfirmOpen = ref(false)
const pendingAction = ref<'restart' | 'delete' | null>(null)
const logsAutoScroll = ref(true)
const messagesAutoScroll = ref(true)
const packetsAutoScroll = ref(true)

function formatNumber(value: number | null, decimals = 1): string {
  if (value === null || !Number.isFinite(value)) return '—'
  if (Number.isInteger(value)) return String(value)
  return String(Number(value.toFixed(decimals)))
}

function formatClock(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '未知时间' : date.toLocaleTimeString()
}

function formatAge(seconds: number | null): string {
  if (seconds === null) return '—'
  return `${formatNumber(seconds, 2)} 秒前`
}

function formatRate(bytesPerSecond: number): string {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond < 0) return '—'
  if (bytesPerSecond < 1_024) return `${Math.round(bytesPerSecond)} B/s`
  return `${formatNumber(bytesPerSecond / 1_024)} KB/s`
}

function armedLabel(armed: boolean | null): string {
  if (armed === null) return '—'
  return armed ? '已解锁' : '未解锁'
}

async function refreshAll(): Promise<void> {
  await Promise.all([
    channelPolling.refresh(),
    logsPolling.refresh(),
    messagesPolling.refresh(),
    packetsPolling.refresh(),
  ])
}

function openEdit(): void {
  if (!channel.value) return
  actionMessage.value = null
  actionError.value = null
  formError.value = null
  formOpen.value = true
}

async function saveChannel(input: ChannelWrite): Promise<void> {
  if (formSubmitting.value) return
  const targetId = channelId.value
  formSubmitting.value = true
  formError.value = null
  actionMessage.value = null
  try {
    const updated = await updateChannel(targetId, input)
    if (channelId.value !== targetId) return
    channelPolling.data.value = updated
    const configurationApplied =
      updated.uav_udp_port === input.uav_udp_port &&
      updated.ground_station_port === input.ground_station_port &&
      updated.ground_station_protocol === input.ground_station_protocol &&
      updated.enabled === input.enabled
    await refreshAll()
    if (channelId.value !== targetId) return
    if (!configurationApplied) {
      formError.value = '服务器未应用本次端口配置，当前端口参数仍为原值。请检查下方安全组和服务状态后重试。'
      return
    }

    formOpen.value = false
    const subsystemFailed =
      updated.security_group.state === 'error' ||
      updated.security_group.state === 'cleanup_pending' ||
      (updated.enabled &&
        (updated.runtime.state === 'failed' || updated.capture_runtime.state === 'failed'))
    actionMessage.value = subsystemFailed
      ? '配置已保存，但阿里云安全组同步或运行服务状态异常，请检查下方状态。'
      : '端口组配置已保存。'
  } catch (error: unknown) {
    if (channelId.value === targetId) {
      formError.value = toChineseError(error, '保存端口组失败，请检查配置后重试。')
    }
  } finally {
    formSubmitting.value = false
  }
}

async function confirmRestart(): Promise<void> {
  if (pendingAction.value || !channel.value) return
  const targetId = channelId.value
  pendingAction.value = 'restart'
  actionError.value = null
  actionMessage.value = null
  try {
    const updated = await restartChannel(targetId)
    if (channelId.value !== targetId) return
    channelPolling.data.value = updated
    restartConfirmOpen.value = false
    actionMessage.value = 'Router 重启请求已完成。'
    await refreshAll()
  } catch (error: unknown) {
    if (channelId.value === targetId) {
      actionError.value = toChineseError(error, 'Router 重启失败，请检查运行状态后重试。')
      restartConfirmOpen.value = false
    }
  } finally {
    pendingAction.value = null
  }
}

async function confirmDelete(): Promise<void> {
  if (pendingAction.value) return
  const targetId = channelId.value
  pendingAction.value = 'delete'
  actionError.value = null
  try {
    await deleteChannel(targetId)
    if (channelId.value === targetId) {
      await router.replace({ name: 'channels' })
    }
  } catch (error: unknown) {
    if (channelId.value === targetId) {
      actionError.value = toChineseError(error, '删除端口组失败，请检查服务状态后重试。')
      deleteConfirmOpen.value = false
    }
  } finally {
    pendingAction.value = null
  }
}

watch(channelId, (nextId, previousId) => {
  if (!nextId || nextId === previousId) return
  channelPolling.data.value = undefined
  logsPolling.data.value = undefined
  messagesPolling.data.value = undefined
  packetsPolling.data.value = undefined
  formOpen.value = false
  restartConfirmOpen.value = false
  deleteConfirmOpen.value = false
  formError.value = null
  actionError.value = null
  actionMessage.value = null
  void refreshAll()
})
</script>

<template>
  <section class="channel-detail page-stack">
    <RouterLink
      class="back-link"
      :to="{ name: 'channels' }"
    >
      <span aria-hidden="true">←</span>
      返回端口组
    </RouterLink>

    <header class="detail-heading">
      <div class="detail-heading__copy">
        <p class="detail-heading__eyebrow">
          端口组详情
        </p>
        <h1 v-if="channel">
          飞控 UDP {{ channel.uav_udp_port }}
          <span>/</span>
          {{ channel.ground_station_protocol.toUpperCase() }} {{ channel.ground_station_port }}
        </h1>
        <h1 v-else>
          端口组状态
        </h1>
        <p
          v-if="channel"
          class="detail-heading__meta"
        >
          监测端口 UDP {{ channel.monitor_udp_port }}
          <span>·</span>
          SYSID {{ channel.telemetry.system_id ?? '—' }}
        </p>
        <p
          v-else
          class="detail-heading__meta"
        >
          实时状态、飞控遥测与服务信息
        </p>
      </div>
      <div
        v-if="channel"
        class="detail-actions"
      >
        <button
          class="detail-action detail-action--primary"
          type="button"
          @click="openEdit"
        >
          修改配置
        </button>
        <button
          class="detail-action"
          type="button"
          :disabled="!channel.enabled || pendingAction !== null"
          @click="restartConfirmOpen = true"
        >
          重启 Router
        </button>
        <button
          class="detail-action detail-action--danger"
          type="button"
          :disabled="pendingAction !== null"
          @click="deleteConfirmOpen = true"
        >
          删除端口组
        </button>
        <button
          class="detail-action detail-action--icon"
          type="button"
          :disabled="channelPolling.loading.value"
          aria-label="刷新状态"
          @click="refreshAll"
        >
          ↻
        </button>
      </div>
    </header>

    <p
      v-if="actionMessage"
      class="detail-notice detail-notice--success"
      role="status"
    >
      {{ actionMessage }}
    </p>
    <p
      v-if="actionError"
      class="detail-notice detail-notice--error"
      role="alert"
    >
      {{ actionError }}
    </p>
    <div
      v-if="channelError"
      class="detail-load-error"
      role="alert"
    >
      <span>{{ channelError }}</span>
      <button
        class="detail-action"
        type="button"
        @click="refreshAll"
      >
        重试
      </button>
    </div>
    <div
      v-else-if="isLoading"
      class="detail-loading"
      role="status"
    >
      正在读取端口组状态…
    </div>

    <template v-if="channel">
      <section class="telemetry-panel">
        <div class="telemetry-panel__heading">
          <div>
            <p class="detail-section__eyebrow">
              飞控与地面站
            </p>
            <h2>实时遥测</h2>
          </div>
          <div class="telemetry-panel__badges">
            <StatusBadge
              label="飞控"
              :state="channel.telemetry.uav_online ? 'online' : 'offline'"
            />
            <StatusBadge
              label="地面站"
              :state="channel.telemetry.ground_station_connected ? 'connected' : 'disconnected'"
            />
          </div>
        </div>

        <div
          class="monitor-note"
          :class="{ 'monitor-note--error': channel.telemetry.monitor_state === 'unavailable' || !channel.telemetry.uav_online }"
        >
          <span
            class="monitor-note__dot"
            aria-hidden="true"
          />
          <strong>{{ monitorStateText }}</strong>
          <span v-if="channel.telemetry.monitor_state === 'unavailable'">
            UDP 监测服务当前不可用。
          </span>
          <span v-if="!channel.telemetry.uav_online && channel.telemetry.last_packet_at">
            飞控最近断开。
          </span>
          <span v-else-if="channel.telemetry.last_packet_at">
            最近收到飞控数据：{{ formatAge(channel.telemetry.last_packet_age_seconds) }}
          </span>
          <span v-else>收到首条飞控消息后，这里会显示遥测状态。</span>
        </div>

        <div class="telemetry-grid">
          <div class="telemetry-value">
            <span>飞行模式</span>
            <strong>{{ channel.telemetry.flight_mode ?? '—' }}</strong>
          </div>
          <div class="telemetry-value">
            <span>解锁状态</span>
            <strong>{{ armedLabel(channel.telemetry.armed) }}</strong>
          </div>
          <div class="telemetry-value">
            <span>电量</span>
            <strong>{{ channel.telemetry.battery_remaining_percent === null ? '—' : `${channel.telemetry.battery_remaining_percent}%` }}</strong>
          </div>
          <div class="telemetry-value">
            <span>电池电压</span>
            <strong>{{ channel.telemetry.battery_voltage_v === null ? '—' : `${formatNumber(channel.telemetry.battery_voltage_v)} V` }}</strong>
          </div>
          <div class="telemetry-value">
            <span>GPS 卫星数</span>
            <strong>{{ channel.telemetry.gps_satellites ?? '—' }}</strong>
          </div>
          <div class="telemetry-value">
            <span>GPS 定位类型</span>
            <strong>{{ channel.telemetry.gps_fix_type ?? '—' }}</strong>
          </div>
          <div class="telemetry-value">
            <span>海拔</span>
            <strong>{{ channel.telemetry.altitude_m === null ? '—' : `${formatNumber(channel.telemetry.altitude_m)} m` }}</strong>
          </div>
          <div class="telemetry-value">
            <span>相对高度</span>
            <strong>{{ channel.telemetry.relative_altitude_m === null ? '—' : `${formatNumber(channel.telemetry.relative_altitude_m)} m` }}</strong>
          </div>
          <div class="telemetry-value">
            <span>地速</span>
            <strong>{{ channel.telemetry.ground_speed_m_s === null ? '—' : `${formatNumber(channel.telemetry.ground_speed_m_s)} m/s` }}</strong>
          </div>
          <div class="telemetry-value">
            <span>飞控接收速率</span>
            <strong>{{ formatRate(channel.telemetry.uav_rx_bytes_per_second) }}</strong>
          </div>
          <div class="telemetry-value">
            <span>地面站发送速率</span>
            <strong>{{ formatRate(channel.telemetry.gcs_tx_bytes_per_second) }}</strong>
          </div>
          <div class="telemetry-value">
            <span>丢包 / 收包</span>
            <strong>{{ channel.telemetry.packets_lost_window }} / {{ channel.telemetry.packets_received_window }}</strong>
          </div>
        </div>

        <div class="telemetry-panel__quality">
          <LinkQuality :value="channel.telemetry.link_quality_percent" />
        </div>

        <div class="peer-grid">
          <div class="peer-card">
            <span>飞控对端</span>
            <strong>{{ channel.telemetry.uav_peer ?? '—' }}</strong>
          </div>
          <div class="peer-card">
            <span>地面站对端</span>
            <strong>{{ channel.telemetry.ground_station_peer ?? '—' }}</strong>
          </div>
          <div class="peer-card">
            <span>最近飞控数据</span>
            <strong>{{ channel.telemetry.last_packet_at ? formatClock(channel.telemetry.last_packet_at) : '—' }}</strong>
          </div>
          <div class="peer-card">
            <span>最近地面站数据</span>
            <strong>{{ channel.telemetry.ground_station_last_packet_at ? formatClock(channel.telemetry.ground_station_last_packet_at) : '—' }}</strong>
          </div>
        </div>
      </section>

      <ChannelRuntime :channel="channel" />

      <div class="terminal-grid">
        <RouterLogPanel
          :lines="logLines"
          :loading="logsPolling.initialLoading.value"
          :error="logsPolling.error.value ? toChineseError(logsPolling.error.value, '暂时无法读取 Router 日志。') : null"
          :auto-scroll="logsAutoScroll"
          @update:auto-scroll="logsAutoScroll = $event"
        />
        <TerminalPanel
          title="飞控消息 · STATUSTEXT"
          :lines="messageLines"
          :loading="messagesPolling.initialLoading.value"
          :error="messagesPolling.error.value ? toChineseError(messagesPolling.error.value, '暂时无法读取飞控消息。') : null"
          :auto-scroll="messagesAutoScroll"
          @update:auto-scroll="messagesAutoScroll = $event"
        />
      </div>
      <TerminalPanel
        title="实时 MAVLink 报文摘要"
        :lines="packetLines"
        :loading="packetsPolling.initialLoading.value"
        :error="packetsPolling.error.value ? toChineseError(packetsPolling.error.value, '暂时无法读取报文摘要。') : null"
        :auto-scroll="packetsAutoScroll"
        @update:auto-scroll="packetsAutoScroll = $event"
      />
    </template>

    <ChannelFormDialog
      :open="formOpen"
      :channel="channel ?? null"
      :submitting="formSubmitting"
      :error="formError"
      @close="formOpen = false"
      @submit="saveChannel"
    />

    <div
      v-if="restartConfirmOpen"
      class="confirm-backdrop"
      @click.self="restartConfirmOpen = false"
    >
      <section
        class="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="restart-title"
      >
        <p class="confirm-dialog__eyebrow">
          确认操作
        </p>
        <h2 id="restart-title">
          重启 Router？
        </h2>
        <p>重启期间，这组端口的 MAVLink 转发会短暂中断。</p>
        <footer>
          <button
            class="detail-action"
            type="button"
            :disabled="pendingAction !== null"
            @click="restartConfirmOpen = false"
          >
            取消
          </button>
          <button
            class="detail-action detail-action--primary"
            type="button"
            :disabled="pendingAction !== null"
            @click="confirmRestart"
          >
            {{ pendingAction === 'restart' ? '正在重启…' : '确认重启' }}
          </button>
        </footer>
      </section>
    </div>

    <div
      v-if="deleteConfirmOpen"
      class="confirm-backdrop"
      @click.self="deleteConfirmOpen = false"
    >
      <section
        class="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-title"
      >
        <p class="confirm-dialog__eyebrow confirm-dialog__eyebrow--danger">
          删除端口组
        </p>
        <h2 id="delete-title">
          确定删除这组端口吗？
        </h2>
        <p v-if="channel">
          将删除飞控 UDP {{ channel.uav_udp_port }} 与地面站 {{ channel.ground_station_protocol.toUpperCase() }} {{ channel.ground_station_port }} 的配置，并停止相关服务。
        </p>
        <footer>
          <button
            class="detail-action"
            type="button"
            :disabled="pendingAction !== null"
            @click="deleteConfirmOpen = false"
          >
            取消
          </button>
          <button
            class="detail-action detail-action--danger"
            type="button"
            :disabled="pendingAction !== null"
            @click="confirmDelete"
          >
            {{ pendingAction === 'delete' ? '正在删除…' : '确认删除' }}
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>

<style scoped>
.channel-detail {
  display: grid;
  width: 100%;
  gap: 1rem;
}

.back-link {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: 0.45rem;
  color: #52718a;
  font-size: 0.74rem;
  font-weight: 650;
  text-decoration: none;
}

.back-link:hover {
  color: #1f67a7;
}

.detail-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.25rem;
}

.detail-heading__copy {
  min-width: 0;
}

.detail-heading__eyebrow,
.detail-section__eyebrow {
  margin: 0 0 0.35rem;
  color: #74879a;
  font-size: 0.64rem;
  font-weight: 750;
  letter-spacing: 0.1em;
}

.detail-heading h1 {
  margin: 0;
  color: #1e3348;
  font-size: clamp(1.35rem, 2.5vw, 1.95rem);
  letter-spacing: -0.045em;
}

.detail-heading h1 span {
  margin: 0 0.22rem;
  color: #a1acb8;
  font-weight: 400;
}

.detail-heading__meta {
  margin: 0.4rem 0 0;
  color: #788899;
  font-size: 0.72rem;
}

.detail-heading__meta span {
  margin: 0 0.3rem;
}

.detail-actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.45rem;
}

.detail-action {
  display: inline-flex;
  min-height: 2.35rem;
  align-items: center;
  justify-content: center;
  padding: 0.45rem 0.7rem;
  border: 1px solid #dce4eb;
  border-radius: 0.55rem;
  color: #4e6276;
  background: #fff;
  cursor: pointer;
  font-size: 0.71rem;
  font-weight: 650;
  white-space: nowrap;
}

.detail-action:hover:not(:disabled) {
  border-color: #bad1e4;
  color: #1f67a7;
}

.detail-action:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.detail-action--primary {
  border-color: #246fb5;
  color: #fff;
  background: #246fb5;
}

.detail-action--primary:hover:not(:disabled) {
  border-color: #1c5d99;
  color: #fff;
  background: #1c5d99;
}

.detail-action--danger {
  border-color: #efd3d6;
  color: #a53b47;
  background: #fff7f7;
}

.detail-action--danger:hover:not(:disabled) {
  border-color: #d98c94;
  color: #8d2633;
}

.detail-action--icon {
  width: 2.35rem;
  padding: 0;
  font-size: 1.1rem;
}

.detail-notice,
.detail-load-error,
.detail-loading {
  margin: 0;
  padding: 0.7rem 0.85rem;
  border: 1px solid #e2e9ef;
  border-radius: var(--radius-sm);
  color: #53677b;
  background: #fff;
  font-size: 0.75rem;
}

.detail-notice--success {
  border-color: #ccecdf;
  color: #107a5b;
  background: #effaf5;
}

.detail-notice--error,
.detail-load-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-color: #f1cfd3;
  color: #983c47;
  background: #fff4f5;
}

.detail-loading {
  color: #718398;
  background: #fbfcfd;
}

.telemetry-panel {
  display: grid;
  gap: 1rem;
  padding: 1.15rem 1.25rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: #fff;
  box-shadow: var(--shadow-card);
}

.telemetry-panel__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.telemetry-panel__heading h2 {
  margin: 0;
  color: #263a4f;
  font-size: 1.05rem;
}

.telemetry-panel__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.monitor-note {
  display: flex;
  min-height: 2.45rem;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid #cfe9dc;
  border-radius: 0.65rem;
  color: #3f775e;
  background: #f3fbf7;
  font-size: 0.7rem;
}

.monitor-note strong {
  color: #24694d;
}

.monitor-note--error {
  border-color: #efd9b3;
  color: #87621d;
  background: #fffaf0;
}

.monitor-note--error strong {
  color: #795511;
}

.monitor-note__dot {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: #25a477;
}

.monitor-note--error .monitor-note__dot {
  background: #d4a03d;
}

.telemetry-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.8rem;
}

.telemetry-value {
  display: grid;
  min-width: 0;
  gap: 0.28rem;
  padding: 0.68rem 0.72rem;
  border: 1px solid #edf1f4;
  border-radius: 0.62rem;
  background: #fbfcfd;
}

.telemetry-value span,
.peer-card span {
  color: #7b8998;
  font-size: 0.65rem;
}

.telemetry-value strong,
.peer-card strong {
  overflow: hidden;
  color: #30485e;
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.telemetry-panel__quality {
  padding: 0.65rem 0.75rem;
  border: 1px solid #edf1f4;
  border-radius: 0.65rem;
}

.peer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.peer-card {
  display: grid;
  min-width: 0;
  gap: 0.25rem;
  padding: 0.6rem 0.75rem;
  border-top: 1px solid #edf1f4;
}

.peer-card strong {
  font-family: var(--font-mono);
  font-size: 0.7rem;
}

.terminal-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.confirm-backdrop {
  position: fixed;
  z-index: 70;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgb(13 28 42 / 48%);
  backdrop-filter: blur(3px);
}

.confirm-dialog {
  width: min(100%, 28rem);
  padding: 1.35rem;
  border: 1px solid #e2e9ef;
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: 0 28px 80px rgb(8 21 35 / 28%);
}

.confirm-dialog__eyebrow {
  margin: 0 0 0.35rem;
  color: #667d92;
  font-size: 0.65rem;
  font-weight: 750;
  letter-spacing: 0.08em;
}

.confirm-dialog__eyebrow--danger {
  color: #aa3f49;
}

.confirm-dialog h2 {
  margin: 0;
  color: #273d52;
  font-size: 1.15rem;
}

.confirm-dialog > p:not(.confirm-dialog__eyebrow) {
  margin: 0.65rem 0 1.2rem;
  color: #697a8c;
  font-size: 0.76rem;
  line-height: 1.6;
}

.confirm-dialog footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
}

@media (max-width: 930px) {
  .detail-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .telemetry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .terminal-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 500px) {
  .telemetry-panel__heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .peer-grid {
    grid-template-columns: 1fr;
  }

  .detail-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
  }
}
</style>
