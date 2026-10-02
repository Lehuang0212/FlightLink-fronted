<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { listChannels } from '@/api/channels'
import ChannelCard from '@/components/ChannelCard.vue'
import SummaryCard from '@/components/SummaryCard.vue'
import { usePolling } from '@/composables/usePolling'

interface ActivityEntry {
  id: string
  message: string
  time: string
}

interface ChannelSnapshot {
  uavOnline: boolean
  groundStationConnected: boolean
  ports: string
}

const polling = usePolling(listChannels, 1_000)
const channels = computed(() => polling.data.value ?? [])
const hasLoaded = computed(() => polling.data.value !== undefined)
const onlineUavCount = computed(
  () => channels.value.filter((channel) => channel.telemetry.uav_online).length,
)
const connectedGroundStationCount = computed(
  () =>
    channels.value.filter((channel) => channel.telemetry.ground_station_connected)
      .length,
)
const visibleChannels = computed(() => channels.value.slice(0, 5))
const activity = ref<ActivityEntry[]>([])
let hasBaseline = false
let priorState = new Map<string, ChannelSnapshot>()

watch(
  channels,
  (currentChannels) => {
    const nextState = new Map<string, ChannelSnapshot>()
    const changes: ActivityEntry[] = []

    for (const channel of currentChannels) {
      const current: ChannelSnapshot = {
        uavOnline: channel.telemetry.uav_online,
        groundStationConnected: channel.telemetry.ground_station_connected,
        ports: `${channel.uav_udp_port} / ${channel.ground_station_port}`,
      }
      nextState.set(channel.id, current)

      const previous = priorState.get(channel.id)
      if (hasBaseline && previous) {
        if (previous.uavOnline !== current.uavOnline) {
          changes.push({
            id: `${channel.id}-uav-${Date.now()}-${changes.length}`,
            message: `飞控${current.uavOnline ? '已连接' : '已断开'} · ${current.ports}`,
            time: new Date().toLocaleTimeString(),
          })
        }
        if (previous.groundStationConnected !== current.groundStationConnected) {
          changes.push({
            id: `${channel.id}-gcs-${Date.now()}-${changes.length}`,
            message: `地面站${current.groundStationConnected ? '已连接' : '已断开'} · ${current.ports}`,
            time: new Date().toLocaleTimeString(),
          })
        }
      }
    }

    if (changes.length > 0) activity.value = [...changes.reverse(), ...activity.value].slice(0, 8)
    priorState = nextState
    hasBaseline = true
  },
  { immediate: true },
)

async function refresh(): Promise<void> {
  await polling.refresh()
}
</script>

<template>
  <section class="overview-page page-stack">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">
          FLIGHTLINK · 运行总览
        </p>
        <h1>运行总览</h1>
        <p class="page-heading__description">
          实时查看 MAVLink 端口组、无人机和地面站连接状态。
        </p>
      </div>
      <button
        class="quiet-button"
        type="button"
        :disabled="polling.loading.value"
        @click="refresh"
      >
        <span aria-hidden="true">↻</span>
        {{ polling.loading.value ? '正在更新…' : '刷新' }}
      </button>
    </header>

    <p
      v-if="polling.error.value"
      class="page-alert"
      role="status"
    >
      {{ hasLoaded ? '更新失败，当前显示最近一次成功获取的数据。' : '无法读取端口组，请检查后端服务后重试。' }}
      <button
        type="button"
        @click="refresh"
      >
        重试
      </button>
    </p>

    <div
      class="summary-grid"
      aria-label="运行状态汇总"
    >
      <SummaryCard
        label="端口组"
        :value="channels.length"
        detail="已配置的端口对"
        marker="01"
      />
      <SummaryCard
        label="无人机在线"
        :value="`${onlineUavCount} / ${channels.length}`"
        detail="正在回传飞行数据"
        marker="02"
      />
      <SummaryCard
        label="地面站连接"
        :value="`${connectedGroundStationCount} / ${channels.length}`"
        detail="已连接的 QGC 客户端"
        marker="03"
      />
    </div>

    <div class="overview-grid">
      <section class="overview-panel overview-panel--channels">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__eyebrow">
              当前连接
            </p>
            <h2>端口组</h2>
          </div>
          <RouterLink
            class="text-link"
            :to="{ name: 'channels' }"
          >
            查看全部 <span aria-hidden="true">→</span>
          </RouterLink>
        </div>

        <div
          v-if="visibleChannels.length"
          class="channel-card-list"
        >
          <ChannelCard
            v-for="channel in visibleChannels"
            :key="channel.id"
            :channel="channel"
          />
        </div>
        <div
          v-else-if="polling.initialLoading.value || !hasLoaded"
          class="empty-state"
        >
          <span
            class="empty-state__loader"
            aria-hidden="true"
          />
          <strong>正在读取实时状态</strong>
          <span>正在连接端口组服务…</span>
        </div>
        <div
          v-else
          class="empty-state"
        >
          <span
            class="empty-state__icon"
            aria-hidden="true"
          >＋</span>
          <strong>尚未配置端口组</strong>
          <span>新增端口对后，即可监测无人机与地面站连接。</span>
        </div>
      </section>

      <section class="overview-panel overview-panel--activity">
        <div class="panel-heading">
          <div>
            <p class="panel-heading__eyebrow">
              本次访问
            </p>
            <h2>近期状态变化</h2>
          </div>
          <span
            class="activity-live-dot"
            aria-label="正在轮询状态"
          />
        </div>

        <ol
          v-if="activity.length"
          class="activity-list"
        >
          <li
            v-for="entry in activity"
            :key="entry.id"
            class="activity-list__item"
          >
            <span
              class="activity-list__dot"
              aria-hidden="true"
            />
            <span class="activity-list__message">{{ entry.message }}</span>
            <time class="activity-list__time">{{ entry.time }}</time>
          </li>
        </ol>
        <div
          v-else
          class="activity-empty"
        >
          <span
            class="activity-empty__icon"
            aria-hidden="true"
          >◷</span>
          <strong>本次访问尚未观察到状态变化</strong>
          <span>新出现的连接和断开事件会显示在这里。</span>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-stack {
  display: grid;
  width: 100%;
  gap: 1.35rem;
}

.page-heading,
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}

.page-heading__eyebrow,
.panel-heading__eyebrow {
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.9rem;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(17rem, 0.8fr);
  align-items: start;
  gap: 1rem;
}

.overview-panel {
  min-width: 0;
  padding: 1.15rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading__eyebrow {
  margin-bottom: 0.25rem;
  color: #8997a7;
  font-size: 0.59rem;
}

.panel-heading h2 {
  margin: 0;
  color: #263a4f;
  font-size: 1.05rem;
  letter-spacing: -0.025em;
}

.text-link {
  color: #276eaa;
  font-size: 0.75rem;
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
}

.text-link:hover {
  color: #174f82;
  text-decoration: underline;
}

.channel-card-list {
  display: grid;
  gap: 0.8rem;
}

.activity-live-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: #1ca779;
  box-shadow: 0 0 0 4px rgb(28 167 121 / 10%);
}

.activity-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.activity-list__item {
  display: grid;
  grid-template-columns: 0.6rem minmax(0, 1fr) auto;
  align-items: start;
  gap: 0.55rem;
  padding: 0.8rem 0;
  border-bottom: 1px solid #eef1f5;
}

.activity-list__item:first-child {
  padding-top: 0.2rem;
}

.activity-list__item:last-child {
  border-bottom: 0;
}

.activity-list__dot {
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.23rem;
  border-radius: 50%;
  background: #458dca;
}

.activity-list__message {
  color: #44576c;
  font-size: 0.73rem;
  line-height: 1.45;
}

.activity-list__time {
  color: #8996a5;
  font-family: var(--font-mono);
  font-size: 0.64rem;
}

.activity-empty,
.empty-state {
  display: grid;
  justify-items: center;
  gap: 0.55rem;
  padding: 2.1rem 1rem;
  color: var(--color-muted);
  text-align: center;
}

.activity-empty__icon,
.empty-state__icon {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  place-items: center;
  border: 1px solid #e2e9ef;
  border-radius: 50%;
  color: #7591a9;
  background: #f7fafc;
  font-size: 1.15rem;
}

.activity-empty strong,
.empty-state strong {
  color: #506277;
  font-size: 0.76rem;
  font-weight: 650;
}

.activity-empty > span:last-child,
.empty-state > span:last-child {
  max-width: 19rem;
  font-size: 0.68rem;
  line-height: 1.5;
}

.empty-state {
  padding: 2.5rem 1rem;
  border: 1px dashed #dce5ec;
  border-radius: 0.75rem;
  background: #fbfcfd;
}

.empty-state__loader {
  width: 1.6rem;
  height: 1.6rem;
  border: 2px solid #dce7ef;
  border-top-color: #3988c7;
  border-radius: 50%;
  animation: spin 850ms linear infinite;
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
  color: #805915;
  background: transparent;
  cursor: pointer;
  font-size: inherit;
  font-weight: 700;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1050px) {
  .overview-grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(15rem, 0.8fr);
  }
}

@media (max-width: 850px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .overview-panel--activity {
    order: 2;
  }
}

@media (max-width: 620px) {
  .page-heading {
    align-items: flex-start;
  }

  .page-heading__description {
    max-width: 25rem;
  }

  .quiet-button {
    padding: 0.48rem 0.6rem;
    font-size: 0;
  }

  .quiet-button span {
    font-size: 1rem;
  }

  .summary-grid {
    grid-template-columns: 1fr;
    gap: 0.6rem;
  }

  .summary-card {
    min-height: 7rem;
  }
}
</style>
