type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'linkguard_admin_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
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