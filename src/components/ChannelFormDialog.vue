<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ChannelPublic, ChannelWrite } from '@/api/types'

const props = withDefaults(
  defineProps<{
    open: boolean
    channel?: ChannelPublic | null
    submitting?: boolean
    error?: string | null
  }>(),
  { channel: null, submitting: false, error: null },
)

const emit = defineEmits<{
  close: []
  submit: [payload: ChannelWrite]
}>()

const uavUdpPort = ref('')
const groundStationPort = ref('')
const protocol = ref<ChannelWrite['ground_station_protocol']>('tcp')
const enabled = ref(true)
const validationError = ref<string | null>(null)

function resetForm(): void {
  uavUdpPort.value = props.channel ? String(props.channel.uav_udp_port) : ''
  groundStationPort.value = props.channel
    ? String(props.channel.ground_station_port)
    : ''
  protocol.value = props.channel?.ground_station_protocol ?? 'tcp'
  enabled.value = props.channel?.enabled ?? true
  validationError.value = null
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) resetForm()
  },
)
watch(
  () => props.channel?.id,
  () => {
    if (props.open) resetForm()
  },
)

function parsePort(value: string): number | null {
  if (!/^\d+$/.test(value)) return null
  const port = Number(value)
  return Number.isSafeInteger(port) && port >= 1 && port <= 65_535
    ? port
    : null
}

function submit(): void {
  if (props.submitting) return
  const uavPort = parsePort(uavUdpPort.value)
  if (uavPort === null) {
    validationError.value = '请输入 1–65535 之间的飞控 UDP 端口。'
    return
  }
  const stationPort = parsePort(groundStationPort.value)
  if (stationPort === null) {
    validationError.value = '请输入 1–65535 之间的地面站端口。'
    return
  }
  if (uavPort === stationPort && protocol.value === 'udp') {
    validationError.value = '同为 UDP 时，飞控端口和地面站端口不能相同。'
    return
  }

  validationError.value = null
  emit('submit', {
    uav_udp_port: uavPort,
    ground_station_port: stationPort,
    ground_station_protocol: protocol.value,
    enabled: enabled.value,
  })
}
</script>

<template>
  <div
    v-if="open"
    class="dialog-backdrop"
    @click.self="!submitting && emit('close')"
  >
    <section
      class="channel-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="channel-dialog-title"
    >
      <header class="channel-dialog__header">
        <div>
          <p class="channel-dialog__eyebrow">
            端口组配置
          </p>
          <h2 id="channel-dialog-title">
            {{ channel ? '修改端口组' : '新增端口组' }}
          </h2>
        </div>
        <button
          class="channel-dialog__close"
          type="button"
          aria-label="关闭"
          :disabled="submitting"
          @click="emit('close')"
        >
          ×
        </button>
      </header>

      <form
        class="channel-form"
        @submit.prevent="submit"
      >
        <div class="channel-form__field">
          <label for="uav-udp-port">飞控数据端口（UDP）</label>
          <input
            id="uav-udp-port"
            v-model="uavUdpPort"
            type="number"
            inputmode="numeric"
            min="1"
            max="65535"
            step="1"
            placeholder="例如 5760"
            autocomplete="off"
            :disabled="submitting"
          >
          <span>4G DTU 固定通过 UDP 向此端口发送数据。</span>
        </div>

        <div class="channel-form__field">
          <label for="ground-station-protocol">地面站连接协议</label>
          <select
            id="ground-station-protocol"
            v-model="protocol"
            :disabled="submitting"
          >
            <option value="tcp">
              TCP（默认）
            </option>
            <option value="udp">
              UDP
            </option>
          </select>
        </div>

        <div class="channel-form__field">
          <label for="ground-station-port">地面站连接端口</label>
          <input
            id="ground-station-port"
            v-model="groundStationPort"
            type="number"
            inputmode="numeric"
            min="1"
            max="65535"
            step="1"
            placeholder="例如 14552"
            autocomplete="off"
            :disabled="submitting"
          >
          <span>QGC 选择相同协议和端口连接服务器。</span>
        </div>

        <label class="channel-form__enabled">
          <input
            v-model="enabled"
            type="checkbox"
            :disabled="submitting"
          >
          <span>
            <strong>启用端口组</strong>
            <small>停用后将停止该组的服务转发。</small>
          </span>
        </label>

        <p
          v-if="validationError"
          class="channel-form__error"
          role="alert"
        >
          {{ validationError }}
        </p>
        <p
          v-if="error"
          class="channel-form__error"
          role="alert"
        >
          {{ error }}
        </p>

        <footer class="channel-form__actions">
          <button
            class="button button--secondary"
            type="button"
            :disabled="submitting"
            @click="emit('close')"
          >
            取消
          </button>
          <button
            class="button button--primary"
            type="submit"
            :disabled="submitting"
          >
            {{ submitting ? '正在保存…' : '保存配置' }}
          </button>
        </footer>
      </form>
    </section>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  z-index: 60;
  inset: 0;
  display: grid;
  overflow: auto;
  place-items: center;
  padding: 1.25rem;
  background: rgb(13 28 42 / 48%);
  backdrop-filter: blur(3px);
}

.channel-dialog {
  width: min(100%, 33rem);
  overflow: hidden;
  border: 1px solid #e2e9ef;
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: 0 28px 80px rgb(8 21 35 / 28%);
}

.channel-dialog__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.35rem 1.5rem 1.1rem;
  border-bottom: 1px solid #e9eef2;
}

.channel-dialog__eyebrow {
  margin: 0 0 0.3rem;
  color: var(--color-primary);
  font-size: 0.65rem;
  font-weight: 750;
  letter-spacing: 0.1em;
}

.channel-dialog h2 {
  margin: 0;
  color: #1f3448;
  font-size: 1.25rem;
  letter-spacing: -0.035em;
}

.channel-dialog__close {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border: 1px solid #e1e8ee;
  border-radius: 0.55rem;
  color: #627386;
  background: #fff;
  cursor: pointer;
  font-size: 1.25rem;
}

.channel-form {
  display: grid;
  gap: 1.05rem;
  padding: 1.3rem 1.5rem 1.45rem;
}

.channel-form__field {
  display: grid;
  gap: 0.4rem;
}

.channel-form__field label {
  color: #354b60;
  font-size: 0.8rem;
  font-weight: 650;
}

.channel-form__field input,
.channel-form__field select {
  width: 100%;
  min-height: 2.8rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid #d6e0e8;
  border-radius: var(--radius-sm);
  color: #263a4f;
  background: #fff;
}

.channel-form__field > span {
  color: #8492a1;
  font-size: 0.67rem;
  line-height: 1.45;
}

.channel-form__enabled {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.8rem;
  border: 1px solid #e4ebf0;
  border-radius: 0.7rem;
  background: #fafcfd;
  cursor: pointer;
}

.channel-form__enabled input {
  margin: 0.2rem 0 0;
  accent-color: var(--color-primary);
}

.channel-form__enabled span {
  display: grid;
  gap: 0.25rem;
}

.channel-form__enabled strong {
  color: #41566b;
  font-size: 0.76rem;
}

.channel-form__enabled small {
  color: #8794a1;
  font-size: 0.66rem;
}

.channel-form__error {
  margin: 0;
  padding: 0.7rem 0.8rem;
  border: 1px solid #efd0d4;
  border-radius: var(--radius-sm);
  color: #983c47;
  background: #fff4f5;
  font-size: 0.75rem;
  line-height: 1.5;
}

.channel-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.65rem;
  padding-top: 0.25rem;
}

.button {
  min-height: 2.6rem;
  padding: 0.55rem 0.9rem;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.76rem;
  font-weight: 700;
}

.button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.button--secondary {
  border-color: #dbe3ea;
  color: #52667a;
  background: #fff;
}

.button--primary {
  color: #fff;
  background: #246fb5;
}

@media (max-width: 520px) {
  .dialog-backdrop {
    align-items: end;
    padding: 0.5rem;
  }

  .channel-dialog {
    border-radius: 1rem;
  }

  .channel-dialog__header,
  .channel-form {
    padding-right: 1rem;
    padding-left: 1rem;
  }
}
</style>
