<script setup lang="ts">
import { computed, ref } from 'vue'
import { createChannel, listChannels } from '@/api/channels'
import { toChineseError } from '@/api/error-message'
import type { ChannelWrite } from '@/api/types'
import ChannelCard from '@/components/ChannelCard.vue'
import ChannelFormDialog from '@/components/ChannelFormDialog.vue'
import { usePolling } from '@/composables/usePolling'

const polling = usePolling(listChannels, 3_000)
const channels = computed(() => polling.data.value ?? [])
const hasLoaded = computed(() => polling.data.value !== undefined)
const atLimit = computed(() => channels.value.length >= 5)
const dialogOpen = ref(false)
const submitting = ref(false)
const formError = ref<string | null>(null)
const operationMessage = ref<string | null>(null)
const operationNeedsAttention = ref(false)

async function refresh(): Promise<void> {
  await polling.refresh()
}

function openCreateDialog(): void {
  formError.value = null
  operationMessage.value = null
  operationNeedsAttention.value = false
  dialogOpen.value = true
}

async function createPortGroup(input: ChannelWrite): Promise<void> {
  if (atLimit.value || submitting.value) return
  submitting.value = true
  formError.value = null
  operationMessage.value = null
  operationNeedsAttention.value = false
  try {
    const created = await createChannel(input)
    dialogOpen.value = false
    if (created.security_group.state === 'error') {
      operationMessage.value = '端口组已创建，但阿里云安全组规则同步失败，请查看该组状态。'
      operationNeedsAttention.value = true
    } else if (created.security_group.state === 'cleanup_pending') {
      operationMessage.value = '端口组已创建，但安全组规则仍待清理，请查看该组状态。'
      operationNeedsAttention.value = true
    } else if (created.security_group.state === 'pending') {
      operationMessage.value = '端口组已创建，阿里云安全组规则正在同步。'
    } else {
      operationMessage.value = '端口组已创建。'
    }
    await polling.refresh()
  } catch (error: unknown) {
    formError.value = toChineseError(error, '创建端口组失败，请检查服务状态后重试。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="channels-page page-stack">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">
          连接管理
        </p>
        <h1>端口组</h1>
        <p class="page-heading__description">
          每组由飞控 UDP 入口和地面站连接端口组成。
        </p>
      </div>
      <div class="page-heading__actions">
        <button
          class="quiet-button create-channel"
          type="button"
          :disabled="atLimit"
          :title="atLimit ? '最多配置 5 组端口组' : undefined"
          @click="openCreateDialog"
        >
          <span aria-hidden="true">＋</span>
          新增端口组
        </button>
        <button
          class="quiet-button"
          type="button"
          :disabled="polling.loading.value"
          @click="refresh"
        >
          <span aria-hidden="true">↻</span>
          {{ polling.loading.value ? '正在更新…' : '刷新' }}
        </button>
      </div>
    </header>

    <div class="channels-toolbar">
      <span>
        <strong>{{ channels.length }}</strong>
        组
      </span>
      <span class="channels-toolbar__refresh">
        页面显示时每 3 秒更新一次
      </span>
    </div>

    <p
      v-if="atLimit"
      class="channels-limit-note"
    >
      最多配置 5 组端口组。
    </p>
    <p
      v-if="operationMessage"
      class="channels-success"
      :class="{ 'channels-success--warning': operationNeedsAttention }"
      :role="operationNeedsAttention ? 'alert' : 'status'"
    >
      {{ operationMessage }}
    </p>

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
      v-if="channels.length"
      class="channels-grid"
    >
      <ChannelCard
        v-for="channel in channels"
        :key="channel.id"
        :channel="channel"
      />
    </div>
    <div
      v-else-if="polling.loading.value || !hasLoaded"
      class="empty-state"
    >
      <span
        class="empty-state__loader"
        aria-hidden="true"
      />
      <strong>正在读取端口组</strong>
      <span>正在获取无人机和地面站连接状态…</span>
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
      <span>创建端口组后，连接状态会显示在这里。</span>
    </div>

    <ChannelFormDialog
      :open="dialogOpen"
      :submitting="submitting"
      :error="formError"
      @close="dialogOpen = false"
      @submit="createPortGroup"
    />
  </section>
</template>

<style scoped>
.channels-page {
  display: grid;
  width: 100%;
  gap: 1.2rem;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}

.page-heading__actions {
  display: flex;
  flex: 0 0 auto;
  gap: 0.55rem;
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

.quiet-button.create-channel {
  border-color: #c7dff2;
  color: #1f67a7;
  background: #f7fbff;
}

.quiet-button.create-channel:disabled {
  border-color: #e2e8ed;
  color: #9aa6b2;
  background: #f8fafb;
}

.quiet-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.channels-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 0.9rem;
  border: 1px solid #e3eaf0;
  border-radius: var(--radius-sm);
  color: #728195;
  background: #fff;
  font-size: 0.74rem;
}

.channels-toolbar strong {
  margin-right: 0.2rem;
  color: #344a5e;
  font-family: var(--font-mono);
}

.channels-toolbar__refresh {
  color: #8794a2;
  font-size: 0.68rem;
}

.channels-limit-note,
.channels-success {
  margin: -0.45rem 0 0;
  color: #88703e;
  font-size: 0.72rem;
}

.channels-success {
  color: #107a5b;
}

.channels-success--warning {
  color: #a34836;
}

.channels-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 0.9rem;
}

.empty-state {
  display: grid;
  min-height: 15rem;
  justify-items: center;
  align-content: center;
  gap: 0.55rem;
  padding: 2.5rem 1rem;
  border: 1px dashed #dce5ec;
  border-radius: 0.75rem;
  color: var(--color-muted);
  background: #fbfcfd;
  text-align: center;
}

.empty-state__loader {
  width: 1.6rem;
  height: 1.6rem;
  border: 2px solid #dce7ef;
  border-top-color: #3988c7;
  border-radius: 50%;
  animation: spin 850ms linear infinite;
}

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

.empty-state strong {
  color: #506277;
  font-size: 0.76rem;
  font-weight: 650;
}

.empty-state > span:last-child {
  max-width: 24rem;
  font-size: 0.68rem;
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
  color: #805915;
  background: transparent;
  cursor: pointer;
  font-size: inherit;
  font-weight: 700;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 820px) {
  .channels-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .page-heading {
    align-items: flex-start;
  }

  .page-heading__actions {
    flex-direction: column;
  }

  .page-heading__description {
    max-width: 24rem;
  }

  .quiet-button {
    padding: 0.48rem 0.6rem;
    font-size: 0;
  }

  .quiet-button span {
    font-size: 1rem;
  }

  .channels-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.35rem;
  }
}
</style>
