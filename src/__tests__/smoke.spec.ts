import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

function readEntryHtml(): string {
  try {
    return readFileSync(resolve(process.cwd(), 'index.html'), 'utf8')
  } catch {
    return ''
  }
}

function readMainSource(): string {
  return readFileSync(resolve(process.cwd(), 'src/main.ts'), 'utf8')
}

describe('SPA entry document', () => {
  it('provides the Vue application mount point', () => {
    expect(readEntryHtml()).toContain('<div id="app"></div>')
  })

  it('loads the TypeScript application entry', () => {
    expect(readEntryHtml()).toContain('/src/main.ts')
  })

  it('installs the router before mounting the root view', () => {
    expect(readMainSource()).toContain('createApp(App).use(router).mount')
  })
})
