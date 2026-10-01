<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <section class="route-placeholder">
    <p class="route-placeholder__eyebrow">
      FlightLink-Console 管理平台
    </p>
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
  </section>
</template>

<style scoped>
.route-placeholder {
  max-width: 52rem;
  padding: clamp(1.5rem, 4vw, 2.5rem);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.route-placeholder__eyebrow {
  margin: 0 0 0.75rem;
  color: var(--color-primary);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0;
  font-size: clamp(1.7rem, 4vw, 2.2rem);
  letter-spacing: -0.04em;
}

p:last-child {
  max-width: 38rem;
  margin: 0.8rem 0 0;
  color: var(--color-muted);
  line-height: 1.7;
}
</style>
