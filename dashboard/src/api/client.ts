type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Primary storage key used by the dashboard.
const TOKEN_KEY = 'linkguard_admin_token'

// Fallback keys used by other auth flows (e.g., login storing `access_token`).
// We will prefer a JWT-looking value (three base64url-ish segments separated by dots)
// and migrate it into TOKEN_KEY for consistency.
const FALLBACK_TOKEN_KEYS = ['access_token', 'linkguard_access_token', 'token', 'jwt'] as const

function looksLikeJwt(token: string): boolean {
  // JWTs are typically: header.payload.signature
  return token.split('.').length === 3
}

function isKnownDevPlaceholder(token: string): boolean {
  return token === 'dev-admin-token' || token === 'dev-token'
}

export function getToken(): string | null {
  const primary = localStorage.getItem(TOKEN_KEY)
  if (primary && !isKnownDevPlaceholder(primary)) return primary

  // If primary is a known placeholder (or missing), try fallbacks.
  const candidates: Array<{ key: string; value: string }> = []

  for (const key of FALLBACK_TOKEN_KEYS) {
    const v = localStorage.getItem(key)
    if (v) candidates.push({ key, value: v })
  }

  if (candidates.length === 0) return null

  // Prefer a JWT-looking candidate.
  const preferred = candidates.find((c) => looksLikeJwt(c.value) && !isKnownDevPlaceholder(c.value)) ??
    candidates.find((c) => !isKnownDevPlaceholder(c.value))

  if (!preferred) return null

  // Migrate to primary key so the rest of the app is consistent.
  try {
    localStorage.setItem(TOKEN_KEY, preferred.value)
  } catch {
    // ignore storage errors
  }

  return preferred.value
}

export function setToken(token: string): void {
  if (!token || isKnownDevPlaceholder(token)) {
    clearToken()
    return
  }
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  for (const key of FALLBACK_TOKEN_KEYS) localStorage.removeItem(key)
}

export async function apiRequest<T>(
  path: string,
  options?: {
    method?: HttpMethod
    body?: unknown
    auth?: boolean
    signal?: AbortSignal
  },
): Promise<T> {
  const method = options?.method ?? 'GET'
  const auth = options?.auth ?? true

  const headers: Record<string, string> = { Accept: 'application/json' }

  let body: string | undefined
  if (options?.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body,
    signal: options?.signal,
  })

  const contentType = res.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await res.json().catch(() => null) : await res.text().catch(() => '')

  if (!res.ok) {
    type ErrorPayload = {
      detail?: unknown
      message?: unknown
    }

    const message = (() => {
      if (typeof payload === 'string' && payload) return payload

      if (payload && typeof payload === 'object') {
        const err = payload as ErrorPayload
        if (err.detail) return String(err.detail)
        if (err.message) return String(err.message)
      }

      return `Request failed: ${res.status} ${res.statusText}`
    })()

    throw new Error(message)
  }

  return payload as T
}

export const api = {
  get: <T>(path: string, auth = true) => apiRequest<T>(path, { method: 'GET', auth }),
  post: <T>(path: string, body?: unknown, auth = true) => apiRequest<T>(path, { method: 'POST', body, auth }),
  put: <T>(path: string, body?: unknown, auth = true) => apiRequest<T>(path, { method: 'PUT', body, auth }),
  del: <T>(path: string, auth = true) => apiRequest<T>(path, { method: 'DELETE', auth }),
}