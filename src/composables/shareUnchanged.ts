/** Reuse unchanged JSON branches so background polls do not churn component props. */
export function shareUnchanged<T>(previous: T | undefined, next: T): T {
  if (Object.is(previous, next)) return next
  if (Array.isArray(previous) && Array.isArray(next)) {
    const byId = new Map<unknown, unknown>()
    for (const item of previous) {
      if (item && typeof item === 'object' && 'id' in item) byId.set(item.id, item)
    }
    const values = next.map((item, index) => {
      const prior = item && typeof item === 'object' && 'id' in item
        ? byId.get(item.id) : previous[index]
      return shareUnchanged(prior, item)
    })
    return (previous.length === values.length && values.every((item, index) => item === previous[index])
      ? previous : values) as T
  }
  if (previous && next && typeof previous === 'object' && typeof next === 'object'
    && !Array.isArray(previous) && !Array.isArray(next)) {
    const before = previous as Record<string, unknown>
    const after = next as Record<string, unknown>
    const keys = Object.keys(after)
    const values = Object.fromEntries(keys.map((key) => [key, shareUnchanged(before[key], after[key])]))
    return (Object.keys(before).length === keys.length && keys.every((key) =>
      Object.hasOwn(before, key) && Object.is(before[key], values[key])) ? previous : values) as T
  }
  return next
}
