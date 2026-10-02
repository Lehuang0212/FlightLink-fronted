<script setup lang="ts">
import type { CaptureFilePublic } from '@/api/types'

defineProps<{
  captures: readonly CaptureFilePublic[]
  loading?: boolean
  error?: string | null
  downloadingFileName?: string | null
}>()

defineEmits<{
  download: [capture: CaptureFilePublic]
}>()

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '未知大小'
  if (bytes < 1_024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1_024).toFixed(2)} KiB`
  return `${(bytes / 1_048_576).toFixed(2)} MiB`
}

function formatStartedAt(value: string | null): string {
  if (!value) return '未知时间'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '未知时间'
    : date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <p
    v-if="error"
    class="capture-file-state capture-file-state--error"
    role="alert"
  >
    {{ error }}
  </p>
  <p
    v-if="!error && loading && captures.length === 0"
    class="capture-file-state"
    role="status"
  >
    正在读取 PCAP 文件…
  </p>
  <div
    v-if="captures.length"
    class="capture-file-list"
  >
    <article
      v-for="capture in captures"
      :key="capture.file_name"
      class="capture-file"
      :class="{ 'capture-file--current': capture.is_current }"
    >
      <div
        class="capture-file__icon"
        aria-hidden="true"
      >
        PCAP
      </div>
      <div class="capture-file__details">
        <strong class="capture-file__name">{{ capture.file_name }}</strong>
        <div class="capture-file__meta">
          <time>{{ formatStartedAt(capture.started_at) }}</time>
          <span aria-hidden="true">·</span>
          <span>{{ formatSize(capture.size_bytes) }}</span>
        </div>
      </div>
      <span
        class="capture-file__state"
        :class="{ 'capture-file__state--current': capture.is_current }"
      >
        <span aria-hidden="true" />
        {{ capture.is_current ? '写入中' : '已关闭' }}
      </span>
      <button
        class="capture-file__download"
        type="button"
        :aria-label="`下载 ${capture.file_name}`"
        :disabled="capture.is_current || Boolean(downloadingFileName)"
        :title="capture.is_current ? '正在写入的片段不可下载' : undefined"
        @click="$emit('download', capture)"
      >
        {{ downloadingFileName === capture.file_name ? '下载中…' : '下载' }}
      </button>
    </article>
  </div>
  <p
    v-else-if="!error && !loading"
    class="capture-file-state"
    role="status"
  >
    暂无已生成的抓包文件。
  </p>
</template>

<style scoped>
.capture-file-list {
  display: grid;
  gap: 0.55rem;
}

.capture-file {
  display: grid;
  min-width: 0;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 0.8rem;
  padding: 0.7rem 0.75rem;
  border: 1px solid #e6ebf0;
  border-radius: 0.65rem;
  background: #fff;
}

.capture-file--current {
  border-color: #eeddb5;
  background: #fffdf8;
}

.capture-file__icon {
  display: grid;
  width: 2.45rem;
  height: 2.45rem;
  place-items: center;
  border: 1px solid #dce8f1;
  border-radius: 0.55rem;
  color: #3178ad;
  background: #f2f8fc;
  font-family: var(--font-mono);
  font-size: 0.56rem;
  font-weight: 750;
}

.capture-file__details {
  display: grid;
  min-width: 0;
  gap: 0.3rem;
}

.capture-file__name {
  overflow: hidden;
  color: #334a60;
  font-family: var(--font-mono);
  font-size: 0.67rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.capture-file__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  color: #8592a0;
  font-size: 0.63rem;
}

.capture-file__state {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #4f846e;
  font-size: 0.64rem;
  font-weight: 650;
  white-space: nowrap;
}

.capture-file__state > span {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: #3da57a;
}

.capture-file__state--current {
  color: #926a1d;
}

.capture-file__state--current > span {
  background: #d79a2b;
  box-shadow: 0 0 0 3px rgb(215 154 43 / 13%);
}

.capture-file__download {
  min-width: 3.6rem;
  min-height: 2rem;
  padding: 0.3rem 0.55rem;
  border: 1px solid #d8e4ed;
  border-radius: 0.45rem;
  color: #326d9f;
  background: #f8fbfd;
  cursor: pointer;
  font-size: 0.66rem;
  font-weight: 650;
}

.capture-file__download:hover:not(:disabled) {
  border-color: #b9d0e4;
  background: #edf6fc;
}

.capture-file__download:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.capture-file-state {
  margin: 0;
  padding: 1rem;
  border: 1px dashed #dce5ec;
  border-radius: 0.65rem;
  color: #7b8a99;
  background: #fbfcfd;
  font-size: 0.73rem;
  text-align: center;
}

.capture-file-state--error {
  border-style: solid;
  border-color: #f0d1d4;
  color: #9b3541;
  background: #fff5f5;
}

@media (max-width: 620px) {
  .capture-file {
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.55rem;
  }

  .capture-file__icon {
    width: 2.15rem;
    height: 2.15rem;
  }

  .capture-file__state {
    grid-column: 2;
    grid-row: 2;
  }

  .capture-file__download {
    grid-column: 3;
    grid-row: 1 / span 2;
  }
}
</style>
