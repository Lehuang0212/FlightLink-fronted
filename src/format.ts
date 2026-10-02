export function formatDecimal(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '—' : value.toFixed(2)
}
