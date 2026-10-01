import { apiRequest } from './http'
import type { AdminPublic, LoginRequest } from './types'

export function loginAdmin(input: LoginRequest): Promise<AdminPublic> {
  return apiRequest<AdminPublic>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function logoutAdmin(): Promise<void> {
  return apiRequest<void>('/auth/logout', { method: 'POST' })
}

export function getCurrentAdmin(): Promise<AdminPublic> {
  return apiRequest<AdminPublic>('/auth/me')
}
