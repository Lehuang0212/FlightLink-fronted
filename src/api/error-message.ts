import { ApiError } from './http'

export function toChineseError(
  error: unknown,
  fallback = '操作失败，请检查服务状态后重试。',
): string {
  if (!(error instanceof ApiError)) {
    if (error instanceof TypeError) return '无法连接后端服务，请检查服务和网络配置。'
    if (error instanceof Error && error.name === 'AbortError') return '请求已取消。'
    return fallback
  }

  const detail =
    typeof error.detail === 'string' ? error.detail.toLocaleLowerCase() : ''

  if (error.status === 401) {
    return detail.includes('invalid username') || detail.includes('invalid credentials')
      ? '用户名或密码错误。'
      : '登录状态已失效，请重新登录。'
  }
  if (error.status === 404) {
    if (detail.includes('capture file')) return '抓包文件已不可用或已清理。'
    return '端口组不存在或已被删除。'
  }
  if (error.status === 409) {
    if (detail.includes('capture') || detail.includes('segment')) {
      return '抓包片段仍在写入，暂时无法下载。'
    }
    if (detail.includes('disabled channels cannot be restarted')) {
      return '已停用的端口组无法重启，请先启用端口组。'
    }
    if (detail.includes('port') || detail.includes('conflict')) {
      return '端口冲突：该端口已被占用，请检查端口后重试。'
    }
    return '端口冲突或配置状态已变化，请检查后重试。'
  }
  if (error.status === 422) return '提交内容无效，请检查端口范围和连接协议。'
  if (error.status === 503) {
    if (/security[ -]group/.test(detail)) {
      return '阿里云安全组操作失败，请检查 RAM 权限和安全组配置。'
    }
    if (detail.includes('router')) return 'Router 服务暂不可用，请检查运行日志后重试。'
    if (detail.includes('capture')) return '抓包服务暂不可用，请检查抓包状态后重试。'
    return '后端服务暂不可用，请稍后重试。'
  }
  if (error.status >= 500) {
    if (detail.includes('router config')) return 'Router 配置生成失败，配置变更已回滚。'
    return '后端处理失败，请检查服务日志后重试。'
  }
  if (error.status === 400) return '请求内容无效，请检查输入后重试。'
  return fallback
}
