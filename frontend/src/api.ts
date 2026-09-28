import type {
  ApiError,
  DataHealth,
  HealthResponse,
  PlanResult,
} from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  let body: unknown = null
  try {
    body = await resp.json()
  } catch {
    body = null
  }
  if (!resp.ok) {
    const err: ApiError =
      body && typeof body === 'object' && 'error' in body
        ? (body as ApiError)
        : { error: 'http_error', detail: `HTTP ${resp.status}`, issues: [] }
    throw err
  }
  return body as T
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  seed: () => request<DataHealth>('/api/seed', { method: 'POST' }),

  plan: () => request<PlanResult>('/api/plan', { method: 'POST' }),

}

export function describeApiError(err: unknown): string {
  if (err && typeof err === 'object') {
    const e = err as ApiError
    if (e.issues && e.issues.length > 0) return `${e.error}: ${e.issues.length} issue(s) found`
    if (e.detail) return `${e.error}: ${e.detail}`
  }
  return err instanceof Error ? err.message : 'Unexpected error'
}