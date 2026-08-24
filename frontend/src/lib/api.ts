import type {
  AnalysisJobStatusResponse,
  AnalysisProgressResponse,
  AnalysisResponse,
  AuthConfigResponse,
  UploadReportResponse,
} from '../types/api'

const defaultApiBaseUrl = '/api'
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? defaultApiBaseUrl
const USERNAME_KEY = 'trustsignal_auth_username'

export function setAuthToken(_token: string | null): void {
  // legacy no-op; auth now uses HttpOnly session cookies
}

function cookieValue(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

async function authFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers ?? {})
  const csrf = cookieValue('trustsignal_csrf')
  if (csrf) headers.set('X-CSRF-Token', csrf)

  const response = await fetch(input, { ...init, headers, credentials: 'include' })

  if (response.status === 401) {
    window.dispatchEvent(new Event('trustsignal-auth-expired'))
    throw new Error('Session expired. Please sign in again.')
  }

  return response
}

export async function getAuthConfig(): Promise<AuthConfigResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/config`, { credentials: 'include' })
  if (!response.ok) throw new Error('Unable to load auth config')
  return response.json() as Promise<AuthConfigResponse>
}

export async function validateSession(): Promise<boolean> {
  try {
    const response = await authFetch(`${API_BASE_URL}/auth/session`)
    if (!response.ok) return false
    const payload = (await response.json()) as { authenticated: boolean }
    return Boolean(payload.authenticated)
  } catch {
    return false
  }
}

export async function setupLogin(username: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Setup failed' }))
    throw new Error(payload.detail ?? 'Setup failed')
  }
}

export async function login(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Login failed' }))
    throw new Error(payload.detail ?? 'Login failed')
  }
  const payload = (await response.json()) as { token: string }
  window.localStorage.setItem(USERNAME_KEY, username.trim())
  return payload.token
}

export async function logout(): Promise<void> {
  await authFetch(`${API_BASE_URL}/auth/logout`, { method: 'POST' })
}

export async function uploadReport(file: File): Promise<UploadReportResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await authFetch(`${API_BASE_URL}/reports/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(payload.detail ?? 'Upload failed')
  }

  return response.json() as Promise<UploadReportResponse>
}

export function reportFileUrlWithAuth(reportId: string, page?: number): string {
  const url = `${API_BASE_URL}/reports/${reportId}/file`
  return page && page > 0 ? `${url}#page=${page}` : url
}

export async function purgeReports(): Promise<void> {
  await authFetch(`${API_BASE_URL}/reports/purge`, { method: 'POST', keepalive: true })
}

export async function getAnalysisProgress(reportId: string): Promise<AnalysisProgressResponse> {
  const response = await authFetch(`${API_BASE_URL}/reports/${reportId}/progress`)

  if (!response.ok) {
    throw new Error('Progress unavailable')
  }

  return response.json() as Promise<AnalysisProgressResponse>
}

export async function startAnalysisJob(reportId: string): Promise<AnalysisJobStatusResponse> {
  const response = await authFetch(`${API_BASE_URL}/reports/${reportId}/analyze/start`, {
    method: 'POST',
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Failed to start analysis' }))
    throw new Error(payload.detail ?? 'Failed to start analysis')
  }

  return response.json() as Promise<AnalysisJobStatusResponse>
}

export async function getAnalysisJobStatus(reportId: string): Promise<AnalysisJobStatusResponse> {
  const response = await authFetch(`${API_BASE_URL}/reports/${reportId}/analyze/status`)

  if (!response.ok) {
    throw new Error('Analysis status unavailable')
  }

  return response.json() as Promise<AnalysisJobStatusResponse>
}

export async function getReportAnalysis(reportId: string): Promise<AnalysisResponse> {
  const response = await authFetch(`${API_BASE_URL}/reports/${reportId}/analysis`)

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Analysis failed' }))
    throw new Error(payload.detail ?? 'Analysis failed')
  }

  return response.json() as Promise<AnalysisResponse>
}
