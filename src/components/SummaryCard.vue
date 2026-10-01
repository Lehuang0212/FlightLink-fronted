<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  detail: string
  marker: string
}>()
</script>

<template>
  <article class="summary-card">
    <div class="summary-card__topline">
      <span class="summary-card__label">{{ label }}</span>
      <span
        class="summary-card__marker"
        aria-hidden="true"
      >{{ marker }}</span>
    </div>
    <strong class="summary-card__value">{{ value }}</strong>
    <span class="summary-card__detail">{{ detail }}</span>
  </article>
</template>

<style scoped>
.summary-card {
  display: grid;
  min-height: 9.25rem;
  gap: 0.55rem;
  padding: 1.1rem 1.2rem;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.summary-card__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.summary-card__label,
.summary-card__detail {
  color: var(--color-muted);
  font-size: 0.78rem;
}

.summary-card__label {
  font-weight: 650;
}

.summary-card__marker {
  color: #9aabba;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
}

.summary-card__value {
  align-self: center;
  color: #1e3449;
  font-size: clamp(1.6rem, 3vw, 2.05rem);
  letter-spacing: -0.055em;
  line-height: 1;
}

.summary-card__detail {
  align-self: end;
  font-size: 0.72rem;
}
</style>
