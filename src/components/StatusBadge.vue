<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  state: string
  label?: string
}>()

const tone = computed(() => {
  if (
    ['available', 'active', 'ok', 'synced', 'online', 'connected'].includes(
      props.state,
    )
  ) return 'good'
  if (['checking', 'pending', 'starting', 'stopping'].includes(props.state)) {
    return 'pending'
  }
  if (
    [
      'degraded', 'cleanup_pending', 'unknown', 'inactive', 'offline',
      'disconnected',
    ].includes(props.state)
  ) {
    return 'muted'
  }
  return 'bad'
})

const statusText = computed(() => {
  const labels: Record<string, string> = {
    available: '在线',
    active: '运行中',
    ok: '正常',
    synced: '已同步',
    checking: '检查中',
    pending: '处理中',
    starting: '启动中',
    stopping: '停止中',
    degraded: '状态异常',
    cleanup_pending: '待清理',
    unknown: '未知',
    inactive: '已停止',
    unavailable: '不可用',
    failed: '失败',
    error: '异常',
    disabled: '已停用',
    online: '在线',
    offline: '离线',
    connected: '已连接',
    disconnected: '未连接',
    listening: '监听中',
  }
  return labels[props.state] ?? props.state
})
</script>

<template>
  <span
    class="status-badge"
    :class="`status-badge--${tone}`"
  >
    <span
      class="status-badge__dot"
      aria-hidden="true"
    />
    <span
      v-if="label"
      class="status-badge__label"
    >{{ label }}</span>
    {{ statusText }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  min-height: 1.7rem;
  padding: 0.2rem 0.58rem;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 650;
  line-height: 1.2;
  white-space: nowrap;
}

.status-badge__dot {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: currentColor;
}

.status-badge__label {
  color: var(--color-muted);
  font-weight: 550;
}

.status-badge--good {
  color: #107a5b;
  border-color: #ccecdf;
  background: #effaf5;
}

.status-badge--pending {
  color: #976014;
  border-color: #f1dfbd;
  background: #fff9ec;
}

.status-badge--muted {
  color: #657487;
  border-color: #e1e7ee;
  background: #f5f7f9;
}

.status-badge--bad {
  color: #ad3342;
  border-color: #f1cfd3;
  background: #fff2f3;
}
</style>
