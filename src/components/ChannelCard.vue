<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { ChannelPublic } from '@/api/types'
import LinkQuality from '@/components/LinkQuality.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { formatDecimal } from '@/format'

const props = defineProps<{ channel: ChannelPublic }>()

const telemetry = computed(() => props.channel.telemetry)
function display(value: string | number | null, suffix = ''): string {
  return value === null ? '—' : `${value}${suffix}`
}

function armedText(value: boolean | null): string {
  if (value === null) return '—'
  return value ? '已解锁' : '未解锁'
}

function lastPacketText(age: number | null): string {
  if (age === null) return '尚未收到飞控数据'
  return `最近收到数据：${formatDecimal(age)} 秒前`
}
</script>

<template>
  <RouterLink
    class="channel-card"
    :to="{ name: 'channel-detail', params: { id: channel.id } }"
    :aria-label="`飞控 UDP ${channel.uav_udp_port}，地面站 ${channel.ground_station_protocol.toUpperCase()} ${channel.ground_station_port}`"
  >
    <div class="channel-card__header">
      <div class="channel-card__identity">
        <span class="channel-card__eyebrow">端口组</span>
        <h3>
          飞控 UDP <span>{{ channel.uav_udp_port }}</span>
          <span class="channel-card__separator">/</span>
          {{ channel.ground_station_protocol.toUpperCase() }}
          <span>{{ channel.ground_station_port }}</span>
        </h3>
        <p class="channel-card__packet-age">
          {{ lastPacketText(telemetry.last_packet_age_seconds) }}
        </p>
      </div>
      <span
        class="channel-card__chevron"
        aria-hidden="true"
      >↗</span>
    </div>

    <div class="channel-card__status-row">
      <StatusBadge
        label="飞控"
        :state="telemetry.uav_online ? 'online' : 'offline'"
      />
      <StatusBadge
        label="地面站"
        :state="telemetry.ground_station_connected ? 'connected' : 'disconnected'"
      />
      <span class="channel-card__sysid">SYSID <strong>{{ display(telemetry.system_id) }}</strong></span>
    </div>

    <div class="channel-card__quality-row">
      <LinkQuality :value="telemetry.link_quality_percent" />
    </div>

    <div class="channel-card__telemetry">
      <div class="telemetry-item">
        <span>飞行模式</span>
        <strong>{{ telemetry.flight_mode ?? '—' }}</strong>
      </div>
      <div class="telemetry-item">
        <span>解锁状态</span>
        <strong>{{ armedText(telemetry.armed) }}</strong>
      </div>
      <div class="telemetry-item">
        <span>电池</span>
        <strong>{{ display(telemetry.battery_remaining_percent, '%') }}</strong>
      </div>
      <div class="telemetry-item">
        <span>卫星数</span>
        <strong>{{ display(telemetry.gps_satellites) }}</strong>
      </div>
      <div class="telemetry-item">
        <span>海拔</span>
        <strong>{{ telemetry.altitude_m === null ? '—' : `${formatDecimal(telemetry.altitude_m)} m` }}</strong>
      </div>
      <div class="telemetry-item">
        <span>地速</span>
        <strong>{{ telemetry.ground_speed_m_s === null ? '—' : `${formatDecimal(telemetry.ground_speed_m_s)} m/s` }}</strong>
      </div>
    </div>

    <div class="channel-card__footer">
      <span>Router</span>
      <StatusBadge :state="channel.runtime.state" />
      <span class="channel-card__footer-spacer" />
      <span>抓包</span>
      <StatusBadge :state="channel.capture_runtime.state" />
      <span class="channel-card__footer-spacer" />
      <span>安全组</span>
      <StatusBadge :state="channel.security_group.state" />
    </div>
  </RouterLink>
</template>

<style scoped>
.channel-card {
  display: grid;
  min-width: 0;
  gap: 1rem;
  padding: 1.15rem 1.25rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  color: inherit;
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
  text-decoration: none;
  transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
}

.channel-card:hover {
  border-color: #c5d9eb;
  box-shadow: 0 18px 38px rgb(28 53 80 / 12%);
  transform: translateY(-1px);
}

.channel-card__header,
.channel-card__status-row,
.channel-card__footer {
  display: flex;
  align-items: center;
}

.channel-card__header {
  justify-content: space-between;
  gap: 1rem;
}

.channel-card__identity {
  min-width: 0;
}

.channel-card__eyebrow {
  color: #8392a3;
  font-size: 0.62rem;
  font-weight: 750;
  letter-spacing: 0.13em;
}

.channel-card h3 {
  margin: 0.3rem 0 0;
  color: #25394e;
  font-size: 1rem;
  letter-spacing: -0.025em;
}

.channel-card h3 > span:not(.channel-card__separator) {
  font-family: var(--font-mono);
  font-size: 0.95em;
}

.channel-card__separator {
  margin: 0 0.25rem;
  color: #94a1af;
  font-weight: 450;
}

.channel-card__packet-age {
  margin: 0.3rem 0 0;
  color: var(--color-muted);
  font-size: 0.7rem;
}

.channel-card__chevron {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #e3eaf0;
  border-radius: 0.6rem;
  color: #718397;
  background: #f9fbfc;
}

.channel-card__status-row {
  flex-wrap: wrap;
  gap: 0.45rem;
}

.channel-card__sysid {
  margin-left: auto;
  color: var(--color-muted);
  font-size: 0.7rem;
}

.channel-card__sysid strong {
  margin-left: 0.2rem;
  color: #40546a;
  font-family: var(--font-mono);
}

.channel-card__quality-row {
  min-height: 2.2rem;
  padding: 0.45rem 0;
  border-top: 1px solid #eef1f5;
  border-bottom: 1px solid #eef1f5;
}

.channel-card__telemetry {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.85rem 1rem;
}

.telemetry-item {
  display: grid;
  min-width: 0;
  gap: 0.25rem;
}

.telemetry-item span {
  overflow: hidden;
  color: #7b8998;
  font-size: 0.65rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.telemetry-item strong {
  overflow: hidden;
  color: #34495e;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.channel-card__footer {
  gap: 0.4rem;
  padding-top: 0.8rem;
  border-top: 1px solid #eef1f5;
  color: #8290a0;
  font-size: 0.66rem;
}

.channel-card__footer-spacer {
  flex: 1;
}

@media (max-width: 560px) {
  .channel-card {
    padding: 1rem;
  }

  .channel-card__telemetry {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .channel-card__footer {
    flex-wrap: wrap;
  }
}
</style>
