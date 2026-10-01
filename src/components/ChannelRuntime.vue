<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelPublic } from '@/api/types'
import StatusBadge from '@/components/StatusBadge.vue'

const props = defineProps<{ channel: ChannelPublic }>()

const services = computed(() => [
  {
    key: 'router',
    label: 'Router 服务',
    state: props.channel.runtime.state,
    detail: props.channel.runtime,
    problem: props.channel.runtime.error ? 'Router 服务异常，请查看运行日志。' : null,
  },
  {
    key: 'capture',
    label: '抓包服务',
    state: props.channel.capture_runtime.state,
    detail: props.channel.capture_runtime,
    problem: props.channel.capture_runtime.error
      ? '抓包服务异常，请检查抓包状态和磁盘空间。'
      : null,
  },
  {
    key: 'security-group',
    label: '阿里云安全组',
    state: props.channel.security_group.state,
    detail: null,
    problem: props.channel.security_group.error
      ? '安全组规则同步失败，请检查 RAM 权限和安全组配置。'
      : null,
  },
])

function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}
</script>

<template>
  <section
    class="runtime-panel"
    aria-labelledby="runtime-title"
  >
    <div class="runtime-panel__heading">
      <div>
        <p class="runtime-panel__eyebrow">
          服务状态
        </p>
        <h2 id="runtime-title">
          端口组与运行服务
        </h2>
      </div>
      <StatusBadge
        label="端口组"
        :state="channel.enabled ? 'active' : 'disabled'"
      />
    </div>

    <div class="runtime-grid">
      <article
        v-for="service in services"
        :key="service.key"
        class="runtime-service"
      >
        <div class="runtime-service__topline">
          <strong>{{ service.label }}</strong>
          <StatusBadge :state="service.state" />
        </div>
        <div
          v-if="service.detail"
          class="runtime-service__meta"
        >
          <span v-if="service.detail.pid !== null">PID {{ service.detail.pid }}</span>
          <span>启动时间 {{ formatDate(service.detail.active_since) }}</span>
          <span v-if="service.detail.result">结果 {{ service.detail.result }}</span>
        </div>
        <p
          v-if="service.problem"
          class="runtime-service__problem"
        >
          {{ service.problem }}
        </p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.runtime-panel {
  display: grid;
  gap: 1rem;
  padding: 1.1rem 1.2rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: #fff;
  box-shadow: var(--shadow-card);
}

.runtime-panel__heading,
.runtime-service__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.runtime-panel__eyebrow {
  margin: 0 0 0.25rem;
  color: #8594a4;
  font-size: 0.62rem;
  font-weight: 750;
  letter-spacing: 0.1em;
}

.runtime-panel h2 {
  margin: 0;
  color: #263a4f;
  font-size: 1rem;
}

.runtime-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.7rem;
}

.runtime-service {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 0.6rem;
  padding: 0.8rem;
  border: 1px solid #e7edf2;
  border-radius: 0.7rem;
  background: #fbfcfd;
}

.runtime-service__topline strong {
  color: #465a6e;
  font-size: 0.76rem;
}

.runtime-service__meta {
  display: grid;
  gap: 0.25rem;
  color: #8391a0;
  font-size: 0.65rem;
  line-height: 1.4;
}

.runtime-service__problem {
  margin: 0;
  color: #a3484e;
  font-size: 0.66rem;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .runtime-grid {
    grid-template-columns: 1fr;
  }
}
</style>
