import { apiRequest } from './http'
import type { HealthPublic } from './types'

export function getHealth(): Promise<HealthPublic> {
  return apiRequest<HealthPublic>('/health')
}
