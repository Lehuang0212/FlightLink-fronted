export interface EndpointStatistics {
  id: string
  lines: string[]
}

/** Recognize complete native ReportStats blocks without interpreting their counters. */
export function splitRouterLogs(lines: readonly string[]) {
  const endpoints = new Map<string, EndpointStatistics>()
  const events: string[] = []
  let pending: EndpointStatistics | undefined
  let depth = 0
  const ansi = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*[A-Za-z]`, 'g')
  for (const raw of lines) {
    const line = raw.replace(ansi, '')
    const header = line.match(/^((?:UDP|TCP|UART|Log) Endpoint \[-?\d+\].*?)\s*\{$/)
    if (header) {
      pending = { id: header[1]!, lines: [line] }
      depth = 1
    } else if (pending) {
      // Only native statistics rows belong to the block; interleaved errors remain events.
      if (/^\s*(?:Received messages \{|Transmitted messages \{|CRC error:|Sequence lost:|Handled:|Total:|\})/.test(line)) {
        pending.lines.push(line)
        depth += (line.match(/\{/g)?.length ?? 0) - (line.match(/\}/g)?.length ?? 0)
        if (depth === 0) {
          endpoints.set(pending.id, pending)
          pending = undefined
        }
      } else if (line.trim()) {
        events.push(line)
      }
    } else if (line.trim() && !/^\s*(?:Received messages \{|Transmitted messages \{|CRC error:|Sequence lost:|Handled:|Total:|\})/.test(line)) {
      // A journal tail may begin halfway through an older statistics block.
      events.push(line)
    }
  }
  return { endpoints: [...endpoints.values()], events }
}

export function statisticsTone(line: string): string {
  if (line.includes('CRC error:')) return /CRC error:\s*[1-9]/.test(line) ? 'critical' : 'muted'
  if (line.includes('Sequence lost:')) return /Sequence lost:\s*[1-9]/.test(line) ? 'warning' : 'muted'
  if (line.includes('Endpoint')) return 'info'
  if (line.includes('messages {')) return 'section'
  return 'default'
}
