import { describe, expect, it } from 'vitest'
import { toChineseError } from '@/api/error-message'
import { ApiError } from '@/api/http'

describe('localized API errors', () => {
  it('recognizes the backend security-group error spelling', () => {
    const error = new ApiError(
      503,
      'Aliyun security-group cleanup did not complete.',
      'Aliyun security-group cleanup did not complete.',
    )

    expect(toChineseError(error)).toContain('阿里云安全组操作失败')
  })

  it('maps a writing capture conflict to a download-specific Chinese message', () => {
    const error = new ApiError(
      409,
      'The newest capture segment is still being written',
      'The newest capture segment is still being written',
    )

    expect(toChineseError(error)).toBe('抓包片段仍在写入，暂时无法下载。')
  })

  it('maps a missing capture to a capture-specific Chinese message', () => {
    const error = new ApiError(404, 'Capture file not found', 'Capture file not found')

    expect(toChineseError(error)).toBe('抓包文件已不可用或已清理。')
  })
})
