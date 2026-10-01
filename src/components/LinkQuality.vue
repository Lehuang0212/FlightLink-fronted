<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number | null
    label?: string
  }>(),
  { label: 'MAVLink 链路质量' },
)

const bars = [1, 2, 3, 4, 5, 6]
const quality = computed(() => {
  if (props.value === null || !Number.isFinite(props.value)) {
    return { value: null, level: 0, tone: 'unknown' }
  }
  const value = Math.max(0, Math.min(100, props.value))
  return {
    value,
    level: Math.ceil((value / 100) * bars.length),
    tone: value >= 80 ? 'good' : value >= 50 ? 'medium' : 'poor',
  }
})
</script>

<template>
  <div class="link-quality">
    <span class="link-quality__label">{{ label }}</span>
    <span
      class="link-quality__bars"
      :class="`link-quality__bars--${quality.tone}`"
      role="img"
      :aria-label="`${label}：${quality.value === null ? '未知' : `${quality.value}%`}`"
    >
      <span
        v-for="bar in bars"
        :key="bar"
        class="link-quality__bar"
        :class="{ 'link-quality__bar--active': bar <= quality.level }"
        :style="{ height: `${0.32 + bar * 0.12}rem` }"
        aria-hidden="true"
      />
    </span>
    <strong class="link-quality__value">{{ quality.value === null ? '未知' : `${quality.value}%` }}</strong>
  </div>
</template>

<style scoped>
.link-quality {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.7rem;
}

.link-quality__label {
  color: #58697d;
  font-size: 0.73rem;
  font-weight: 600;
}

.link-quality__bars {
  display: inline-flex;
  height: 1.15rem;
  align-items: end;
  gap: 0.15rem;
  margin-left: auto;
}

.link-quality__bar {
  display: block;
  width: 0.27rem;
  min-height: 0.25rem;
  border-radius: 0.1rem 0.1rem 0.05rem 0.05rem;
  background: #dce3e9;
}

.link-quality__bars--good .link-quality__bar--active {
  background: #20a77d;
}

.link-quality__bars--medium .link-quality__bar--active {
  background: #d39a32;
}

.link-quality__bars--poor .link-quality__bar--active {
  background: #cf5763;
}

.link-quality__value {
  min-width: 2.5rem;
  color: #334c62;
  font-family: var(--font-mono);
  font-size: 0.74rem;
  text-align: right;
}
</style>
